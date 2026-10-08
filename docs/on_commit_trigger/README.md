# Triggering PDE runs on commits - research

Research notes on starting PDE runs automatically when commits land in GitHub/GitLab repositories.

**Assumed deployment:** one PDE Operator instance reachable at a public HTTPS URL; all `/api/v1/*` behind the admin
Bearer token; runs and templates created through the existing REST API.

```text
developer -> git push -> GitHub / GitLab -> ??? -> PDE Operator -> Run -> PDE Job
```

The "???" is what this folder investigates.

---

## GitLab

### Webhook approach

**Idea:** the webhook body *is* the start request - `pipeline_data`, `pipeline_vars`, profile, flags - assembled by
GitLab from a fixed template plus payload placeholders. Requires **custom headers** and a **custom webhook template** on
the webhook (both GA since GitLab 17.0; 18.6+ recommended so interpolated values are JSON-escaped); authentication is
the operator's admin Bearer token in a custom header - GitLab's own secret token and signing token are not used.

#### Limits and delivery behavior of webhooks

| Topic               | Behavior                                                                                                                                                                                                |
|---------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Multi-branch pushes | If a single push touches more than 3 branches/tags in total (default `push_event_hooks_limit`), **no webhook fires at all** for that push.                                                              |
| Large pushes        | Pushes over 20 commits include only the newest 20 in `commits[]`; `total_commits_count` is accurate.                                                                                                    |
| Branch filter       | Per-webhook: all branches / wildcard (`main`, `release/*`) / regex (RE2). Filtering happens in GitLab, before delivery.                                                                                 |
| Timeout             | GitLab.com: **10 seconds** per request; max payload 25 MB; 100 webhooks per project (50 per group).                                                                                                     |
| Rate limit          | GitLab.com: per top-level namespace, shared by all its webhooks - 500 calls/min on Free, more on paid tiers. Exceeding it temporarily disables all namespace webhooks for the rest of the minute.       |
| Failure handling    | `4xx`/`5xx`/timeout count as failures. **4 consecutive failures → webhook temporarily disabled** (1 min, extending up to 24 h). **40 consecutive → permanently disabled** until a manual test succeeds. |
| Retries             | **No automatic re-delivery.** GitLab documents manual resend from *Recent events* only; treat failed deliveries as lost.                                                                                |
| Observability       | *Recent events* keeps 2 days of request/response details (status code, body, headers - custom header values masked).                                                                                    |

The auto-disable rules are the operational crux: **every non-2xx response counts, including `404` (profile missing)
and `422` (body does not match `CreateRunRequest`)**. A misconfigured webhook silently stops firing after four pushes to
the branch.

#### Configuration

1. *Settings → Webhooks → Add new webhook*.
2. **URL:** `https://<operator-host>/api/v1/runs`
3. **Trigger:** only **Push events** (leave *Tag push events* off).
4. **Branch filter:** the branch you care about - wildcard `main`, or regex for more.
5. **Custom headers:** `Authorization: Bearer <PDE_OPERATOR_API_ADMIN_TOKEN>`.
6. **Custom webhook template:**

   ```json
   {
     "profile_id": "default",
     "pipeline_data": "https://gitlab.com/quber-test/quber-pipeline/-/raw/main/pipeline_configs/samples/deploy.yaml",
     "pipeline_vars": "ENV_NAME=ENV_FROM_GITLAB_WEBHOOK;COMMIT_SHA={{checkout_sha}}\nGIT_REF={{ref}}\nGIT_BEFORE_SHA={{before}}\nGIT_USER={{user_username}}\nGIT_USER_NAME={{user_name}}\nGIT_USER_EMAIL={{user_email}}\nGIT_PROJECT_ID={{project_id}}\nGIT_PROJECT_NAME={{project.name}}\nGIT_PROJECT_PATH={{project.path_with_namespace}}\nGIT_PROJECT_URL={{project.web_url}}\nGIT_REPO_URL={{project.git_http_url}}\nGIT_DEFAULT_BRANCH={{project.default_branch}}\nGIT_REF_PROTECTED={{ref_protected}}\nGIT_TOTAL_COMMITS={{total_commits_count}}",
     "is_dry_run": true,
     "log_level": "INFO"
   }
   ```

   Escaping and content rules that matter:

    - `\n` inside the `pipeline_vars` string is a **literal backslash-n in the template** - JSON decodes it to a real
      newline in the received body, giving one `KEY=value` per dotenv line. (A real line break inside the template
      string would render invalid JSON.)
    - Keep placeholders quoted (`"{{ref}}"`). Quoted placeholders produce strings across GitLab 17.0–18.x; on
      18.8–18.10, **unquoted** placeholders cannot even be saved (fixed in 18.11).
    - Prefer fields that cannot contain newlines (SHAs, refs, users, project paths - exactly the set above). `message`
      is excluded on purpose: a value with line breaks would split `pipeline_vars` into garbage dotenv lines, and
      JSON-serialization (18.6+) does not prevent that - it only keeps the JSON body valid.
    - No secrets in the template: the body is stored in plain text in the webhook config (only headers and URL portions
      get masking), so `pipeline_vars_secure` values must not go here.
    - `pipeline_data` as a URL keeps the body small and needs no escaping; it can point at a file in this repository (
      GitLab raw URL), so a push updates the pipeline and triggers the run in one motion.
    - `is_dry_run: true` puts PDE in dry-run mode - handy while validating the trigger plumbing; flip to `false` for
      real runs.
7. SSL verification: keep enabled.

A native (template-less) delivery does **not** work here: GitLab's default push payload has no `pipeline_data`, and
`POST /api/v1/runs` requires it - the operator answers `422`, which counts toward GitLab's auto-disable rule (see the
limits table above).

The template above was validated locally on this branch: rendered with sample push values it parses as JSON and passes
`CreateRunRequest.model_validate`, with all 14 variables arriving as dotenv lines.

---

### Custom workflow approach

**Idea:** runs triggered from the repository's own GitLab CI workflow - a job posts the same `CreateRunRequest` to the
operator. Works outbound-only, so it also works when the operator is not publicly reachable. Triggers: push to
configured branches, or manually.

#### Configuration

1. Copy [.gitlab-ci.yml](.gitlab-ci.yml) to the target repository root.
2. Add repository CI/CD variables: `PDE_OPERATOR_URL`, `PDE_OPERATOR_TOKEN` (required); `GITLAB_TOKEN`.
3. Point the `PIPELINE_DATA` / `PIPELINE_VARS` input defaults at the repo's pipeline. Push triggers use the defaults;
   manual runs can override the inputs in the UI.
4. Runs default to `RUN_MODE: trigger` - start the run and exit. Pick `follow` in the manual run form to wait for
   completion, fetch the log / x_debug / report artifacts, and propagate the run status to the job. Push triggers
   always use the default.
5. Optional: `LIVE_LOGS: true` (follow runs) additionally streams flat log lines while polling. Either way the full
   log with collapsible sections is printed once at the end; the default `false` shows progress dots only.
6. Optional: set `PDE_TRIGGER_BRANCHES` (CI/CD variable, slash-enclosed regex) to change the push-trigger branches;
   the file default is `/^(main|master)$/`.

---

## GitHub

### Webhook approach

**Not possible in the same form as GitLab.** GitHub webhooks cannot set custom headers or a custom body: auth is
only a `secret` → `X-Hub-Signature-256` HMAC (the operator does not verify it), and the payload is the event JSON
as-is - so a webhook can never post a `CreateRunRequest` to `POST /api/v1/runs`. Alternatives: the workflow below,
or an external relay that verifies the signature and calls the operator.

### Custom workflow approach

**Idea:** same as GitLab - the repository's own CI (GitHub Actions) posts the `CreateRunRequest` to the operator;
outbound-only, so it also works when the operator is not publicly reachable. Two files:
[reusable-pipeline.yml](reusable-pipeline.yml) (the job) and [execute-pipeline.yml](execute-pipeline.yml)
(push + manual triggers with UI inputs).

#### Configuration

1. Copy [reusable-pipeline.yml](reusable-pipeline.yml) and [execute-pipeline.yml](execute-pipeline.yml) into
   `.github/workflows/` of the target repository (keep the names - the trigger references the reusable by path).
2. Add repository secrets: `PDE_OPERATOR_URL`, `PDE_OPERATOR_TOKEN`.
3. Point the `pipeline_data` / `pipeline_vars` input defaults at the repo's pipeline. Push runs use the defaults;
   manual runs can override the inputs.
4. Edit the `push` → `branches` list in `execute-pipeline.yml` for the repo's branches - Actions cannot read
   variables from `on:`.
5. Runs default to `run_mode: trigger` - start the run and exit. Pick `follow` in the manual run form to wait for
   completion, fetch the log / x_debug / report artifacts, and propagate the run status to the job. Push runs
   always use the default.
6. Optional: `live_logs: true` (follow runs) additionally streams flat log lines while polling. Either way the full
   log is printed once at the end; the default `false` shows progress dots only.
