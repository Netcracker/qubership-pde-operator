from __future__ import annotations

from typing import Any

import yaml

from pde_operator.declarative_templates.contract.errors import DeclarativeContractError
from pde_operator.declarative_templates.contract.models import (
    BindTo,
    DeclarativeRunTemplate,
    FieldSpec,
    FieldType,
    SelectType,
    ValidatorPattern,
)

_BIND_TO_VALUES = frozenset({"pipeline_var", "env_var", "pipeline_data", "is_dry_run", "log_level", "profile"})


class GitLabCiLoader(yaml.SafeLoader):
    """SafeLoader that accepts GitLab CI `!reference` tags."""


def _reference_constructor(loader: yaml.SafeLoader, node: yaml.Node) -> Any:
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node)
    if isinstance(node, yaml.ScalarNode):
        return loader.construct_scalar(node)
    if isinstance(node, yaml.MappingNode):
        return loader.construct_mapping(node)
    return None


GitLabCiLoader.add_constructor("!reference", _reference_constructor)


class DeclarativeTemplateParser:
    """Parse `.gitlab-ci.yml` (or equivalent) into a normalized DeclarativeRunTemplate."""

    @staticmethod
    def parse_yaml(yaml_text: str, *, fallback_name: str = "Declarative template") -> DeclarativeRunTemplate:
        try:
            parsed = yaml.load(yaml_text, Loader=GitLabCiLoader)
        except yaml.YAMLError as exc:
            raise DeclarativeContractError(f"Invalid YAML: {exc}") from exc
        if not isinstance(parsed, dict):
            raise DeclarativeContractError("YAML document must be a mapping")
        return DeclarativeTemplateParser.from_document(parsed, fallback_name=fallback_name)

    @staticmethod
    def from_document(doc: dict[str, Any], *, fallback_name: str = "Declarative template") -> DeclarativeRunTemplate:
        ui_variables = doc.get(".ui-variables")
        if not isinstance(ui_variables, dict):
            raise DeclarativeContractError("Document must contain a root '.ui-variables' mapping")

        variables = ui_variables.get("variables")
        if not isinstance(variables, dict) or not variables:
            raise DeclarativeContractError(".ui-variables.variables must be a non-empty mapping")

        customization = ui_variables.get("variables-fields-customization", {})
        fields = [
            DeclarativeTemplateParser._build_field(name, DeclarativeTemplateParser._normalize_variable_entry(name, raw), customization.get(name, {}))
            for name, raw in variables.items()
        ]
        return DeclarativeRunTemplate(name=DeclarativeTemplateParser._workflow_name(doc) or fallback_name, fields=fields)

    @staticmethod
    def _workflow_name(doc: dict[str, Any]) -> str | None:
        workflow = doc.get("workflow")
        if not isinstance(workflow, dict):
            return None
        name = workflow.get("name")
        return str(name).strip() if name else None

    @staticmethod
    def _normalize_variable_entry(name: str, raw_field: Any) -> dict[str, Any]:
        if isinstance(raw_field, dict):
            if "value" not in raw_field:
                raise DeclarativeContractError(f"Variable '{name}' must define 'value'")
            return raw_field
        if isinstance(raw_field, bool) or raw_field is None:
            return {"value": raw_field}
        if isinstance(raw_field, (int, float)):
            return {"value": str(raw_field)}
        if isinstance(raw_field, str):
            return {"value": raw_field}
        raise DeclarativeContractError(f"Variable '{name}' must be a scalar or a mapping with 'value'")

    @staticmethod
    def _build_field(name: str, raw_field: dict[str, Any], custom: dict[str, Any]) -> FieldSpec:
        value = raw_field.get("value")
        options = DeclarativeTemplateParser._parse_options(name, raw_field.get("options"))
        settings = custom.get("settings", {})
        interface, data = DeclarativeTemplateParser._parse_data(name, custom.get("data"))

        label = DeclarativeTemplateParser._optional_str(settings.get("label")) or name
        return FieldSpec(
            name=str(name),
            value=value,
            description=DeclarativeTemplateParser._optional_str(raw_field.get("description")),
            options=options,
            field_type=DeclarativeTemplateParser._infer_field_type(value, options, interface),
            select_type=DeclarativeTemplateParser._parse_select_type(name, settings.get("select_type")),
            required=bool(settings.get("required", False)),
            required_condition=DeclarativeTemplateParser._optional_str(settings.get("required_condition")),
            hide_condition=DeclarativeTemplateParser._optional_str(settings.get("hide_condition")),
            hidden=bool(settings.get("hidden", False)),
            readonly=bool(settings.get("readonly", False)),
            secure=bool(settings.get("secure", False)),
            placeholder=DeclarativeTemplateParser._optional_str(settings.get("placeholder")),
            label=label,
            bind_to=DeclarativeTemplateParser._parse_bind_to(name, settings.get("bind_to")),
            validators=DeclarativeTemplateParser._parse_validators(name, settings.get("validators")),
            interface=interface,
            data=data,
        )

    @staticmethod
    def _optional_str(raw: Any) -> str | None:
        if raw is None:
            return None
        text = str(raw).strip()
        return text or None

    @staticmethod
    def _parse_data(name: str, data_raw: Any) -> tuple[str | None, dict[str, Any]]:
        if not data_raw:
            return None, {}
        if not isinstance(data_raw, dict):
            raise DeclarativeContractError(f"variables-fields-customization.{name}.data must be a mapping")
        interface = DeclarativeTemplateParser._optional_str(data_raw.get("interface"))
        if not interface:
            raise DeclarativeContractError(f"variables-fields-customization.{name}.data.interface is required when data is set")
        return interface, {k: v for k, v in data_raw.items() if k != "interface"}

    @staticmethod
    def _parse_options(name: str, raw: Any) -> list[str] | None:
        if raw is None:
            return None
        if not isinstance(raw, list):
            raise DeclarativeContractError(f"Variable '{name}.options' must be an array of strings")
        return [str(item) for item in raw]

    @staticmethod
    def _infer_field_type(value: Any, options: list[str] | None, interface: str | None) -> FieldType:
        if isinstance(value, bool):
            return "checkbox"
        if options is not None:
            if {item.lower() for item in options} == {"true", "false"}:
                return "checkbox"
            return "select"
        if interface is not None:
            return "select"
        return "string"

    @staticmethod
    def _parse_select_type(name: str, raw: Any) -> SelectType:
        if raw is None:
            return "single"
        if raw not in ("single", "multi"):
            raise DeclarativeContractError(f"settings.select_type for '{name}' must be 'single' or 'multi'")
        return raw

    @staticmethod
    def _parse_bind_to(name: str, raw: Any) -> BindTo:
        if raw is None:
            return "pipeline_var"
        if raw not in _BIND_TO_VALUES:
            raise DeclarativeContractError(f"settings.bind_to for '{name}' must be one of: {', '.join(sorted(_BIND_TO_VALUES))}")
        return raw  # type: ignore[return-value]

    @staticmethod
    def _parse_validators(name: str, raw: Any) -> list[ValidatorPattern]:
        if not raw:
            return []
        if not isinstance(raw, list):
            raise DeclarativeContractError(f"settings.validators for '{name}' must be an array")
        try:
            return [ValidatorPattern.model_validate(item) for item in raw]
        except Exception as exc:
            raise DeclarativeContractError(f"Invalid validators for '{name}': {exc}") from exc
