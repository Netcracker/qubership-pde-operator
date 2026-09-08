# Declarative Run Template Syntax

Contract reference for declarative run templates ingested from `.gitlab-ci.yml`.

## Document shape

A declarative template is any YAML document that contains a root **`.ui-variables`** mapping. That key is how PDE recognizes the form contract (not `kind`).

```yaml
# all optional except .ui-variables for PDE form ingest
apiVersion: v1
kind: DeclarativeRunTemplate

workflow:
  name: Custom Pipeline Name

variables: !reference [.ui-variables, variables]

.ui-variables:
  variables: { ... }
  variables-fields-customization: { ... }   # optional
```

---

## `.ui-variables` — baseline (GitLab / Custom UIs)

Shared with the existing GitLab-based UI contract. PDE must accept these without requiring changes.

| Name                                                            | Type             | Is mandatory            | Description                                                                                                                                                                                            | Example value                        |
|-----------------------------------------------------------------|------------------|-------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|--------------------------------------|
| `variables`                                                     | object           | yes                     | Main object with fields definition                                                                                                                                                                     | -                                    |
| `variables.{name}`                                              | object or scalar | yes                     | Parameter field on UI. Scalar form (`NAME: value`) or expanded mapping (`NAME: { value, description, options }`).                                                                                      | `PARAMETER` / `"value"`              |
| `variables.{name}.value`                                        | string           | yes (expanded form)     | Default value of field. If boolean, field type is checkbox; if string, string. For multi-select, provide a comma-separated string of selected values. In scalar form, the entry itself is the default. | `"value"`                            |
| `variables.{name}.description`                                  | string           | no                      | Description of field                                                                                                                                                                                   | `Parameter for integration`          |
| `variables.{name}.options`                                      | array{string}    | no                      | If defined, field type is select (single by default). If options are exactly `"true"` / `"false"`, field is treated as checkbox (default should match a default option).                               | `["value1", "value2"]`               |
| `variables-fields-customization`                                | object           | no                      | Object for additional properties for fields                                                                                                                                                            | -                                    |
| `variables-fields-customization.{name}`                         | object           | yes                     | Name of field on UI                                                                                                                                                                                    | -                                    |
| `variables-fields-customization.{name}.data`                    | object           | no                      | Object for field data properties                                                                                                                                                                       | -                                    |
| `variables-fields-customization.{name}.data.interface`          | string           | yes (if `data` present) | Name of interface used for dynamic values fetch                                                                                                                                                        | `Environments`                       |
| `variables-fields-customization.{name}.settings`                | object           | no                      | Object for field settings properties                                                                                                                                                                   | -                                    |
| `variables-fields-customization.{name}.settings.select_type`    | string           | no                      | Select mode: `single` or `multi` (default `single`)                                                                                                                                                    | `single`                             |
| `variables-fields-customization.{name}.settings.hide_condition` | string           | no                      | RSQL expression over other parameters; when true, field is hidden                                                                                                                                      | `PREDEFINED_OPTIONS_FIELD!='value1'` |

Type inference: boolean `value` -> checkbox; else if `options` (and not true/false-only checkbox) -> select; else -> string.

---

## `.ui-variables` — PDE extensions

Additive keys under `variables-fields-customization.{name}.settings`. Other UIs ignore unknown properties. Same table format as above.

Boolean flags `required`, `hidden`, `readonly`, and `secure` default to **`false`** when omitted.

| Name                   | Type          | Is mandatory | Description                                                                                                                                                                                         | Example value                                     |
|------------------------|---------------|--------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------|
| `required`             | boolean       | no           | When true, field is required **if visible**. Combined with `required_condition` as OR. Hidden fields are never treated as required for validation.                                                  | `true`                                            |
| `required_condition`   | string        | no           | RSQL; when true and field is visible, field is required. Effective required = `required OR required_condition` (visibility still wins).                                                             | `ENVIRONMENT=='prod'`                             |
| `hidden`               | boolean       | no           | Always hide in UI. Value still submitted to the field's bind (from `value` / user).                                                                                                                 | `true`                                            |
| `readonly`             | boolean       | no           | Rendered but not editable.                                                                                                                                                                          | `true`                                            |
| `secure`               | boolean       | no           | Mask input in UI. If effective `bind_to` is `pipeline_var` (default), also store in secure pipeline vars. If `bind_to` is anything else, still mask UI but ignore `secure` for assembly.            | `true`                                            |
| `placeholder`          | string        | no           | Input placeholder text.                                                                                                                                                                             | `my-app`                                          |
| `label`                | string        | no           | Display label; defaults to `{name}`.                                                                                                                                                                | `Target namespace`                                |
| `bind_to`              | string        | no           | Where the value is written. One of: `pipeline_var` (default), `env_var`, `pipeline_data`, `is_dry_run`, `log_level`, `profile`. Field `{name}` is the variable name for `pipeline_var` / `env_var`. | `pipeline_data`                                   |
| `validators`           | array{object} | no           | Validation rules applied when the field has a non-empty value (and is validated).                                                                                                                   | -                                                 |
| `validators[].type`    | string        | yes          | Validator type. MVP: `pattern` only.                                                                                                                                                                | `pattern`                                         |
| `validators[].value`   | string        | yes          | For `pattern`: regular expression passed to match-from-start.                                                                                                                                       | `"^[a-z0-9-]+$"`                                  |
| `validators[].message` | string        | yes          | Error text when validation fails.                                                                                                                                                                   | `Use lowercase letters, digits, and dashes only.` |

---

## Available interfaces

Used in `variables-fields-customization.{name}.data.interface`. Extra per-interface keys may live under the same `data` object.

| Name                | Description                                                                                                                             |
|---------------------|-----------------------------------------------------------------------------------------------------------------------------------------|
| `Profiles`          | Lists profile IDs from the operator database.                                                                                           |
| `ClusterNamespaces` | Lists cluster namespaces. Optional `data.name_regex` filter.                                                                            |
| `GitFiles`          | Lists files or directories from a Git repository (`data.url`, `ref`, `glob`, `select_directories`, `strip_extension`, `use_full_path`). |

Unknown interface names (for example `Environments` from the GitLab UI sample): ingest still succeeds; the UI shows a **warning** and the control falls back to a free **string** input so the user can type a value manually.

---

## Full example

Illustrates baseline GitLab fields plus every PDE extension in one document.

```yaml
workflow:
  name: Declarative features sample

variables: !reference [.ui-variables, variables]

.ui-variables:
  variables:
    PIPELINE_URL:
      value: "https://example.com/pipelines/deploy.yaml"
      description: |
        Pipeline definition URL (bound to pipeline_data)

    PROFILE:
      value: "default"
      description: |
        Execution profile

    DRY_RUN:
      value: false
      description: |
        Dry-run flag (checkbox via boolean value)

    LOG_LEVEL:
      value: "INFO"
      description: |
        Log level
      options:
        - "DEBUG"
        - "INFO"
        - "WARNING"
        - "ERROR"

    GENERIC_FIELD:
      value: ""
      description: |
        Free-text pipeline variable

    CHECKBOX_FIELD:
      value: false
      description: |
        Checkbox pipeline variable

    PREDEFINED_OPTIONS_FIELD:
      value: "value1"
      description: |
        Hardcoded multi-select (comma-separated default when multiple)
      options:
        - "value1"
        - "value2"
        - "value3"

    ENVIRONMENT:
      value: "stage"
      description: |
        Controls visibility / requiredness of other fields
      options:
        - "dev"
        - "stage"
        - "prod"

    NAMESPACE:
      value: ""
      description: |
        Namespace from ClusterNamespaces interface

    PIPELINE_CONFIG_DIR:
      value: ""
      description: |
        Directory from GitFiles interface

    UNKNOWN_INTERFACE_FIELD:
      value: ""
      description: |
        Unknown interface -> UI warning + free string input

    APPROVAL_TICKET:
      value: ""
      description: |
        Visible and required only when ENVIRONMENT is exactly prod

    SERVICE_ACCOUNT:
      value: "deploy-bot"
      description: |
        Hidden but still submitted as a pipeline var

    APP_NAME:
      value: ""
      description: |
        Validated string with placeholder and label

    MY_TOKEN:
      value: ""
      description: |
        Secure (masked) pipeline variable

    REFERENCE_FIELD:
      value: "value1"
      description: |
        Controller for field-to-field RSQL compare
      options:
        - "value1"
        - "value2"

    CONDITIONAL_PEER:
      value: ""
      description: |
        Hidden unless REFERENCE_FIELD equals value1

    MIRROR_GATE:
      value: "value1"
      description: |
        Used as RHS field name in RSQL (field-to-field compare)

    FIELD_TO_FIELD_PEER:
      value: ""
      description: |
        Hidden unless REFERENCE_FIELD == MIRROR_GATE (field-to-field)

  variables-fields-customization:
    PIPELINE_URL:
      settings:
        bind_to: pipeline_data
        required: true
        readonly: true
        label: Pipeline URL

    PROFILE:
      data:
        interface: Profiles
      settings:
        bind_to: profile
        required: true
        select_type: single
        label: Profile

    DRY_RUN:
      settings:
        bind_to: is_dry_run

    LOG_LEVEL:
      settings:
        bind_to: log_level
        select_type: single

    PREDEFINED_OPTIONS_FIELD:
      settings:
        select_type: multi

    ENVIRONMENT:
      settings:
        select_type: single
        required: true

    NAMESPACE:
      data:
        interface: ClusterNamespaces
        name_regex: "^cloud-.*"
      settings:
        select_type: single
        required: true
        label: Namespace

    PIPELINE_CONFIG_DIR:
      data:
        interface: GitFiles
        url: https://github.com/Netcracker/qubership-pipelines-declarative-executor.git
        ref: sample_pipelines
        glob: "**/pipeline_configs/*"
        select_directories: true
        strip_extension: false
        use_full_path: false
      settings:
        select_type: single
        label: Pipeline config dir

    UNKNOWN_INTERFACE_FIELD:
      data:
        interface: Environments
      settings:
        select_type: single
        label: Environment (manual if unsupported)

    APPROVAL_TICKET:
      settings:
        hide_condition: "ENVIRONMENT!='prod'"
        required_condition: "ENVIRONMENT=='prod'"
        placeholder: TICKET-123

    SERVICE_ACCOUNT:
      settings:
        hidden: true
        readonly: true

    APP_NAME:
      settings:
        required: true
        placeholder: my-app
        label: Application name
        validators:
          - type: pattern
            value: "^[a-z0-9-]+$"
            message: Use lowercase letters, digits, and dashes only.

    MY_TOKEN:
      settings:
        secure: true
        placeholder: secret

    REFERENCE_FIELD:
      settings:
        select_type: single

    CONDITIONAL_PEER:
      settings:
        hide_condition: "REFERENCE_FIELD!='value1'"
        required_condition: "REFERENCE_FIELD=='value1'"

    FIELD_TO_FIELD_PEER:
      settings:
        hide_condition: "REFERENCE_FIELD!=MIRROR_GATE"
        required_condition: "REFERENCE_FIELD==MIRROR_GATE"
```
