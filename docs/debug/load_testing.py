#!/usr/bin/env python3
"""Fire N create-run-from-template requests against a pde-operator instance."""

from __future__ import annotations

import json
import random
import sys
import urllib.error
import urllib.request
from datetime import datetime

OPERATOR_BASE = "http://192.168.0.201:8000"
ADMIN_TOKEN = "pde-stable-admin-token"
RUN_COUNT = 10
DECLARATIVE_TEMPLATES_ENABLED = True


def api_url(path: str) -> str:
    return OPERATOR_BASE.rstrip("/") + "/api/v1" + path


def request_json(method: str, path: str, body: dict | None = None) -> dict | list:
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        api_url(path),
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {ADMIN_TOKEN}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"{method} {path} failed: HTTP {exc.code} {detail}") from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f"{method} {path} failed: {exc.reason}") from exc
    return json.loads(raw) if raw else {}


def _random_string_value(_: dict) -> str:
    return f"loadtest-{random.randint(0, 99999):05d}"


def _random_field_value(field: dict) -> bool | int | str:
    field_type = field.get("field_type") or "string"
    if field_type == "checkbox":
        return random.choice([True, False])
    if field_type == "select":
        options = [opt for opt in (field.get("options") or []) if opt != ""]
        if options:
            return random.choice(options)
        return _random_string_value(field)
    return _random_string_value(field)


def build_declarative_values(spec: dict) -> dict[str, bool | int | str]:
    values: dict[str, bool | int | str] = {}
    for field in spec.get("fields", []):
        name = field.get("name")
        if not name:
            continue
        default = field.get("value")
        if default is not None and default != "":
            values[name] = default
        elif field.get("required"):
            values[name] = _random_field_value(field)
    return values


def with_env_name(pipeline_vars: str | None, env_name: str) -> str:
    lines = [line for line in (pipeline_vars or "").splitlines() if line.strip()]
    kept = [line for line in lines if not line.strip().startswith("ENV_NAME=")]
    kept.append(f"ENV_NAME={env_name}")
    return "\n".join(kept)


def list_templates() -> list[dict]:
    payload = request_json("GET", "/run-templates?offset=0&limit=500")
    items = payload.get("items") if isinstance(payload, dict) else None
    if not items:
        raise SystemExit("No run templates available")
    if DECLARATIVE_TEMPLATES_ENABLED:
        selected = items
    else:
        selected = [item for item in items if item.get("template_kind", "simple") == "simple"]
    if not selected:
        raise SystemExit("No run templates available")
    details = []
    for item in selected:
        template = request_json("GET", f"/run-templates/{item['id']}")
        details.append(template)
        kind = template.get("template_kind", "simple")
        print(f"Prefetched template {template.get('name')} ({template.get('id')}) kind={kind}")
    return details


def create_run(template: dict) -> dict:
    template_id = template["id"]
    if template.get("template_kind") == "declarative":
        spec = template.get("declarative_spec")
        if not spec:
            raise SystemExit(f"Declarative template {template_id} missing declarative_spec")
        values = build_declarative_values(spec)
        return request_json("POST", f"/run-templates/{template_id}/declarative-runs", {"values": values})
    else:
        env_name = f"cloud-env-{random.randint(0, 99):02d}"
        body = {"pipeline_vars": with_env_name(template.get("pipeline_vars"), env_name)}
        return request_json("POST", f"/run-templates/{template_id}/runs", body)


def main() -> None:
    templates = list_templates()
    print(f"Loaded {len(templates)} template(s); creating {RUN_COUNT} run(s)")
    ok = 0
    for i in range(1, RUN_COUNT + 1):
        template = random.choice(templates)
        run = create_run(template)
        ok += 1
        print(f"[{i}/{RUN_COUNT}] {run.get('id')} status={run.get('status')} template={template.get('name')}")
    print(f"Done: {ok}/{RUN_COUNT} created")
    print(f"Finished at {datetime.now().isoformat(timespec='seconds')}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
