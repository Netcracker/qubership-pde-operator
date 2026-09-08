"""MCP server instructions and shared agent-facing copy for PDE Operator."""
MCP_SERVER_NAME = "PDE Operator"

# Surfaced to clients on initialize (same idea as APIHUB WithInstructions).
MCP_INSTRUCTIONS = """\
You are talking to the PDE Operator MCP server (agent API v0.2).

## What PDE is
PDE (Pipelines Declarative Executor / qubership-pipelines-declarative-executor) is the execution
engine. It runs declarative pipeline YAML: stages, scripts, artifacts, retries. PDE itself does not
expose this MCP — it runs inside Kubernetes Jobs.

## What PDE Operator is
PDE Operator is a Kubernetes control plane *around* PDE ("PDE as a Service"):
- Accepts run requests (CI, UI, Argo CD extension, or this MCP)
- Queues work, creates isolated PDE Jobs, tracks lifecycle in PostgreSQL
- Stores console log / state archive / debug zip in MinIO
- Exposes cancel (SIGINT + grace) and smart-retry (new run from archived state)
- Catalog of run templates (named/tagged presets) for starting common pipelines

Primary consumers are CI workflows calling REST. This MCP is the same admin API surface for agents.

## Run lifecycle (statuses)
QUEUED → NOT_STARTED → IN_PROGRESS → SUCCESS | FAILED | CANCELLED

- QUEUED: accepted, waiting for a Job slot
- NOT_STARTED: Job created; PDE has not reported progress yet
- IN_PROGRESS: PDE status deliveries are flowing
- SUCCESS / FAILED / CANCELLED: terminal

Operator does not invent IN_PROGRESS/started_at; those come from PDE status deliveries.
Cancel is cooperative: request cancel on a non-terminal run, then poll until CANCELLED (or FAILED).
Retry only works for FAILED or CANCELLED runs that have archived state in MinIO; it creates a *new*
run (retry_of_run_id points at the parent).

## How to use the tools
1. Context: read resources `pde://lifecycle`, `pde://pipeline-inputs`, `pde://profiles`,
   and `pde://run-templates` when unsure
2. Discover templates: pde_list_run_templates (q/tag) → pde_get_run_template if needed
3. Discover runs: pde_list_runs (filter by status/profile) → pde_get_run for detail/progress_json
4. Diagnose: pde_get_run_log (tail) after failure/cancel; use artifact report for full pipeline state
5. Start work:
   - Prefer pde_create_run_from_template when the user names a catalog entry or tags
   - Or pde_create_run with pipeline_data (required). Prefer dry-run first if unsure.
6. Wait: poll pde_get_run until status is terminal; do not spam create
7. Stop: pde_cancel_run on QUEUED / NOT_STARTED / IN_PROGRESS
8. Recover: pde_retry_run on FAILED / CANCELLED when state was archived

## Resources (read on demand)
- pde://lifecycle — statuses, cancel/retry rules (markdown)
- pde://pipeline-inputs — pipeline_data / pipeline_vars formats and examples (markdown)
- pde://profiles — live list of profile ids and images from this operator (JSON)
- pde://run-templates — how to find and start from catalog templates (markdown)

## pipeline_data / pipeline_vars
See resource pde://pipeline-inputs. Short form:
- pipeline_data: one or more PDE pipeline sources, separated by `;`
- pipeline_vars: optional KEY=VALUE lines (newline-separated)
- pipeline_vars_secure: optional KEY=VALUE secrets for PDE (create only; not echoed by pde_get_run)
- profile_id: usually `default`; confirm via pde://profiles
- is_dry_run / log_level / pde_image: as documented on pde_create_run

## Response tips
- Prefer short run UUIDs in replies; quote full UUIDs when calling tools.
- Summarize status + finished_at + progress_json/log; do not dump entire logs unless asked.
- If a tool errors (not found, not cancellable, not retriable, artifacts disabled), explain the
  precondition and suggest the next tool.
- Do not echo pipeline_vars_secure from templates back to the user unless they ask.
"""
