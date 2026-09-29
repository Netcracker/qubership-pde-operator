# PDE Operator - Architecture & Roadmap

Kubernetes control plane for **PDE as a Service**: accept pipeline run requests, spawn isolated PDE Jobs, track lifecycle, store reports/archives, expose REST (and related surfaces).

PDE itself stays unchanged - it remains the execution engine inside Job pods.

- Setup / settings: [README.md](../README.md)
- Helm: [charts/pde-operator](../pde_operator/charts/pde-operator/README.md)
- Argo CD extension: [argocd_extension](../argocd_extension/README.md)

## Primary use case

**CI on a cluster** (workflows in other repos call this operator over REST):

1. Submit a run (`POST /runs`), poll status, download log / state / x_debug.
2. **Cancel** and **smart-retry** map to first-class operator APIs.

**Same API also powers:** Dev UI (`/ui`), embedded MCP (`/api/v1/mcp/`), Argo CD system extension ("PDE Operator").

## Architecture

```text
┌──────────────────────────────────────────────────────────────┐
│  namespace: pde-system                                       │
│  ┌────────────────┐  ┌────────────┐  ┌──────────┐            │
│  │ pde-operator   │──│ PostgreSQL │  │  MinIO   │            │
│  │ FastAPI +      │  │ runs /     │  │ artifacts│            │
│  │ workers        │  │ profiles   │  │ + input  │            │
│  └───────┬────────┘  └────────────┘  └──────────┘            │
│          │ Job create / signal / watch                       │
│          ▼                                                   │
│     PDE Jobs (fetch input -> run|retry -> archive -> upload) │
└──────────────────────────────────────────────────────────────┘
        ▲
        │ REST: CI / MCP / Dev UI / Argo CD extension
```

| Piece                 | Role                                                                 |
|-----------------------|----------------------------------------------------------------------|
| **Operator**          | REST, queue, Job create/cancel, report ingest, reconciler, retention |
| **PostgreSQL**        | Run + profile metadata                                               |
| **MinIO**             | Per-run artifacts + encrypted `input.json` (real run-start payload)  |
| **Dev UI**            | Console at `/ui`                                                     |
| **Argo CD extension** | "PDE Operator" UI -> Argo proxy -> backend -> operator API           |

## Status

### Core

- Runs: create, list, detail, cancel (SIGINT + grace), smart-retry, remote deliveries, artifacts
- Scheduled runs: CRON + timezone, enable/disable, manual trigger, run history per schedule
- Profiles: CRUD (`default` protected); Describes image, env, resources
- Auth: admin Bearer + per-Job JWTs; readiness `/ready` (DB + schema)
- Queue, reconciler, retention; Helm chart (optional in-chart Postgres/MinIO)
- MCP Streamable HTTP; Prometheus gauges at `/metrics`
- Argo CD system extension (proxy + RBAC on operator Application)

### Security

- **External secrets for Jobs** — optional cluster Secret mounted as files; entrypoint exports env + SOPS-encrypted AtlasConfig (`CUSTOM_GLOBAL_CONFIG_MOUNTED_SECRETS`); not on Pod `envFrom`
- **Encrypted run input** — `pipeline_vars_secure` and other start params in MinIO `{run_id}/input.json`; Postgres masked; Job entrypoint fetches via `GET /runs/{id}/input`
- **Profile list API** — safe list shape; full detail on `GET /profiles/{id}`

## Scheduled runs

`/api/v1/schedules` manages CRON-scheduled runs: a schedule stores the same parameters as a manual run plus a cron expression and an explicit IANA timezone, and fires normal runs on that cadence. The Dev UI exposes them in the **Schedules** tab (admin mode), including a per-schedule run history.

- Cron takes 5 fields (`minute hour day month weekday`) or 6 with seconds **first**; expressions firing more often than `PDE_OPERATOR_SCHEDULES_MIN_INTERVAL_SECONDS` (default 60s) are rejected.
- Each fired run records `triggered_by = "schedule:<id>"` and its Job is labelled `pde.schedule/id`, so `GET /runs?triggered_by=schedule:<id>` lists everything a schedule produced.
- Overlap is per schedule: `allow` (default) fires even while the previous run is still active; `skip` holds that firing instead.
- Fire times that pass while the operator is down are skipped, not replayed: the schedule re-anchors to its next occurrence. `last_fire_status` records `success`, `failed`, `skipped_overlap` or `skipped_missed`.
- Secrets follow the run pattern: real `pipeline_vars_secure` values are encrypted in MinIO under `{schedule_id}/input.json`, Postgres keeps `[MASKED]`, and editing with an unchanged `[MASKED]` value keeps the stored secret.
- Schedules can also be applied from a config-import document (`kind: ScheduledRun`, optionally carrying `id` to update in place) — see [samples/import.yaml](samples/import.yaml). `replace` mode deletes all schedules together with their stored secrets.
- `POST /schedules/{id}/trigger` fires once, ignoring cron and overlap policy; use it to verify a new schedule without waiting for its first occurrence.

## Design notes

- PDE `run` / `retry` do not archive; Jobs must archive after execute (including cancel) so cancelled runs stay retryable.
- Cancel = SIGINT + grace, then hard-delete - not bare `kubectl delete job` as the product path.
- Operator does not invent `IN_PROGRESS` / `started_at`; those come from PDE reports (`QUEUED` -> `NOT_STARTED` on Job create).
- Near-term tenancy: shared cluster per team; no hard multi-tenant isolation yet.
- Run detail omits `env_vars`; `pipeline_vars_secure` in Postgres/API is always masked (`[MASKED]`). Real values live only in encrypted MinIO input.
- Profile / run `env_vars` are not treated as secrets — use external-secrets mount for shared secret env; use `pipeline_vars_secure` for per-run secrets.
- Retry: decrypt parent `input.json`, apply `retry_vars`, store new child `input.json`; parent state ZIP fetched separately by entrypoint.
- Scheduled runs: the runner claims due rows with `FOR UPDATE SKIP LOCKED`, advances `next_fire_at` from *now* (so downtime skips missed fires instead of replaying them), then creates runs outside the lock. Firing is at-most-once: a crash between claim and run creation loses one firing. `next_fire_at` uses a short grace window so a normal poll is not mistaken for a missed fire.
