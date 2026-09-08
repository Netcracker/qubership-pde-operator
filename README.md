# qubership-pde-operator

Kubernetes control plane for [PDE](https://github.com/Netcracker/qubership-pipelines-declarative-executor) pipeline runs.

Accepts run requests via REST, spawns PDE workloads as Kubernetes Jobs, tracks lifecycle, and stores reports/artifacts.

- Operator Helm chart: [pde-operator](pde_operator/charts/pde-operator/README.md)
- Argo CD extension: [argocd_extension](argocd_extension/README.md)
- Declarative run templates (GitLab-compatible syntax): [Syntax Guide](docs/declarative_run_templates_syntax.md)
- API docs: `/docs` on a running server; probes: `/health` (live), `/ready` (DB + schema)

## Requirements

- Python 3.13+
- [uv](https://docs.astral.sh/uv/)

## API auth

`/api/v1/*` requires Bearer auth (`/health` and `/ready` stay open):

- **Admin** (`PDE_OPERATOR_API_ADMIN_TOKEN`) - full API (CI, Dev UI, `/docs`, MCP)
- **Job JWT** - minted per Job; that run’s deliveries/artifacts, parent `state` on retry, and `GET /runs/{id}/input`

`PDE_OPERATOR_JOB_TOKEN_SIGNING_KEY` signs Job JWTs. If either secret is unset at startup, an ephemeral value is generated and logged at WARNING.

## Security

Secrets are split by scope — nothing sensitive should live in Postgres, Job Pod specs, or profile `env_vars` by default.

| Scope                   | Mechanism                                                                                                                                                                                                                                                                                      |
|-------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **API**                 | Admin Bearer for operators/CI/UI; per-run JWT for Job callbacks only (deliveries, artifacts, parent state on retry, run input fetch).                                                                                                                                                          |
| **Per-run params**      | `pipeline_vars_secure` and other start params are encrypted in MinIO (`{run_id}/input.json`) before the run row is written. Postgres stores `[MASKED]` for UI; Jobs fetch decrypted input via `GET /runs/{id}/input`.                                                                          |
| **Cluster / namespace** | Optional `{release}-external-secrets` Secret mounted as files in every Job (`/var/run/secrets/pde-external`). Entrypoint loads keys into env and can build SOPS-encrypted `CUSTOM_GLOBAL_CONFIG_MOUNTED_SECRETS` for PDE AtlasConfig. Keys are not declared on the Pod `env` / `envFrom` spec. |

**Practical rules:** put shared secrets (registry tokens, API keys) in the external-secrets mount; put per-run secrets in `pipeline_vars_secure` at create time; do not treat profile or run `env_vars` as a secrets store. Run input encryption uses `PDE_OPERATOR_INPUT_ENCRYPTION_KEY`.

## MCP

Streamable HTTP at `/api/v1/mcp/` (same admin Bearer). Tools: list/get/create/cancel/retry runs, get log. Resources: `pde://lifecycle`, `pde://pipeline-inputs`, `pde://profiles`. Prompt: `investigate_run`.

## Metrics

`GET /metrics` (unauthenticated): `pde_operator_runs_queued`, `pde_operator_runs_in_progress`, `pde_operator_runs_total`.

## Configuration

Env prefix: `PDE_OPERATOR_`.

| Variable                                            | Default                                                    | Description                                    |
|-----------------------------------------------------|------------------------------------------------------------|------------------------------------------------|
| `HOST` / `PORT`                                     | `0.0.0.0` / `8000`                                         | Bind address                                   |
| `LOG_LEVEL`                                         | `INFO`                                                     | App logger                                     |
| `UI_ENABLED`                                        | `true`                                                     | Dev UI at `/ui`                                |
| `API_ADMIN_TOKEN`                                   | _(generated)_                                              | Admin Bearer                                   |
| `JOB_TOKEN_SIGNING_KEY`                             | _(generated)_                                              | HMAC for Job JWTs                              |
| `INPUT_ENCRYPTION_KEY`                              | _(generated)_                                              | Run input encryption secret                    |
| `JOB_TOKEN_TTL_SECONDS`                             | `172800`                                                   | Job JWT lifetime                               |
| `DATABASE_URL`                                      | `postgresql+asyncpg://pde:pde@localhost:5432/pde_operator` | Postgres                                       |
| `EXECUTION_URL_BASE`                                | `http://localhost:8000`                                    | Human-facing run URL base                      |
| `OPERATOR_BASE_URL`                                 | `http://host.minikube.internal:8000`                       | URL pods use to reach operator                 |
| `K8S_NAMESPACE`                                     | `pde-system`                                               | Job namespace                                  |
| `K8S_JOB_TTL_SECONDS`                               | `300`                                                      | Job TTL after finish                           |
| `K8S_JOB_CREATION_ENABLED`                          | `true`                                                     | Allow creating Jobs                            |
| `MAX_CONCURRENT_RUNS`                               | `10`                                                       | Cap; `<=0` = unlimited                         |
| `QUEUE_ENABLED` / `QUEUE_POLL_SECONDS`              | `true` / `5`                                               | FIFO queue worker                              |
| `RECONCILER_ENABLED` / `INTERVAL` / `STUCK_TIMEOUT` | `true` / `30` / `1800`                                     | Job run reconciler                             |
| `CANCEL_GRACE_SECONDS`                              | `60`                                                       | SIGINT then hard-stop                          |
| `PDE_DEFAULT_IMAGE`                                 | `ghcr.io/.../executor:v2.2.1`                              | Seeded `default` profile image                 |
| `PDE_DELIVERY_*_INTERVAL`                           | `5 / 15 / 15`                                              | PDE `STATUS`/`REPORT`/`LOG` delivery (seconds) |
| `K8S_JOB_RESOURCES`                                 | (cpu/memory JSON)                                          | Default Job resources                          |
| `RETENTION_ENABLED` / `DAYS` / `CRON`               | `true` / `30` / `0 0 * * *`                                | Retention cleanup                              |
| `MINIO_*`                                           | localhost defaults                                         | Artifact store                                 |

Full names are `PDE_OPERATOR_<Variable>` (e.g. `PDE_OPERATOR_DATABASE_URL`).
