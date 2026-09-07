"""Static MCP resource bodies and URI constants."""

URI_LIFECYCLE = "pde://lifecycle"
URI_PIPELINE_INPUTS = "pde://pipeline-inputs"
URI_PROFILES = "pde://profiles"
URI_RUN_TEMPLATES = "pde://run-templates"

LIFECYCLE_MARKDOWN = """\
# PDE Operator — run lifecycle

## Status flow

```
QUEUED → NOT_STARTED → IN_PROGRESS → SUCCESS | FAILED | CANCELLED
```

| Status | Meaning |
|--------|---------|
| QUEUED | Accepted; waiting for a Job slot |
| NOT_STARTED | Kubernetes Job created; PDE has not reported progress yet |
| IN_PROGRESS | PDE status deliveries are flowing (`started_at` / progress from deliveries) |
| SUCCESS | Terminal — completed successfully |
| FAILED | Terminal — PDE or Job failed |
| CANCELLED | Terminal — cooperative cancel finished |

The operator does **not** invent `IN_PROGRESS` / `started_at`; those come from PDE status deliveries.
Admission only moves `QUEUED` → `NOT_STARTED` when a Job is created.

## Cancel

- Tool: `pde_cancel_run` on **non-terminal** runs (`QUEUED`, `NOT_STARTED`, `IN_PROGRESS`)
- Cooperative: SIGINT into the Job wrapper, then grace; poll `pde_get_run` until `CANCELLED` (or `FAILED`)
- Not instant — do not assume status flips on the cancel response alone

## Retry (smart-retry)

- Tool: `pde_retry_run` only for **FAILED** or **CANCELLED** parents that have archived state in MinIO
- Creates a **new** run; `retry_of_run_id` on the child points at the parent
- Parent `env_vars` are reused when not overridden

## Diagnose

1. `pde_get_run` — status, timings, `progress_json`, `state_location`, `cancel_requested_at`
2. `pde_get_run_log` — console log (live during run via deliveries; final from archive)
3. Prompt `investigate_run` — guided checklist for one UUID
"""

PIPELINE_INPUTS_MARKDOWN = """\
# PDE Operator — pipeline inputs for `pde_create_run`

## pipeline_data (required)

One or more PDE pipeline sources, separated by `;` (URLs or paths PDE understands).

Example (lab-style, two YAMLs):

```
https://raw.githubusercontent.com/Netcracker/qubership-pipelines-declarative-executor/refs/heads/sample_pipelines/tests/pipeline_configs/samples/sample_long_pipeline.yaml;https://raw.githubusercontent.com/Netcracker/qubership-pipelines-declarative-executor/refs/heads/main/tests/pipeline_configs/debug_logs/pipeline_complex.yaml;
```

## pipeline_vars (optional)

Plain `KEY=VALUE` lines, newline-separated, passed to PDE as `--pipeline_vars`.

Example:

```
SLEEP_TIME=10
SLEEP_DURATION=2
PIPELINE_DATA_DIR=https://raw.githubusercontent.com/Netcracker/qubership-pipelines-declarative-executor/refs/heads/main/tests/pipeline_configs/debug_logs;
```

## pipeline_vars_secure (optional)

Same `KEY=VALUE` line format as `pipeline_vars`, passed to PDE as `--pipeline_vars_secure`.
Use for secrets / sensitive values. Prefer this over putting secrets in `pipeline_vars`.

Notes:
- Accepted on `pde_create_run` and stored for the Job
- **Not** returned by `pde_get_run` / list (detail API omits secure vars)
- Avoid echoing secrets back to the user in chat when summarizing

## profile_id

Cluster execution profile (PDE image + default env). Usually `default`.
Read resource `pde://profiles` for ids that exist in this deployment before inventing a name.

## is_dry_run

If true, ask PDE to dry-run when the pipeline supports it — prefer for experiments.

## log_level

PDE verbosity, e.g. `INFO` or `DEBUG`.

## pde_image

Optional per-run image override; omit to use the profile's image.

## After create

Poll `pde_get_run` until a terminal status. Do not spam duplicate creates for the same intent.
"""

RUN_TEMPLATES_MARKDOWN = """\
# PDE Operator — run templates (catalog)

Run templates are named, tagged presets of create-run settings (profile, pipeline_data,
pipeline_vars, secure vars, dry-run, log level, optional env/image overrides).

## Agent workflow

1. `pde_list_run_templates` with optional `q` / `tag` to find a template
2. Optionally `pde_get_run_template` for full body
3. Prefer `pde_create_run_from_template` to start a run (sets `created_from_template_id`)
4. Poll `pde_get_run` until terminal

If the template's `profile_id` was deleted, the operator remaps to `default` when creating
the run (as long as the default profile exists).

## Overrides

`pde_create_run_from_template` accepts optional field overrides; unset fields use the template.
"""
