"""CPU/memory requests and limits for PDE Job pods."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ResourceDict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cpu: str | None = None
    memory: str | None = None


class JobResources(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requests: ResourceDict = Field(default_factory=ResourceDict)
    limits: ResourceDict = Field(default_factory=ResourceDict)

    @classmethod
    def lab_defaults(cls) -> JobResources:
        return cls(
            requests=ResourceDict(cpu="100m", memory="128Mi"),
            limits=ResourceDict(cpu="500m", memory="512Mi"),
        )
