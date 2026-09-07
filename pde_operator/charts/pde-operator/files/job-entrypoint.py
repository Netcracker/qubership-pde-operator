#!/usr/bin/env python3
"""PDE Job wrapper: optional mounted secrets, run/retry PDE, archive artifacts, upload to operator."""

from __future__ import annotations

import json
import os
import pathlib
import shutil
import signal
import subprocess
import sys
import urllib.error
import urllib.request
import uuid

import yaml

WS = pathlib.Path("/workspace")
PIPELINE_DIR = WS / "PIPELINE_DIR"
PIPELINE_DIR_ZIP = WS / "PIPELINE_DIR.zip"
CONSOLE_LOG = WS / "console.log"
X_DEBUG_DIR = PIPELINE_DIR / "x_debug"
X_DEBUG_ZIP = WS / "x_debug.zip"
X_DEBUG_STAGING = WS / "x_debug"
REPORT_JSON = PIPELINE_DIR / "pipeline_state" / "pipeline_report.json"
REPORT_JSON_STAGING = WS / "pipeline_report.json"

ARTIFACT_CANDIDATES: list[tuple[str, pathlib.Path]] = [
    ("state", PIPELINE_DIR_ZIP),
    ("log", CONSOLE_LOG),
    ("x_debug", X_DEBUG_ZIP),
    ("report", REPORT_JSON_STAGING),
]

MOUNTED_SECRETS_ATLAS_ENV = "CUSTOM_GLOBAL_CONFIG_MOUNTED_SECRETS"
EXTERNAL_SECRETS_MOUNT_PATH_ENV = "PDE_OPERATOR_EXTERNAL_SECRETS_MOUNT_PATH"

_child: subprocess.Popen[bytes] | None = None
_cancelled = False
_run_input: dict[str, object] | None = None


def _pde_cli(*args: str) -> list[str]:
    return [sys.executable, "-m", "pipelines_declarative_executor", *args]


def _operator_request(
    url: str,
    *,
    method: str = "GET",
    data: bytes | None = None,
    content_type: str | None = None,
) -> bytes:
    headers = {"Authorization": f"Bearer {os.environ.get('PDE_OPERATOR_TOKEN', '')}"}
    if content_type:
        headers["Content-Type"] = content_type
    request = urllib.request.Request(url, data=data, method=method, headers=headers)
    with urllib.request.urlopen(request) as response:
        return response.read()


def _external_secrets_mount() -> pathlib.Path:
    return pathlib.Path(os.environ.get(EXTERNAL_SECRETS_MOUNT_PATH_ENV, "/var/run/secrets/pde-external"))


def _read_mounted_secrets(mount: pathlib.Path) -> dict[str, str]:
    if not mount.is_dir():
        return {}
    secrets: dict[str, str] = {}
    for path in sorted(mount.iterdir()):
        if not path.is_file() or path.name.startswith(".."):
            continue
        secrets[path.name] = path.read_text(encoding="utf-8")
    return secrets


def export_mounted_secret_env() -> None:
    for key, value in _read_mounted_secrets(_external_secrets_mount()).items():
        os.environ[key] = value


def _sops_encrypt_yaml(plain_yaml: str, *, age_key: str, age_recipients: str) -> str:
    env = os.environ.copy()
    env["SOPS_AGE_KEY"] = age_key
    env["SOPS_AGE_RECIPIENTS"] = age_recipients
    try:
        completed = subprocess.run(
            ["sops", "--encrypt", "--input-type", "yaml", "--output-type", "yaml", "/dev/stdin"],
            input=plain_yaml, capture_output=True, text=True, env=env, check=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("sops executable not found in job container") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()
        raise RuntimeError(detail or "sops encrypt failed") from exc
    encrypted = completed.stdout.strip()
    if not encrypted:
        raise RuntimeError("sops encrypt produced empty output")
    return encrypted


def export_mounted_secrets_atlas_config() -> None:
    mount = _external_secrets_mount()
    secrets = _read_mounted_secrets(mount)
    if not secrets:
        return

    age_key = secrets.get("SOPS_AGE_KEY", "").strip() or None
    age_recipients = secrets.get("SOPS_AGE_RECIPIENTS", "").strip() or None
    if not age_key or not age_recipients:
        print(
            "warning: mounted external secrets found but SOPS_AGE_KEY and SOPS_AGE_RECIPIENTS are missing; "
            "skipping CUSTOM_GLOBAL_CONFIG_MOUNTED_SECRETS",
            file=sys.stderr,
        )
        return

    config = {"kind": "AtlasConfig", "apiVersion": "v1", **secrets}
    plain_yaml = yaml.safe_dump(config, default_flow_style=False, sort_keys=False)
    try:
        encrypted_yaml = _sops_encrypt_yaml(plain_yaml, age_key=age_key, age_recipients=age_recipients)
    except RuntimeError as exc:
        print(f"warning: failed to SOPS-encrypt mounted secrets AtlasConfig: {exc}", file=sys.stderr)
        return
    os.environ[MOUNTED_SECRETS_ATLAS_ENV] = encrypted_yaml


def stage_x_debug() -> None:
    if not X_DEBUG_DIR.is_dir():
        return
    if X_DEBUG_STAGING.exists():
        shutil.rmtree(X_DEBUG_STAGING)
    X_DEBUG_DIR.rename(X_DEBUG_STAGING)


def stage_pipeline_reports() -> None:
    if REPORT_JSON.is_file():
        REPORT_JSON.rename(REPORT_JSON_STAGING)
    # we can remove nested reports to save space, but it will harm retry visualization:
    # if PIPELINE_DIR.is_dir():
    #     for nested in PIPELINE_DIR.rglob("pipeline_state/pipeline_report.json"):
    #         if nested.is_file():
    #             nested.unlink()


def archive_once() -> None:
    subprocess.run(_pde_cli("archive", f"--pipeline_dir={PIPELINE_DIR}", f"--target_path={PIPELINE_DIR_ZIP}"), check=False)


def zip_x_debug() -> None:
    if not X_DEBUG_STAGING.is_dir():
        print(f"x_debug dir missing: {X_DEBUG_STAGING}", file=sys.stderr)
        return
    shutil.make_archive(str(X_DEBUG_ZIP.with_suffix("")), "zip", str(X_DEBUG_STAGING))


def _multipart_body(files: list[tuple[str, pathlib.Path]]) -> tuple[bytes, str]:
    boundary = uuid.uuid4().hex
    chunks: list[bytes] = []
    for field_name, path in files:
        chunks.append(f"--{boundary}\r\n".encode())
        chunks.append(f'Content-Disposition: form-data; name="{field_name}"; filename="{path.name}"\r\n\r\n'.encode())
        chunks.append(path.read_bytes())
        chunks.append(b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode())
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def upload_artifacts() -> int:
    url = os.environ.get("PDE_OPERATOR_ARTIFACTS_URL")
    if not url:
        print("PDE_OPERATOR_ARTIFACTS_URL is not set", file=sys.stderr)
        return 1

    files = [(name, path) for name, path in ARTIFACT_CANDIDATES if path.is_file()]
    if not PIPELINE_DIR_ZIP.is_file():
        print(f"state zip missing: {PIPELINE_DIR_ZIP}", file=sys.stderr)
    if not files:
        print("no artifacts to upload", file=sys.stderr)
        return 0

    body, content_type = _multipart_body(files)
    try:
        _operator_request(url, method="POST", data=body, content_type=content_type)
    except urllib.error.HTTPError as exc:
        print(f"artifact upload failed: {exc}", file=sys.stderr)
        return 1
    except urllib.error.URLError as exc:
        print(f"artifact upload failed: {exc}", file=sys.stderr)
        return 1
    return 0


def finish() -> None:
    stage_x_debug()
    stage_pipeline_reports()
    archive_once()
    zip_x_debug()
    upload_artifacts()


def fetch_parent_state() -> None:
    url = os.environ.get("PDE_OPERATOR_PARENT_STATE_URL")
    if not url:
        raise RuntimeError("PDE_OPERATOR_PARENT_STATE_URL is not set")
    PIPELINE_DIR_ZIP.write_bytes(_operator_request(url))


def fetch_run_input() -> dict[str, object]:
    global _run_input
    if _run_input is not None:
        return _run_input
    url = os.environ.get("PDE_OPERATOR_INPUT_URL")
    if not url:
        raise RuntimeError("PDE_OPERATOR_INPUT_URL is not set")
    _run_input = json.loads(_operator_request(url))
    if not isinstance(_run_input, dict):
        raise RuntimeError("PDE_OPERATOR_INPUT_URL returned invalid JSON object")
    return _run_input


def _input_value(name: str, *, required: bool = False) -> str | None:
    payload = fetch_run_input()
    value = payload.get(name)
    if value is None:
        if required:
            raise RuntimeError(f"run input field '{name}' is not set")
        return None
    return value


def unarchive_once() -> None:
    subprocess.run(_pde_cli("unarchive", f"--archive_path={PIPELINE_DIR_ZIP}", f"--target_path={WS}"), check=True)


def _pde_run_args() -> list[str]:
    args = _pde_cli(
        "run",
        f"--pipeline_data={_input_value('pipeline_data', required=True)}",
        f"--pipeline_dir={PIPELINE_DIR}",
        f"--is_dry_run={_input_value('is_dry_run', required=True)}",
        f"--log_level={_input_value('log_level', required=True)}",
    )
    pipeline_vars = _input_value("pipeline_vars")
    if pipeline_vars:
        args.append(f"--pipeline_vars={pipeline_vars}")
    pipeline_vars_secure = _input_value("pipeline_vars_secure")
    if pipeline_vars_secure:
        args.append(f"--pipeline_vars_secure={pipeline_vars_secure}")
    return args


def _pde_retry_args() -> list[str]:
    args = _pde_cli(
        "retry",
        f"--pipeline_dir={PIPELINE_DIR}",
        f"--log_level={_input_value('log_level', required=True)}",
    )
    retry_vars = _input_value("retry_vars")
    if retry_vars:
        args.append(f"--retry_vars={retry_vars}")
    return args


def _on_signal(signum: int, _frame: object) -> None:
    global _cancelled
    _cancelled = True
    if _child is not None and _child.poll() is None:
        _child.send_signal(signal.SIGINT)


def _run_pde(args: list[str]) -> int:
    global _child, _cancelled
    _cancelled = False
    signal.signal(signal.SIGINT, _on_signal)
    signal.signal(signal.SIGTERM, _on_signal)
    with CONSOLE_LOG.open("w", encoding="utf-8") as log_file:
        _child = subprocess.Popen(args, stdout=log_file, stderr=subprocess.STDOUT)
        status = _child.wait()
    finish()
    if _cancelled or status in {130, -2, -signal.SIGINT}:
        return 143
    return status


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] not in {"run", "retry"}:
        print(f"usage: {argv[0]} run|retry", file=sys.stderr)
        return 2

    export_mounted_secret_env()
    export_mounted_secrets_atlas_config()
    fetch_run_input()
    if argv[1] == "retry":
        fetch_parent_state()
        unarchive_once()
        return _run_pde(_pde_retry_args())
    return _run_pde(_pde_run_args())


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
