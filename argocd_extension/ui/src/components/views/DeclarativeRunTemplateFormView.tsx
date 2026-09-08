import React from "react";
import { Btn } from "../ui";
import { isKnownInterface, type DeclarativeField, type DeclarativeRunTemplate } from "../../lib/declarative_types";

type Props = {
  contract: DeclarativeRunTemplate;
  submitting: boolean;
  onSubmit: (values: Record<string, any>) => Promise<void>;
  fetchOptions: (fieldId: string, context: Record<string, any>) => Promise<{ value: string; label: string }[]>;
};

type EnumOpt = { value: string; label: string };

const RSQL_RE =
  /^\s*([A-Za-z_][A-Za-z0-9_]*)\s*(==|!=)\s*(?:'([^']*)'|([A-Za-z_][A-Za-z0-9_]*))\s*$/;

function normalizeRsqlValue(value: any): string {
  if (value === undefined || value === null) return "";
  if (typeof value === "boolean") return value ? "true" : "false";
  return String(value);
}

function evaluateRsql(expression: string | null | undefined, values: Record<string, any>): boolean {
  if (!expression || !String(expression).trim()) return false;
  const match = RSQL_RE.exec(String(expression));
  if (!match) return false;
  const left = normalizeRsqlValue(values[match[1]]);
  const op = match[2];
  const right = match[3] !== undefined ? match[3] : normalizeRsqlValue(values[match[4]]);
  const equal = left === right;
  return op === "==" ? equal : !equal;
}

function resolveValues(fields: DeclarativeField[], userValues: Record<string, any>): Record<string, any> {
  const out: Record<string, any> = {};
  for (const f of fields) {
    out[f.name] = userValues[f.name] !== undefined ? userValues[f.name] : f.value;
  }
  return out;
}

function evaluateFormState(fields: DeclarativeField[], values: Record<string, any>) {
  const resolved = resolveValues(fields, values);
  const visible: Record<string, boolean> = {};
  const required: Record<string, boolean> = {};
  for (const f of fields) {
    const hidden = !!f.hidden || evaluateRsql(f.hide_condition, resolved);
    visible[f.name] = !hidden;
    required[f.name] = visible[f.name] ? !!f.required || evaluateRsql(f.required_condition, resolved) : false;
  }
  return { visible, required, resolved };
}

function isEmptyValue(value: any): boolean {
  return value === undefined || value === null || (typeof value === "string" && value.trim() === "");
}

function usesDynamicSelect(field: DeclarativeField): boolean {
  return field.field_type === "select" && !!field.interface && isKnownInterface(field.interface);
}

function usesUnknownInterface(field: DeclarativeField): boolean {
  return !!field.interface && !isKnownInterface(field.interface);
}

function staticOptions(field: DeclarativeField): EnumOpt[] {
  if (!field.options || !Array.isArray(field.options)) return [];
  return field.options.map((value) => ({ value, label: value }));
}

function initialFormValues(contract: DeclarativeRunTemplate): Record<string, any> {
  const out: Record<string, any> = {};
  for (const f of contract.fields || []) {
    if (f.value !== undefined && f.value !== null) {
      out[f.name] = f.value;
      continue;
    }
    if (f.field_type === "select" && f.options?.length) {
      out[f.name] = f.options[0];
    }
  }
  return out;
}

function FieldLabel(props: {
  htmlFor: string;
  label: string;
  required: boolean;
  description?: string | null;
}) {
  return (
    <label className="pde-decl-label" htmlFor={props.htmlFor} title={props.description || undefined}>
      {props.label}
      {props.required ? (
        <span className="pde-decl-required" aria-hidden="true">
          {"\u00a0*"}
        </span>
      ) : null}
    </label>
  );
}

export function DeclarativeRunTemplateFormView(props: Props) {
  const { contract, submitting, onSubmit, fetchOptions } = props;
  const fields = contract.fields || [];

  const [values, setValues] = React.useState<Record<string, any>>(() => initialFormValues(contract));
  const [attemptedSubmit, setAttemptedSubmit] = React.useState(false);
  const [optionsByFieldId, setOptionsByFieldId] = React.useState<Record<string, EnumOpt[]>>({});
  const [loadingOptions, setLoadingOptions] = React.useState<Record<string, boolean>>({});
  const fetchedRef = React.useRef<Record<string, boolean>>({});
  const optionsFetchSeqRef = React.useRef<Record<string, number>>({});
  const valuesRef = React.useRef(values);
  valuesRef.current = values;

  const setFieldValue = React.useCallback((fieldId: string, value: any) => {
    setValues((prev) => (prev[fieldId] === value ? prev : { ...prev, [fieldId]: value }));
  }, []);

  React.useEffect(() => {
    setValues(initialFormValues(contract));
    setOptionsByFieldId({});
    setLoadingOptions({});
    setAttemptedSubmit(false);
    fetchedRef.current = {};
    optionsFetchSeqRef.current = {};
  }, [contract]);

  const { visible, required } = evaluateFormState(fields, values);

  React.useEffect(() => {
    for (const f of fields) {
      if (!usesDynamicSelect(f)) continue;
      const fieldId = f.name;
      if (fetchedRef.current[fieldId]) continue;

      const seq = (optionsFetchSeqRef.current[fieldId] || 0) + 1;
      optionsFetchSeqRef.current[fieldId] = seq;
      fetchedRef.current[fieldId] = true;
      setLoadingOptions((prev) => ({ ...prev, [fieldId]: true }));

      void (async () => {
        try {
          const opts = await fetchOptions(fieldId, valuesRef.current);
          if (optionsFetchSeqRef.current[fieldId] !== seq) return;
          setOptionsByFieldId((prev) => ({ ...prev, [fieldId]: opts }));
          setValues((prev) => {
            const current = prev[fieldId];
            if (opts.some((o) => o.value === current)) return prev;
            if (opts.length === 0) return isEmptyValue(current) ? prev : { ...prev, [fieldId]: "" };
            return { ...prev, [fieldId]: opts[0].value };
          });
        } catch {
          if (optionsFetchSeqRef.current[fieldId] !== seq) return;
          setOptionsByFieldId((prev) => ({ ...prev, [fieldId]: [] }));
          setValues((prev) => (isEmptyValue(prev[fieldId]) ? prev : { ...prev, [fieldId]: "" }));
        } finally {
          if (optionsFetchSeqRef.current[fieldId] === seq) {
            setLoadingOptions((prev) => ({ ...prev, [fieldId]: false }));
          }
        }
      })();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [contract]);

  const hasMissingRequired = fields.some((f) => {
    if (!visible[f.name] || !required[f.name]) return false;
    return isEmptyValue(values[f.name]);
  });

  const renderField = (f: DeclarativeField) => {
    if (!visible[f.name]) return null;

    const inputId = `pde-decl-field-${f.name}`;
    const isRequired = !!required[f.name];
    const isReadonly = !!f.readonly;
    const showInvalid = attemptedSubmit && isRequired && isEmptyValue(values[f.name]);
    const controlClass = [
      f.field_type === "select" && !usesUnknownInterface(f) ? "pde-select" : "pde-input",
      showInvalid ? "pde-decl-invalid" : "",
      isReadonly ? "pde-decl-readonly" : "",
    ]
      .filter(Boolean)
      .join(" ");

    let control: React.ReactNode = null;
    let warning: React.ReactNode = null;

    if (usesUnknownInterface(f)) {
      warning = (
        <p className="pde-muted" style={{ margin: "4px 0 0", fontSize: 12 }}>
          Unsupported interface <span className="pde-mono">{f.interface}</span> — enter a value manually.
        </p>
      );
      control = (
        <input
          id={inputId}
          className={controlClass}
          type={f.secure ? "password" : "text"}
          value={values[f.name] ?? ""}
          disabled={isReadonly}
          placeholder={f.placeholder || undefined}
          autoComplete={f.secure ? "off" : undefined}
          onChange={(e: any) => setFieldValue(f.name, e.target.value)}
        />
      );
    } else if (f.field_type === "checkbox") {
      const checked = values[f.name] === true || String(values[f.name]).toLowerCase() === "true";
      control = (
        <input
          id={inputId}
          className={`pde-decl-toggle${showInvalid ? " pde-decl-invalid-toggle" : ""}`}
          type="checkbox"
          checked={checked}
          disabled={isReadonly}
          onChange={(e: any) => setFieldValue(f.name, e.target.checked)}
        />
      );
    } else if (f.field_type === "select") {
      const opts = usesDynamicSelect(f) ? optionsByFieldId[f.name] || [] : staticOptions(f);
      const multi = f.select_type === "multi";
      if (multi) {
        const selected = new Set(
          String(values[f.name] ?? "")
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean),
        );
        control = (
          <select
            id={inputId}
            className={controlClass}
            multiple
            value={[...selected]}
            disabled={isReadonly || (usesDynamicSelect(f) && loadingOptions[f.name] === true)}
            onChange={(e: any) => {
              const next = Array.from(e.target.selectedOptions).map((o: any) => o.value);
              setFieldValue(f.name, next.join(","));
            }}
          >
            {opts.length === 0 ? (
              <option value="">—</option>
            ) : (
              opts.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))
            )}
          </select>
        );
      } else {
        const current = values[f.name];
        const selected = opts.some((o) => o.value === current) ? current : (opts[0]?.value ?? "");
        control = (
          <select
            id={inputId}
            className={controlClass}
            value={selected}
            disabled={isReadonly || loadingOptions[f.name] === true || opts.length === 0}
            onChange={(e: any) => setFieldValue(f.name, e.target.value)}
          >
            {opts.length === 0 ? (
              <option value="">—</option>
            ) : (
              opts.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))
            )}
          </select>
        );
      }
    } else {
      control = (
        <input
          id={inputId}
          className={controlClass}
          type={f.secure ? "password" : "text"}
          value={values[f.name] ?? ""}
          disabled={isReadonly}
          placeholder={f.placeholder || undefined}
          autoComplete={f.secure ? "off" : undefined}
          onChange={(e: any) => setFieldValue(f.name, e.target.value)}
        />
      );
    }

    return (
      <div key={f.name} className="pde-decl-row">
        <FieldLabel htmlFor={inputId} label={f.label} required={isRequired} description={f.description} />
        <div className="pde-decl-control">
          {control}
          {warning}
        </div>
      </div>
    );
  };

  return (
    <form
      className="pde-form pde-decl-form"
      onSubmit={(e: any) => {
        e.preventDefault();
        setAttemptedSubmit(true);
        if (hasMissingRequired) return;
        void onSubmit(valuesRef.current);
      }}
    >
      <div className="pde-decl-fields">{fields.map((f) => renderField(f))}</div>

      <Btn primary type="submit" disabled={submitting}>
        {submitting ? "Starting..." : "Start run"}
      </Btn>
    </form>
  );
}
