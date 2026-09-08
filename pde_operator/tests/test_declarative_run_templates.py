from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from pde_operator.config import Settings
from pde_operator.db.models.run_template import RunTemplate
from pde_operator.declarative_templates.contract.errors import DeclarativeContractError
from pde_operator.declarative_templates.contract.parser import DeclarativeTemplateParser
from pde_operator.declarative_templates.engine import AssembledRunPayload, DeclarativeEngine
from pde_operator.declarative_templates.services.form_state import DeclarativeFormStateUtils
from pde_operator.declarative_templates.services.run_adapter import DeclarativeRunAdapter
from pde_operator.declarative_templates.services.rsql import RsqlUtils
from pde_operator.declarative_templates.services.template_store import DeclarativeTemplateStore
from pde_operator.services.run_service import RunService


def _yaml_template() -> str:
    return """
workflow:
  name: Deploy application

variables: !reference [.ui-variables, variables]

.ui-variables:
  variables:
    PIPELINE_URL:
      value: "https://example.com/p.yaml"
      description: Pipeline URL
    PROFILE:
      value: "default"
    DEPLOY_MODE:
      value: "application"
      options:
        - "application"
        - "library"
    APP_NAME:
      value: ""
      description: Application name
    DRY_RUN:
      value: false
    SERVICE_ACCOUNT:
      value: "deploy-bot"
  variables-fields-customization:
    PIPELINE_URL:
      settings:
        bind_to: pipeline_data
        required: true
        hidden: true
        readonly: true
    PROFILE:
      settings:
        bind_to: profile
        required: true
        hidden: true
    DEPLOY_MODE:
      settings:
        required: true
        select_type: single
    APP_NAME:
      settings:
        required_condition: "DEPLOY_MODE=='application'"
        hide_condition: "DEPLOY_MODE!='application'"
    DRY_RUN:
      settings:
        bind_to: is_dry_run
    SERVICE_ACCOUNT:
      settings:
        hidden: true
        readonly: true
"""


def _settings() -> Settings:
    return Settings(
        k8s_job_creation_enabled=False,
        ui_enabled=False,
        retention_enabled=False,
        api_admin_token="admin",
        job_token_signing_key="test-job-token-signing-key-32b!!",
    )


def test_parse_gitlab_ui_yaml() -> None:
    contract = DeclarativeTemplateParser.parse_yaml(_yaml_template())
    assert contract.name == "Deploy application"
    assert len(contract.fields) == 6
    by_name = {f.name: f for f in contract.fields}
    assert by_name["PIPELINE_URL"].bind_to == "pipeline_data"
    assert by_name["APP_NAME"].hide_condition == "DEPLOY_MODE!='application'"
    assert by_name["DEPLOY_MODE"].field_type == "select"
    assert by_name["DRY_RUN"].field_type == "checkbox"


def test_parse_scalar_variable_entries() -> None:
    contract = DeclarativeTemplateParser.parse_yaml(
        """
.ui-variables:
  variables:
    GENERIC_FIELD: some_value
    ANOTHER_FIELD: 42
    FLAG: true
    PIPELINE_URL: "https://example.com/p.yaml"
  variables-fields-customization:
    PIPELINE_URL:
      settings:
        bind_to: pipeline_data
"""
    )
    by_name = {f.name: f for f in contract.fields}
    assert by_name["GENERIC_FIELD"].value == "some_value"
    assert by_name["GENERIC_FIELD"].field_type == "string"
    assert by_name["ANOTHER_FIELD"].value == "42"
    assert by_name["FLAG"].field_type == "checkbox"
    assert by_name["PIPELINE_URL"].bind_to == "pipeline_data"


def test_hide_condition_omits_requiredness() -> None:
    contract = DeclarativeTemplateParser.parse_yaml(_yaml_template())
    effective = DeclarativeFormStateUtils.evaluate(contract, {"DEPLOY_MODE": "library"})
    assert effective.visible["APP_NAME"] is False
    assert effective.required["APP_NAME"] is False


def test_rsql_field_to_field_and_exact_multi() -> None:
    assert RsqlUtils.evaluate("A==B", {"A": "x", "B": "x"}) is True
    assert RsqlUtils.evaluate("A!=B", {"A": "x", "B": "y"}) is True
    assert RsqlUtils.evaluate("ENV=='prod'", {"ENV": "prod"}) is True
    assert RsqlUtils.evaluate("ENV=='prod'", {"ENV": "dev,prod"}) is False


def _yaml_without_run_defaults() -> str:
    return """
.ui-variables:
  variables:
    PIPELINE_URL:
      value: ""
    PROFILE:
      value: ""
  variables-fields-customization:
    PIPELINE_URL:
      settings:
        bind_to: pipeline_data
        required: true
    PROFILE:
      settings:
        bind_to: profile
        required: true
"""


@pytest.mark.asyncio
async def test_import_without_run_field_defaults() -> None:
    session = AsyncMock()
    session.get = AsyncMock(return_value=None)
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock(side_effect=lambda obj: obj)

    store = DeclarativeTemplateStore(session=session)
    template = await store.import_from_yaml(yaml_text=_yaml_without_run_defaults())

    assert template.template_kind == "declarative"
    assert template.name == "Declarative template"
    assert template.pipeline_data == ""
    assert template.declarative_spec is not None
    session.add.assert_called_once()
    assert template.id is not None


def test_run_from_user_provided_run_fields() -> None:
    contract = DeclarativeTemplateParser.parse_yaml(_yaml_without_run_defaults())
    template_id = uuid4()
    template = RunTemplate(
        id=template_id,
        name=contract.name,
        pipeline_data="",
        template_kind="declarative",
        declarative_spec=contract.model_dump(mode="json"),
    )

    payload = DeclarativeEngine.build_run_payload(
        contract,
        {
            "PIPELINE_URL": "https://example.com/user-picked.yaml",
            "PROFILE": "staging",
        },
    )
    assert isinstance(payload, AssembledRunPayload)
    assert payload.pipeline_data == "https://example.com/user-picked.yaml"
    assert payload.profile_id == "staging"

    create_req = DeclarativeRunAdapter.to_create_run_request_from_template(
        template,
        {
            "PIPELINE_URL": "https://example.com/user-picked.yaml",
            "PROFILE": "staging",
        },
    )
    assert create_req.pipeline_data == "https://example.com/user-picked.yaml"
    assert create_req.profile_id == "staging"


def test_hidden_field_still_submitted() -> None:
    contract = DeclarativeTemplateParser.parse_yaml(_yaml_template())
    payload = DeclarativeEngine.build_run_payload(
        contract,
        {
            "DEPLOY_MODE": "application",
            "APP_NAME": "my-app",
        },
    )
    assert payload.pipeline_data == "https://example.com/p.yaml"
    assert payload.pipeline_vars is not None
    assert "SERVICE_ACCOUNT=deploy-bot" in payload.pipeline_vars.splitlines()
    assert "APP_NAME=my-app" in payload.pipeline_vars.splitlines()


def test_secure_pipeline_var() -> None:
    yaml_text = """
.ui-variables:
  variables:
    PIPELINE_URL:
      value: "https://example.com/p.yaml"
    MY_TOKEN:
      value: "secret"
  variables-fields-customization:
    PIPELINE_URL:
      settings:
        bind_to: pipeline_data
    MY_TOKEN:
      settings:
        secure: true
"""
    contract = DeclarativeTemplateParser.parse_yaml(yaml_text)
    payload = DeclarativeEngine.build_run_payload(contract, {})
    assert payload.pipeline_vars_secure == "MY_TOKEN=secret"
    assert payload.pipeline_vars is None


@pytest.mark.asyncio
async def test_static_enum_validation_on_submit() -> None:
    contract = DeclarativeTemplateParser.parse_yaml(_yaml_template())
    template_id = uuid4()

    template = RunTemplate(
        id=template_id,
        name=contract.name,
        pipeline_data="https://example.com/p.yaml",
        template_kind="declarative",
        declarative_spec=contract.model_dump(mode="json"),
    )
    session = AsyncMock()
    session.get = AsyncMock(return_value=template)

    run_service = RunService(session, _settings())
    run_service.create_run = AsyncMock(return_value=MagicMock(id="run-id"))  # type: ignore[method-assign]

    with pytest.raises(DeclarativeContractError):
        await run_service.create_run_from_declarative_template(
            template_id,
            {"DEPLOY_MODE": "invalid", "APP_NAME": "x"},
        )
