from __future__ import annotations

import asyncio
import logging
from uuid import UUID

from pde_operator.config import Settings
from pde_operator.schemas.run_input import RunInputPayload
from pde_operator.services.artifacts_service import ArtifactsService
from pde_operator.utils.artifact_utils import ArtifactNotFoundError
from pde_operator.utils.input_crypto_utils import InputCryptoError, InputCryptoUtils

logger = logging.getLogger(__name__)


class RunInputStorage:
    """Encrypted run input (pipeline data/vars incl. real secure values) kept in artifact storage.

    Runs and scheduled runs both key their payload by their own id, so the same storage serves
    execution (a scheduled fire copies its payload onto the new run) and later reads (retry).
    """

    def __init__(self, settings: Settings, artifacts_service: ArtifactsService | None = None) -> None:
        self._settings = settings
        self._artifacts = artifacts_service or ArtifactsService(settings)

    async def store(self, entity_id: UUID, payload: RunInputPayload) -> None:
        plaintext = payload.model_dump_json().encode("utf-8")
        try:
            ciphertext = InputCryptoUtils.encrypt(self._settings.input_encryption_key, plaintext)
        except InputCryptoError as exc:
            raise RunInputStorageError(str(exc)) from exc
        try:
            await asyncio.to_thread(self._artifacts.put_run_input, entity_id, ciphertext)
        except Exception as exc:
            raise RunInputStorageError(f"Failed to store encrypted run input for '{entity_id}': {exc}") from exc

    def load(self, entity_id: UUID) -> RunInputPayload:
        try:
            ciphertext = self._artifacts.get_run_input_bytes(entity_id)
        except ArtifactNotFoundError as exc:
            raise RunInputNotAvailableError(f"Run input not found in storage for '{entity_id}'") from exc
        try:
            plaintext = InputCryptoUtils.decrypt(self._settings.input_encryption_key, ciphertext)
        except InputCryptoError as exc:
            raise RunInputNotAvailableError(str(exc)) from exc
        return RunInputPayload.model_validate_json(plaintext)

    async def delete(self, entity_id: UUID) -> int:
        """Delete every object stored under the id — for a run that includes its artifacts."""
        try:
            return await asyncio.to_thread(self._artifacts.delete_run_artifacts, entity_id)
        except Exception as exc:
            raise RunInputStorageError(f"Failed to delete stored run input for '{entity_id}': {exc}") from exc


class RunInputNotAvailableError(LookupError):
    def __init__(self, message: str) -> None:
        super().__init__(message)


class RunInputStorageError(RuntimeError):
    def __init__(self, message: str) -> None:
        super().__init__(message)
