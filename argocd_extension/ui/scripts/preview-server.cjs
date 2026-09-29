"use strict";

// Serves dist/standalone behind a stub /api/v1 so the UI can be opened without a cluster.
// Usage: npm run preview [-- --port 4173]

const crypto = require("crypto");
const http = require("http");
const fs = require("fs");
const path = require("path");

const DIST = path.resolve(__dirname, "..", "dist", "standalone");
const DEFAULT_PORT = 4173;
const ARTIFACT_KINDS = ["log", "report", "state", "x_debug"];

const HOUR = 60 * 60 * 1000;

function iso(offsetMs) {
  return new Date(Date.now() + offsetMs).toISOString();
}

const RICH_RUN = {
  id: "11111111-1111-4111-8111-111111111111",
  name: "nightly-deploy",
  status: "FAILED",
  finish_code: "PYTHON_ERROR",
  finish_message: "stage 'deploy' failed: connection refused",
  profile_id: "default",
  pde_image: "ghcr.io/netcracker/qubership-pde:0.0.2",
  created_at: "2026-09-29T07:12:03Z",
  started_at: "2026-09-29T07:12:09Z",
  finished_at: "2026-09-29T07:19:41Z",
  is_dry_run: false,
  log_level: "INFO",
  progress_json: { stagesTotal: 4, stagesCompleted: 3 },
  created_from_template_id: "22222222-2222-4222-8222-222222222222",
  created_from_template_name: "Nightly deploy",
  retry_of_run_id: "33333333-3333-4333-8333-333333333333",
  triggered_by: null,
  pipeline_data: [
    "https://git.example.com/ci/pipelines.git//pipelines/nightly-deploy.yaml",
    "https://git.example.com/ci/pipelines.git//pipelines/stages/deploy.yaml",
    "https://git.example.com/ci/pipelines.git//pipelines/stages/verify.yaml?ref=release-2026.09",
    "extra-local-pipeline.yaml",
  ].join("\n"),
  pipeline_vars: [
    "# deploy target",
    "ENVIRONMENT=dev",
    "NAMESPACE=pde-system",
    "RELEASE_NAME=qubership-pde-operator",
    "CLUSTER=dev-eu-west-1-cluster-with-a-fairly-long-name",
  ].join("\n"),
  pipeline_vars_secure: ["API_TOKEN=[MASKED]", "REGISTRY_PASSWORD=[MASKED]"].join("\n"),
  retry_vars: ["ENVIRONMENT=dev", "DEBUG=true"].join("\n"),
};

const SCHEDULE_ID = "99999999-9999-4999-8999-999999999999";

const SCHEDULED_RUN = {
  ...RICH_RUN,
  id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
  name: "nightly-deploy (scheduled)",
  status: "SUCCESS",
  finish_code: null,
  finish_message: null,
  retry_of_run_id: null,
  triggered_by: `schedule:${SCHEDULE_ID}`,
  progress_json: { stagesTotal: 4, stagesCompleted: 4 },
  created_at: iso(-21 * HOUR),
  started_at: iso(-21 * HOUR),
  finished_at: iso(-21 * HOUR + 8 * 60 * 1000),
};

const EMPTY_RUN = {
  ...RICH_RUN,
  id: "44444444-4444-4444-8444-444444444444",
  name: null,
  status: "SUCCEEDED",
  finish_code: null,
  finish_message: null,
  created_from_template_id: null,
  created_from_template_name: null,
  retry_of_run_id: null,
  progress_json: null,
  pipeline_data: "",
  pipeline_vars: null,
  pipeline_vars_secure: null,
  retry_vars: null,
};

const RUNS = [RICH_RUN, SCHEDULED_RUN, EMPTY_RUN];

const SIMPLE_TEMPLATE = {
  id: "77777777-7777-4777-8777-777777777777",
  name: "Dev Deploy",
  description: "Example deploy pipeline.",
  tags: ["demo", "deploy"],
  template_kind: "simple",
  profile_id: "default",
  pipeline_data: "https://git.example.com/ci/pipelines.git//pipelines/deploy.yaml",
  pipeline_vars: "ENVIRONMENT=dev",
  pipeline_vars_secure: "API_TOKEN=secret",
  is_dry_run: false,
  log_level: "INFO",
  env_vars: null,
  pde_image: null,
  declarative_spec: null,
  created_at: iso(-48 * HOUR),
  updated_at: iso(-24 * HOUR),
};

const DECLARATIVE_TEMPLATE = {
  id: "88888888-8888-4888-8888-888888888888",
  name: "Declarative Deploy",
  description: "Declarative template with a few fields.",
  tags: ["demo", "declarative"],
  template_kind: "declarative",
  profile_id: "default",
  pipeline_data: "",
  pipeline_vars: null,
  pipeline_vars_secure: null,
  is_dry_run: false,
  log_level: "INFO",
  env_vars: null,
  pde_image: null,
  declarative_spec: {
    name: "Declarative Deploy",
    fields: [
      { name: "ENVIRONMENT", field_type: "string", value: "dev", bind_to: "pipeline_var", label: "Environment" },
      {
        name: "API_TOKEN",
        field_type: "string",
        secure: true,
        required: true,
        bind_to: "pipeline_var",
        label: "API token",
      },
      { name: "DRY_RUN", field_type: "checkbox", value: false, bind_to: "is_dry_run", label: "Dry run" },
    ],
  },
  created_at: iso(-48 * HOUR),
  updated_at: iso(-24 * HOUR),
};

const TEMPLATES = [SIMPLE_TEMPLATE, DECLARATIVE_TEMPLATE];

const SCHEDULES = [
  {
    id: SCHEDULE_ID,
    name: "Nightly deploy",
    description: "Deploys dev every night at 02:30 Berlin time.",
    cron_expression: "30 2 * * *",
    timezone: "Europe/Berlin",
    enabled: true,
    overlap_policy: "skip",
    profile_id: "default",
    created_from_template_id: SIMPLE_TEMPLATE.id,
    next_fire_at: iso(3 * HOUR),
    last_fire_at: SCHEDULED_RUN.created_at,
    last_fire_status: "success",
    last_fire_error: null,
    last_run_id: SCHEDULED_RUN.id,
    pipeline_data: SIMPLE_TEMPLATE.pipeline_data,
    pipeline_vars: SIMPLE_TEMPLATE.pipeline_vars,
    pipeline_vars_secure: "API_TOKEN=[MASKED]",
    is_dry_run: false,
    log_level: "INFO",
    env_vars: null,
    pde_image: null,
    created_at: iso(-72 * HOUR),
    updated_at: iso(-24 * HOUR),
  },
  {
    id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
    name: "Hourly cleanup",
    description: "Paused until the next release.",
    cron_expression: "0 * * * *",
    timezone: "UTC",
    enabled: false,
    overlap_policy: "allow",
    profile_id: "default",
    created_from_template_id: null,
    next_fire_at: null,
    last_fire_at: iso(-30 * HOUR),
    last_fire_status: "skipped_overlap",
    last_fire_error: null,
    last_run_id: null,
    pipeline_data: "https://git.example.com/ci/pipelines.git//pipelines/cleanup.yaml",
    pipeline_vars: null,
    pipeline_vars_secure: null,
    is_dry_run: false,
    log_level: "INFO",
    env_vars: null,
    pde_image: null,
    created_at: iso(-96 * HOUR),
    updated_at: iso(-30 * HOUR),
  },
];

const TIMEZONES = ["UTC", "Europe/Berlin", "Europe/London", "Europe/Moscow", "America/New_York", "Asia/Tokyo"];

const MIME = {
  ".html": "text/html",
  ".js": "text/javascript",
  ".css": "text/css",
  ".svg": "image/svg+xml",
  ".woff2": "font/woff2",
  ".ttf": "font/ttf",
  ".txt": "text/plain",
};

function readPort() {
  const flagIndex = process.argv.indexOf("--port");
  const raw = (flagIndex > -1 ? process.argv[flagIndex + 1] : undefined) ?? process.env.PORT ?? DEFAULT_PORT;
  const port = Number(raw);
  if (!Number.isInteger(port) || port < 1 || port > 65535) {
    console.error(`Invalid port: ${raw}`);
    process.exit(1);
  }
  return port;
}

function json(res, status, body) {
  res.writeHead(status, { "Content-Type": "application/json" });
  res.end(JSON.stringify(body));
}

function previewResponse(body) {
  const expression = String(body?.cron_expression || "").trim();
  const fields = expression.split(/\s+/).filter(Boolean);
  if (fields.length < 5 || fields.length > 6) {
    return { status: 400, body: { detail: `Cron expression must have 5 or 6 fields, got ${fields.length}: '${expression}'` } };
  }
  const secondsField = fields.length === 6 ? fields[0] : null;
  if (secondsField && /^\*\/\d+$/.test(secondsField) && Number(secondsField.slice(2)) < 60) {
    return { status: 400, body: { detail: `Cron expression fires every ${secondsField.slice(2)}s, which is below the minimum interval of 60s` } };
  }
  const minute = Number(fields[fields.length === 6 ? 1 : 0]);
  const hour = Number(fields[fields.length === 6 ? 2 : 1]);
  const base = new Date();
  const first = new Date(base);
  first.setSeconds(0, 0);
  if (Number.isInteger(hour)) first.setHours(hour);
  if (Number.isInteger(minute)) {
    first.setMinutes(minute);
    if (first <= base) first.setDate(first.getDate() + 1);
  } else {
    first.setMinutes(first.getMinutes() + 5);
  }
  const stepMs = Number.isInteger(hour) ? 24 * HOUR : HOUR;
  return { status: 200, body: { next_fire_times: [0, 1, 2].map((i) => new Date(first.getTime() + i * stepMs).toISOString()) } };
}

function apiResponse(method, pathname, { body, search }) {
  const runMatch = /^\/api\/v1\/runs\/([^/]+)$/.exec(pathname);
  const runAction = /^\/api\/v1\/runs\/([^/]+)\/(cancel|retry)$/.exec(pathname);
  const templateMatch = /^\/api\/v1\/run-templates\/([^/]+)$/.exec(pathname);
  const scheduleMatch = /^\/api\/v1\/schedules\/([^/]+)$/.exec(pathname);
  const scheduleAction = /^\/api\/v1\/schedules\/([^/]+)\/(trigger|enable|disable)$/.exec(pathname);

  if (pathname === "/api/v1/capabilities") return { status: 200, body: { canWrite: true, username: "preview" } };

  if (pathname === "/api/v1/runs" && method === "GET") {
    const triggeredBy = search.get("triggered_by");
    const items = triggeredBy ? RUNS.filter((run) => run.triggered_by === triggeredBy) : RUNS;
    return { status: 200, body: { items, total: items.length, offset: 0, limit: 20 } };
  }
  if (pathname === "/api/v1/runs" && method === "POST") {
    return {
      status: 200,
      body: {
        id: "55555555-5555-4555-8555-555555555555",
        status: "QUEUED",
        execution_url: "/ui/runs/55555555-5555-4555-8555-555555555555/info",
        created_at: new Date().toISOString(),
      },
    };
  }
  if (runMatch && method === "GET") {
    const run = RUNS.find((r) => r.id === runMatch[1]);
    return run ? { status: 200, body: run } : { status: 404, body: { detail: "run not found" } };
  }
  if (runAction) {
    const run = RUNS.find((r) => r.id === runAction[1]);
    if (!run) return { status: 404, body: { detail: "run not found" } };
    const status = runAction[2] === "cancel" ? "CANCEL_REQUESTED" : "QUEUED";
    return { status: 200, body: { ...run, id: runAction[2] === "retry" ? crypto.randomUUID() : run.id, status } };
  }
  if (pathname === "/api/v1/profiles") {
    return { status: 200, body: { items: [{ id: "default", pde_image: RICH_RUN.pde_image }], total: 1 } };
  }
  if (pathname === "/api/v1/run-templates" && method === "GET") {
    return { status: 200, body: { items: TEMPLATES, total: TEMPLATES.length, offset: 0, limit: 20 } };
  }
  if (templateMatch && method === "GET") {
    const template = TEMPLATES.find((t) => t.id === templateMatch[1]);
    return template ? { status: 200, body: template } : { status: 404, body: { detail: "template not found" } };
  }
  if (pathname === "/api/v1/schedules/timezones") return { status: 200, body: { timezones: TIMEZONES } };
  if (pathname === "/api/v1/schedules/preview") return previewResponse(body);
  if (pathname === "/api/v1/schedules" && method === "GET") {
    return { status: 200, body: { items: SCHEDULES, total: SCHEDULES.length, offset: 0, limit: 20 } };
  }
  if (pathname === "/api/v1/schedules" && method === "POST") {
    const created = {
      ...SCHEDULES[0],
      ...body,
      id: crypto.randomUUID(),
      pipeline_vars_secure: body?.pipeline_vars_secure ? "API_TOKEN=[MASKED]" : null,
      next_fire_at: body?.enabled === false ? null : iso(HOUR),
      last_fire_at: null,
      last_fire_status: null,
      last_run_id: null,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
    SCHEDULES.push(created);
    return { status: 201, body: created };
  }
  if (scheduleMatch && method === "GET") {
    const schedule = SCHEDULES.find((s) => s.id === scheduleMatch[1]);
    return schedule ? { status: 200, body: schedule } : { status: 404, body: { detail: "schedule not found" } };
  }
  if (scheduleMatch && method === "PUT") {
    const schedule = SCHEDULES.find((s) => s.id === scheduleMatch[1]);
    if (!schedule) return { status: 404, body: { detail: "schedule not found" } };
    Object.assign(schedule, body, { id: schedule.id, updated_at: new Date().toISOString() });
    return { status: 200, body: schedule };
  }
  if (scheduleMatch && method === "DELETE") {
    const index = SCHEDULES.findIndex((s) => s.id === scheduleMatch[1]);
    if (index < 0) return { status: 404, body: { detail: "schedule not found" } };
    SCHEDULES.splice(index, 1);
    return { status: 204, body: null };
  }
  if (scheduleAction) {
    const schedule = SCHEDULES.find((s) => s.id === scheduleAction[1]);
    if (!schedule) return { status: 404, body: { detail: "schedule not found" } };
    if (scheduleAction[2] === "trigger") {
      return {
        status: 201,
        body: { id: crypto.randomUUID(), status: "QUEUED", execution_url: null, created_at: new Date().toISOString() },
      };
    }
    schedule.enabled = scheduleAction[2] === "enable";
    schedule.next_fire_at = schedule.enabled ? iso(HOUR) : null;
    return { status: 200, body: schedule };
  }

  return { status: 404, body: { detail: "preview stub has no route for this request" } };
}

function serveDist(res, pathname) {
  const rel = (pathname.startsWith("/ui/") ? pathname.slice(3) : pathname).replace(/^[/\\]+/, "");
  const requested = path.resolve(DIST, rel);
  // Anything that escapes dist/ (encoded traversal, stray separators) falls back to the SPA shell.
  const inDist = requested === DIST || requested.startsWith(DIST + path.sep);
  const file = inDist && fs.existsSync(requested) && fs.statSync(requested).isFile() ? requested : path.join(DIST, "index.html");
  if (!fs.existsSync(file)) {
    res.writeHead(500, { "Content-Type": "text/plain" });
    res.end("dist/standalone is missing - run `npm run build:standalone` first");
    return;
  }
  res.writeHead(200, { "Content-Type": MIME[path.extname(file).toLowerCase()] || "application/octet-stream" });
  fs.createReadStream(file).pipe(res);
}

function readBody(req) {
  return new Promise((resolve) => {
    const chunks = [];
    req.on("data", (chunk) => chunks.push(chunk));
    req.on("end", () => {
      const text = Buffer.concat(chunks).toString("utf-8");
      try {
        resolve(text ? JSON.parse(text) : null);
      } catch {
        resolve(null);
      }
    });
  });
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, "http://localhost");
  const pathname = decodeURIComponent(url.pathname);
  const method = req.method || "GET";

  if (!pathname.startsWith("/api/")) {
    serveDist(res, pathname);
    return;
  }

  // Artifact downloads are what the Logs/Viewer tabs and export buttons fetch.
  if (ARTIFACT_KINDS.some((kind) => pathname.endsWith(`/artifacts/${kind}`))) {
    json(res, 404, { detail: "artifacts are not stubbed in preview" });
    return;
  }

  const body = method === "POST" || method === "PUT" ? await readBody(req) : null;
  const { status, body: responseBody } = apiResponse(method, pathname, { body, search: url.searchParams });
  if (status === 204 || responseBody === null) {
    res.writeHead(status);
    res.end();
    return;
  }
  json(res, status, responseBody);
});

const port = readPort();
server.listen(port, () => {
  console.log(`PDE UI preview: http://localhost:${port}/ui/catalog`);
  console.log(`  run detail : http://localhost:${port}/ui/runs/${RICH_RUN.id}/info`);
  console.log(`  empty run  : http://localhost:${port}/ui/runs/${EMPTY_RUN.id}/info`);
  console.log(`  run list   : http://localhost:${port}/ui/runs`);
  console.log(`  schedules  : http://localhost:${port}/ui/schedules`);
});
