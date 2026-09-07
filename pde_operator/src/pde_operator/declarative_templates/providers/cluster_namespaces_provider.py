from __future__ import annotations

import re
from typing import Any

from kubernetes import client, config
from kubernetes.client import CoreV1Api

from pde_operator.declarative_templates.contract.errors import DeclarativeOptionsProviderError
from pde_operator.declarative_templates.contract.models import EnumOption, FieldSpec


class ClusterNamespacesProvider:
    INTERFACE_NAME = "ClusterNamespaces"

    @staticmethod
    def list_options(field: FieldSpec, context: dict[str, Any]) -> list[EnumOption]:
        _ = context
        name_regex = ClusterNamespacesProvider._name_regex(field)
        namespaces = ClusterNamespacesProvider._get_core_api().list_namespace()
        options = [
            EnumOption(value=name, label=name)
            for ns in namespaces.items
            if (name := getattr(ns.metadata, "name", None)) and ClusterNamespacesProvider._matches(name, name_regex)
        ]
        return sorted(options, key=lambda opt: opt.value)

    @staticmethod
    def _name_regex(field: FieldSpec) -> re.Pattern[str] | None:
        raw = field.data.get("name_regex")
        if raw is None or raw == "":
            return None
        if not isinstance(raw, str):
            raise DeclarativeOptionsProviderError(f"{ClusterNamespacesProvider.INTERFACE_NAME} data.name_regex must be a string")
        try:
            return re.compile(raw)
        except re.error as exc:
            raise DeclarativeOptionsProviderError(f"Invalid {ClusterNamespacesProvider.INTERFACE_NAME} name_regex: {exc}") from exc

    @staticmethod
    def _matches(name: str, name_regex: re.Pattern[str] | None) -> bool:
        if name_regex is None:
            return True
        return name_regex.match(name) is not None

    @staticmethod
    def _get_core_api() -> CoreV1Api:
        try:
            config.load_incluster_config()
        except config.ConfigException:
            try:
                config.load_kube_config()
            except config.ConfigException as exc:
                raise DeclarativeOptionsProviderError("Kubernetes config not available for enum provider") from exc
        return client.CoreV1Api()
