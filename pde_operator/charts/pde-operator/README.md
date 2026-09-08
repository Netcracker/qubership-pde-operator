# PDE Operator Helm chart

Deploys the operator plus optional in-chart **Postgres** and **MinIO**.

```bash
# from the repository root
docker build -f pde_operator/Dockerfile -t pde-operator:<tag> .
helm upgrade --install pde-operator pde_operator/charts/pde-operator -n pde-system --create-namespace \
  --set fullnameOverride=pde-operator \
  --set image.tag=<tag>
```

Expected release namespace is **`pde-system`** (`-n pde-system --create-namespace`, or Argo `destination.namespace`). Helm has no `values.yaml` default for that.

When `dbInit.enabled` (default), an init container runs `pde-operator-init-db` before the operator starts. Probes: `/health` (live), `/ready` (Postgres + `runs` table).

| Value                                       | Default                         | Purpose                                                                      |
|---------------------------------------------|---------------------------------|------------------------------------------------------------------------------|
| `ui.enabled`                                | `true`                          | Dev UI at `/ui`                                                              |
| `dbInit.enabled`                            | `true`                          | Schema init container                                                        |
| `postgres.enabled`                          | `true`                          | In-chart Postgres                                                            |
| `minio.enabled`                             | `true`                          | In-chart MinIO + bucket Job                                                  |
| `image.*`                                   | `pde-operator`                  | Container image                                                              |
| `auth.apiAdminToken` / `jobTokenSigningKey` | empty -> generate               | Stable if set explicitly                                                     |
| `auth.inputEncryptionKey`                   | empty -> generate               | Any secret string; operator derives Fernet key (lookup on upgrade)           |
| `rbac.listClusterNamespaces`                | `true`                          | ClusterRole to list namespaces for declarative enum provider                 |
| `externalSecrets.create`                    | `true`                          | Chart creates empty `{fullname}-external-secrets` (set false if ESO owns it) |
| `externalSecrets.mountPath`                 | `/var/run/secrets/pde-external` | Job mount path; Secret is optional if missing                                |
| `jobRuntime.mountPath`                      | `/opt/pde-operator/job-runtime` | ConfigMap-mounted `job-entrypoint.py` for PDE Jobs                           |

External Secret keys for mounted AtlasConfig: include `SOPS_AGE_KEY` and `SOPS_AGE_RECIPIENTS` plus your secret values.

**External Postgres / MinIO:** set `postgres.enabled=false` / `minio.enabled=false` and fill `*.external.*`.

**No schema init:** `--set dbInit.enabled=false` and run `pde-operator-init-db` yourself before the pod can become Ready.

Jobs are created in the release namespace by default (`operator.k8sNamespace` empty).
