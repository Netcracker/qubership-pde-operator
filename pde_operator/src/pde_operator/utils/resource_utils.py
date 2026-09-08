"""Merge and convert Job resource requests/limits for Kubernetes."""

from __future__ import annotations

from typing import Any

from kubernetes.client.models import V1ResourceRequirements

from pde_operator.schemas.job_resources import JobResources, ResourceDict


class ResourceUtils:
    @staticmethod
    def merge(base: JobResources, override: JobResources | dict[str, Any] | None) -> JobResources:
        """Partial merge: non-null override fields win; empty/None override returns a copy of base."""
        if not override:
            return base.model_copy(deep=True)
        overlay = override if isinstance(override, JobResources) else JobResources.model_validate(override)
        return JobResources(
            requests=ResourceUtils._merge_dict(base.requests, overlay.requests),
            limits=ResourceUtils._merge_dict(base.limits, overlay.limits),
        )

    @staticmethod
    def _merge_dict(base: ResourceDict, overlay: ResourceDict) -> ResourceDict:
        return ResourceDict(
            cpu=overlay.cpu if overlay.cpu is not None else base.cpu,
            memory=overlay.memory if overlay.memory is not None else base.memory,
        )

    @staticmethod
    def to_v1(resources: JobResources) -> V1ResourceRequirements | None:
        requests = ResourceUtils._quantity_map(resources.requests)
        limits = ResourceUtils._quantity_map(resources.limits)
        if not requests and not limits:
            return None
        return V1ResourceRequirements(requests=requests or None, limits=limits or None)

    @staticmethod
    def _quantity_map(values: ResourceDict) -> dict[str, str]:
        out: dict[str, str] = {}
        if values.cpu:
            out["cpu"] = values.cpu
        if values.memory:
            out["memory"] = values.memory
        return out
