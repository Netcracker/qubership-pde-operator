# PDE extension backend

Gateway in front of pde-operator, reached via Argo CD proxy extensions.

- Listens on `:8081` (`pde-argo-extension-backend` Service)
- Forwards paths to `pde-operator/api/v1/*`
- Injects `Authorization: Bearer <auth token>`; strips inbound `Cookie` / `Authorization`
- Enforces write access using `Argocd-Username` / `Argocd-User-Groups` vs allowlists
- Serves `GET /capabilities` -> `{ "canWrite": bool, "username": string }`

Argo strips `/extensions/<name>` before forwarding (`/runs`, `/profiles`, ...).

| Variable                 | Default                                   | Purpose                          |
|--------------------------|-------------------------------------------|----------------------------------|
| `LISTEN_ADDR`            | `:8081`                                   | Listen address                   |
| `PDE_OPERATOR_BASE_URL`  | `http://pde-operator.pde-system.svc:8000` | Operator base                    |
| `PDE_OPERATOR_API_TOKEN` | _(required)_                              | Auth token                       |
| `PDE_RBAC_WRITE_USERS`   | _(empty)_                                 | Comma-separated usernames        |
| `PDE_RBAC_WRITE_GROUPS`  | _(empty)_                                 | Comma-separated IdP group names  |

Non-writers may only use `GET`/`HEAD`/`OPTIONS`. Other methods return `403` with `write_forbidden`.

```bash
docker build -t pde-argo-extension-backend:<tag> .
```
