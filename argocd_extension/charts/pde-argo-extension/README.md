# PDE Argo CD extension chart

Deploys the **backend** (proxy to PDE Operator), **UI ConfigMap**, and **backend RBAC ConfigMap**.
Wire Argo CD with the kubectl patches in [argocd_extension/README.md](../../README.md)
(or enable `argoPatches` on merge-capable custom Helm platforms).

```bash
helm upgrade --install pde-argo-extension ./argocd_extension/charts/pde-argo-extension -n argocd \
  --set backend.operatorBaseUrl=http://pde-operator.pde-system.svc:8000 \
  --set backend.operatorApiToken=<admin-token>
```

When installing via Argo CD, set `backend.operatorApiToken` explicitly - Helm `lookup` of the operator Secret does not run during `helm template`.

| Key                                           | Default                 | Purpose                                            |
|-----------------------------------------------|-------------------------|----------------------------------------------------|
| `extension.name`                              | `pde-argo-extension`    | Proxy path + ConfigMap `PDE_EXTENSION_NAME`        |
| `ui.config.application`                       | `argocd:pde-operator`   | ConfigMap `PDE_ANCHOR_APPLICATION`                 |
| `ui.config.project`                           | `default`               | ConfigMap `PDE_ANCHOR_PROJECT`                     |
| `backend.operatorBaseUrl`                     | in-cluster operator     | Any reachable operator URL                         |
| `backend.operatorApiToken` / `operatorSecret` | token or lookup         | Admin token (lookup only on live `helm install`)   |
| `backend.rbac.writeUsers`                     | `[admin]`               | Seeded into backend RBAC CM (`Argocd-Username`)    |
| `backend.rbac.writeGroups`                    | `[]`                    | Seeded into backend RBAC CM (`Argocd-User-Groups`) |
| `ui.image.*`                                  | `pde-argo-extension-ui` | UI init image (manual patch / argoPatches)         |
| `argoPatches.enabled`                         | `false`                 | Emit Argo merge patches (custom Helm only)         |

**Do not** set `argoPatches.enabled=true` on upstream Helm against an existing Argo install. Use the manual patches in the extension readme instead.

**Reconfigure UI:** edit ConfigMap `pde-argo-extension-ui-config`, then restart `argocd-server`.

**Reconfigure writers:** edit ConfigMap `pde-argo-extension-backend-rbac` (`PDE_RBAC_WRITE_USERS` /
`PDE_RBAC_WRITE_GROUPS`, comma-separated), then restart `pde-argo-extension-backend`.
