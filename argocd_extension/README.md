# PDE Operator Argo CD Extension

System-level Argo CD UI ("PDE Operator" system sidebar tab) plus a small Go backend, authenticated via **Argo CD proxy extensions**.

## Installation

### 0. Prerequisite - Argo RBAC

Append the PDE lines to the **`policy.csv`** key in `argocd-rbac-cm` (under `data:`). Keep any
existing Argo default lines. Adjust project/app if your anchor Application differs.

PDE lines to append:

```csv
p, role:pde-users, applications, get, default/pde-operator, allow
p, role:pde-users, extensions, invoke, pde-argo-extension, allow
g, admin, role:pde-users
```

`applications, get` on the anchor Application is required by Argo for every proxy-extension
call (together with `extensions, invoke`). It does not grant PDE write access by itself.

`argocd-rbac-cm` sample:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: argocd-rbac-cm
  namespace: argocd
data:
  policy.default: role:readonly
  policy.csv: |
    p, role:pde-users, applications, get, default/pde-operator, allow
    p, role:pde-users, extensions, invoke, pde-argo-extension, allow
    g, admin, role:pde-users
```

```bash
kubectl -n argocd edit configmap argocd-rbac-cm
```

**Read vs write:** Argo only gates who may open the extension (`invoke`). Mutations (start/retry/cancel
runs, template/profile changes, cleanup, config import) are enforced by the extension backend using
`Argocd-Username` / `Argocd-User-Groups` against ConfigMap `pde-argo-extension-backend-rbac`:

| Key                     | Matches              | Typical use                               |
|-------------------------|----------------------|-------------------------------------------|
| `PDE_RBAC_WRITE_USERS`  | `Argocd-Username`    | Lab local accounts (`admin`, `pde_write`) |
| `PDE_RBAC_WRITE_GROUPS` | `Argocd-User-Groups` | Customer IdP groups (preferred)           |

Helm seeds that ConfigMap from `backend.rbac.writeUsers` / `writeGroups` (default: `writeUsers: [admin]`).
Edit the ConfigMap, then restart the backend Deployment:

```bash
kubectl -n argocd edit configmap pde-argo-extension-backend-rbac
kubectl -n argocd rollout restart deploy/pde-argo-extension-backend
```

Anyone with `role:pde-users` can view catalog/runs/logs/artifacts. Only users/groups on the write
allowlist get mutate APIs and write UI controls.

### 1. Backend + UI ConfigMap

```bash
helm upgrade --install pde-argo-extension ./argocd_extension/charts/pde-argo-extension -n argocd \
  --set backend.operatorBaseUrl=http://pde-operator.pde-system.svc:8000 \
  --set backend.operatorApiToken=<admin-token>
```

Via Argo CD Apps, set `backend.operatorApiToken` explicitly (`lookup` does not run under `helm template`).

### 2. Wire Argo CD (manual patches)

Apply the three strategic-merge patches below (defaults match chart values). Adjust Service DNS, UI image, or ConfigMap name if you changed Helm names.

### 2a. Enable proxy extensions

```bash
kubectl -n argocd patch configmap argocd-cmd-params-cm --type merge -p '{"data":{"server.enable.proxy.extension":"true"}}'
```

### 2b. Register the proxy -> backend

```bash
kubectl -n argocd patch configmap argocd-cm --type merge --patch "$(cat <<'EOF'
data:
  extension.config.pde-argo-extension: |
    connectionTimeout: 2s
    keepAlive: 15s
    idleConnectionTimeout: 60s
    maxIdleConnections: 30
    services:
      - url: http://pde-argo-extension-backend.argocd.svc:8081
EOF
)"
```

### 2c. UI init container on `argocd-server`

```bash
kubectl -n argocd patch deployment argocd-server --type strategic --patch "$(cat <<'EOF'
spec:
  template:
    spec:
      volumes:
        - name: pde-argo-extension-ui
          emptyDir: {}
      initContainers:
        - name: pde-argo-extension-ui
          image: ghcr.io/netcracker/pde-argo-extension-ui:<tag>
          imagePullPolicy: IfNotPresent
          envFrom:
            - configMapRef:
                name: pde-argo-extension-ui-config
          volumeMounts:
            - name: pde-argo-extension-ui
              mountPath: /tmp/extensions
      containers:
        - name: argocd-server
          volumeMounts:
            - name: pde-argo-extension-ui
              mountPath: /tmp/extensions
EOF
)"
```

### 3. Restart `argocd-server`

```bash
kubectl -n argocd rollout restart deploy/argocd-server
```

## Optional: `argoPatches.enabled` (non-upstream Helm only)

Chart templates can emit the same three partial resources when:

```yaml
argoPatches:
  enabled: true
```

**Do not enable on upstream Helm** against an existing Argo install - Helm will refuse (or fight) objects it does not own (`argocd-cm`, `argocd-cmd-params-cm`, `argocd-server`).
This flag is for custom Helm platforms that support patch output into already-installed apps (values-driven).

## Images

Prebuilt images are published to GHCR:

| Component         | Image                                           |
|-------------------|-------------------------------------------------|
| Operator          | `ghcr.io/netcracker/pde-operator`               |
| Extension backend | `ghcr.io/netcracker/pde-argo-extension-backend` |
| Extension UI      | `ghcr.io/netcracker/pde-argo-extension-ui`      |

Build locally from the repository root:

```bash
docker build -f pde_operator/Dockerfile -t pde-operator:<tag> .
docker build -f argocd_extension/backend/Dockerfile -t pde-argo-extension-backend:<tag> argocd_extension/backend
docker build -f argocd_extension/ui/Dockerfile -t pde-argo-extension-ui:<tag> argocd_extension/ui
```
