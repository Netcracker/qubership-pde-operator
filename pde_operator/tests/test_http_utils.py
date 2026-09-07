import gzip
import json

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from pde_operator.utils.http_utils import HttpUtils


def _app() -> FastAPI:
    app = FastAPI()

    @app.post("/echo")
    async def echo(request: Request) -> dict:
        return await HttpUtils.parse_json_body(request)

    return app


def test_parse_plain_json() -> None:
    client = TestClient(_app())
    response = client.post("/echo", json={"status": "running"})
    assert response.status_code == 200
    assert response.json() == {"status": "running"}


def test_parse_gzip_json() -> None:
    payload = {"status": "succeeded", "stages": []}
    compressed = gzip.compress(json.dumps(payload).encode("utf-8"))

    client = TestClient(_app())
    response = client.post(
        "/echo",
        content=compressed,
        headers={
            "Content-Type": "application/json",
            "Content-Encoding": "gzip",
        },
    )
    assert response.status_code == 200
    assert response.json() == payload


def test_parse_invalid_gzip() -> None:
    client = TestClient(_app())
    response = client.post(
        "/echo",
        content=b"not-gzip",
        headers={"Content-Encoding": "gzip"},
    )
    assert response.status_code == 400
    assert "gzip" in response.json()["detail"].lower()


def test_parse_unsupported_encoding() -> None:
    client = TestClient(_app())
    response = client.post(
        "/echo",
        content=b'{"a":1}',
        headers={"Content-Encoding": "br"},
    )
    assert response.status_code == 415
