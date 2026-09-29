from __future__ import annotations

import base64
import hashlib
import logging
from uuid import UUID

from cryptography.fernet import Fernet, InvalidToken

from pde_operator.config import Settings

logger = logging.getLogger(__name__)

MASKED_VALUE = "[MASKED]"
INPUT_FILENAME = "input.json"
INPUT_CONTENT_TYPE = "application/octet-stream"


class InputCryptoError(RuntimeError):
    pass


class InputCryptoUtils:
    @staticmethod
    def ensure_encryption_key(settings: Settings) -> None:
        if settings.input_encryption_key.strip():
            InputCryptoUtils._fernet(settings.input_encryption_key)
            return
        settings.input_encryption_key = Fernet.generate_key().decode("ascii")
        logger.warning(f"PDE_OPERATOR_INPUT_ENCRYPTION_KEY was not set; generated ephemeral encryption key: {settings.input_encryption_key}")

    @staticmethod
    def encrypt(key: str, plaintext: bytes) -> bytes:
        return InputCryptoUtils._fernet(key).encrypt(plaintext)

    @staticmethod
    def decrypt(key: str, ciphertext: bytes) -> bytes:
        try:
            return InputCryptoUtils._fernet(key).decrypt(ciphertext)
        except InvalidToken as exc:
            raise InputCryptoError("Failed to decrypt run input (invalid key or corrupted ciphertext)") from exc

    @staticmethod
    def input_key(run_id: UUID) -> str:
        return f"{run_id}/{INPUT_FILENAME}"

    @staticmethod
    def mask_secure_vars(value: str | None) -> str | None:
        if not value:
            return value
        masked_lines: list[str] = []
        for line in value.splitlines():
            if not line.strip():
                masked_lines.append(line)
                continue
            if "=" in line:
                key, _sep, _rest = line.partition("=")
                masked_lines.append(f"{key}={MASKED_VALUE}")
            else:
                masked_lines.append(MASKED_VALUE)
        return "\n".join(masked_lines)

    @staticmethod
    def merge_masked_secure(submitted: str | None, existing_real: str | None) -> str | None:
        """Resolve submitted `KEY=value` lines against the stored real values.

        A value equal to MASKED_VALUE means "unchanged": the stored secret for that key is kept.
        Anything else replaces it, and a key missing from the submission is dropped.
        """
        if not submitted or not submitted.strip():
            return None

        existing: dict[str, str] = {}
        for line in (existing_real or "").splitlines():
            if "=" in line:
                key, _sep, value = line.partition("=")
                existing[key] = value

        merged_lines: list[str] = []
        for line in submitted.splitlines():
            if not line.strip():
                continue
            if "=" not in line:
                merged_lines.append(line)
                continue
            key, _sep, value = line.partition("=")
            if value != MASKED_VALUE:
                merged_lines.append(f"{key}={value}")
                continue
            if key not in existing:
                raise InputCryptoError(f"Cannot keep masked value for unknown secure key '{key}'")
            merged_lines.append(f"{key}={existing[key]}")
        return "\n".join(merged_lines) if merged_lines else None

    @staticmethod
    def _fernet(secret: str) -> Fernet:
        cleaned = secret.strip()
        if not cleaned:
            raise InputCryptoError("PDE_OPERATOR_INPUT_ENCRYPTION_KEY is not set")
        derived = base64.urlsafe_b64encode(hashlib.sha256(cleaned.encode("utf-8")).digest())
        return Fernet(derived)
