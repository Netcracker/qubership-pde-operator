# qubership-pde-operator

Kubernetes control plane for PDE pipeline runs.

See the repository root [README.md](../README.md) for overall repository structure, API auth, security, MCP, and metrics.

## Requirements

- Python 3.13+
- [uv](https://docs.astral.sh/uv/)

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
| `PDE_DEFAULT_IMAGE`                                 | `ghcr.io/.../executor:v2.2.2`                              | Seeded `default` profile image                 |
| `PDE_DELIVERY_*_INTERVAL`                           | `5 / 15 / 15`                                              | PDE `STATUS`/`REPORT`/`LOG` delivery (seconds) |
| `K8S_JOB_RESOURCES`                                 | (cpu/memory JSON)                                          | Default Job resources                          |
| `RETENTION_ENABLED` / `DAYS` / `CRON`               | `true` / `30` / `0 0 * * *`                                | Retention cleanup                              |
| `MINIO_*`                                           | localhost defaults                                         | Artifact store                                 |

Full names are `PDE_OPERATOR_<Variable>` (e.g. `PDE_OPERATOR_DATABASE_URL`).
