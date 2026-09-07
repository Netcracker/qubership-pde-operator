from __future__ import annotations

import gzip
import json

from fastapi import HTTPException, Request


class HttpUtils:
    @staticmethod
    async def read_raw_body(request: Request) -> bytes:
        """Return request body bytes, optionally gzip-decompressed via Content-Encoding."""
        body = await request.body()
        encoding = (request.headers.get("content-encoding") or "").lower().strip()

        if encoding == "gzip":
            try:
                return gzip.decompress(body)
            except OSError as exc:
                raise HTTPException(status_code=400, detail="Invalid gzip-compressed body") from exc
        if encoding and encoding != "identity":
            raise HTTPException(status_code=415, detail=f"Unsupported Content-Encoding: {encoding}")
        return body

    @staticmethod
    async def parse_json_body(request: Request) -> dict:
        """Parse a JSON object body, optionally gzip-compressed via Content-Encoding."""
        body = await HttpUtils.read_raw_body(request)

        try:
            data = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise HTTPException(status_code=400, detail="Invalid JSON body") from exc

        if not isinstance(data, dict):
            raise HTTPException(status_code=400, detail="JSON body must be an object")

        return data

