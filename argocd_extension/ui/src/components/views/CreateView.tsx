import { PLACEHOLDER_KV_KEY, PLACEHOLDER_KV_VALUE } from "../../lib/constants";
import { apiJson } from "../../api/client";
import type { CreateForm, CreateMode, RetryForm } from "../../lib/types";
import { RunSettingsFields } from "./CatalogView";
import { Btn, Field, FieldBlock, KeyValueEditor } from "../ui";
import { DeclarativeRunTemplateFormView } from "./DeclarativeRunTemplateFormView";

export function CreateView(props: {
  mode: CreateMode;
  form: CreateForm;
  retryForm: RetryForm;
  profiles: any[];
  submitting: boolean;
  formReady?: boolean;
  templateId?: string;
  templateName?: string;
  templateKind?: "simple" | "declarative";
  declarativeContract?: any;
  adminMode?: boolean;
  onForm: (form: CreateForm) => void;
  onRetryForm: (form: RetryForm) => void;
  onSubmit: (declarativeValues?: Record<string, any>) => void | Promise<void>;
}) {
  const {
    mode,
    form,
    retryForm,
    profiles,
    submitting,
    formReady = true,
    templateId,
    templateName,
    templateKind,
    declarativeContract,
    adminMode = false,
  } = props;
  const isRetry = mode === "retry";
  const isDeclarative = !isRetry && templateKind === "declarative" && declarativeContract;

  return (
    <section>
      <div className="pde-toolbar">
        <h1>{isRetry ? "Retry run" : "New run"}</h1>
      </div>

      {!formReady ? (
        <p className="pde-muted">Loading...</p>
      ) : (
        <>
          {isRetry ? (
            <p className="pde-muted" style={{ marginTop: 0 }}>
              Retry vars from the previous run are prefilled. Leave unchanged to reuse them. Override env vars are reused
              automatically.
            </p>
          ) : null}

          {!isRetry && templateId ? (
            <p className="pde-muted" style={{ marginTop: 0 }}>
              Prefilling from template <span className="pde-mono">{templateName || templateId}</span>.
            </p>
          ) : null}

          {isDeclarative ? (
            <DeclarativeRunTemplateFormView
              contract={declarativeContract}
              submitting={submitting}
              onSubmit={(values) => props.onSubmit(values)}
              fetchOptions={async (fieldId, context) => {
                if (!templateId) return [];
                const data = await apiJson(`/run-templates/${templateId}/declarative/options`, {
                  method: "POST",
                  body: JSON.stringify({ fieldId, context }),
                });
                return (data.options || []).map((o: any) => ({ value: o.value, label: o.label }));
              }}
            />
          ) : (
            <form
              className="pde-form"
              onSubmit={(e: any) => {
                e.preventDefault();
                void props.onSubmit();
              }}
            >
              {isRetry ? (
                <>
                  <FieldBlock label="Retry vars">
                    <KeyValueEditor
                      pairs={retryForm.retry_vars}
                      onChange={(retry_vars) => props.onRetryForm({ ...retryForm, retry_vars })}
                      keyPlaceholder={PLACEHOLDER_KV_KEY}
                      valuePlaceholder={PLACEHOLDER_KV_VALUE}
                    />
                  </FieldBlock>
                  {adminMode ? (
                    <Field label="PDE image override (optional)">
                      <input
                        className="pde-input"
                        type="text"
                        value={retryForm.pde_image}
                        onChange={(e: any) => props.onRetryForm({ ...retryForm, pde_image: e.target.value })}
                        placeholder="Leave empty to reuse previous run image"
                        style={{ width: "100%" }}
                      />
                    </Field>
                  ) : null}
                </>
              ) : (
                <RunSettingsFields form={form} profiles={profiles} onForm={props.onForm} adminMode={adminMode} />
              )}

              <Btn primary type="submit" disabled={submitting || (!isRetry && !form.pipeline_data.trim())}>
                {submitting ? (isRetry ? "Starting retry..." : "Starting...") : isRetry ? "Start retry" : "Start run"}
              </Btn>
            </form>
          )}
        </>
      )}
    </section>
  );
}
