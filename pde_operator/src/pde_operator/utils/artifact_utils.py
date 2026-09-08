from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import BinaryIO


class ArtifactKind(StrEnum):
    STATE = "state"
    LOG = "log"
    X_DEBUG = "x_debug"
    REPORT = "report"


@dataclass(frozen=True)
class ArtifactKindSpec:
    filename: str
    content_type: str
    required: bool = False


@dataclass(frozen=True)
class ArtifactObject:
    key: str
    body: BinaryIO
    content_type: str
    content_length: int | None = None


class ArtifactsDisabledError(RuntimeError):
    pass


class ArtifactNotFoundError(LookupError):
    def __init__(self, key: str) -> None:
        super().__init__(f"Artifact '{key}' not found")
        self.key = key


class ArtifactUtils:
    _KIND_SPECS: dict[ArtifactKind, ArtifactKindSpec] = {
        ArtifactKind.STATE: ArtifactKindSpec("pipeline_dir.zip", "application/zip", required=True),
        ArtifactKind.LOG: ArtifactKindSpec("console.log", "text/plain"),
        ArtifactKind.X_DEBUG: ArtifactKindSpec("x_debug.zip", "application/zip"),
        ArtifactKind.REPORT: ArtifactKindSpec("pipeline_report.json", "application/json"),
    }

    @staticmethod
    def parse_artifact_kind(kind: str) -> ArtifactKind:
        try:
            return ArtifactKind(kind)
        except ValueError as exc:
            raise ValueError(f"Unknown artifact kind '{kind}'") from exc

    @staticmethod
    def spec(kind: ArtifactKind) -> ArtifactKindSpec:
        return ArtifactUtils._KIND_SPECS[kind]

    @staticmethod
    def filename(kind: ArtifactKind) -> str:
        return ArtifactUtils.spec(kind).filename

    @staticmethod
    def content_type(kind: ArtifactKind) -> str:
        return ArtifactUtils.spec(kind).content_type
