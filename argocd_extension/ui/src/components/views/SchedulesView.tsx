import type { CreateForm, ScheduleForm, ScheduleSubview } from "../../lib/types";
import { fmt, pageRange } from "../../lib/format";
import { kvPairsToText } from "../../lib/runs";
import { OVERLAP_POLICIES, fmtAge, fmtFireCountdown, fmtLastFire } from "../../lib/schedules";
import { fetchDeclarativeOptions } from "../../lib/templates";
import { PipelineDataCard, VarsCard } from "../RunParamsCards";
import { Btn, Field, FieldBlock, Pager } from "../ui";
import { RunSettingsFields } from "./CatalogView";
import { DeclarativeRunTemplateFormView } from "./DeclarativeRunTemplateFormView";

export function SchedulesView(props: {
  subview: ScheduleSubview;
  items: any[];
  total: number;
  page: number;
  loading: boolean;
  formReady: boolean;
  form: ScheduleForm;
  submitting: boolean;
  profiles: any[];
  timezones: string[];
  declarativeContract: any | null;
  preview: string[];
  previewError: string;
  adminMode: boolean;
  onSubview: (next: ScheduleSubview) => void;
  onPage: (page: number) => void;
  onRefresh: () => void;
  onEdit: (id: string) => void;
  onDelete: (id: string, name: string) => void;
  onToggleEnabled: (schedule: any) => void;
  onRunNow: (id: string) => void;
  onHistory: (id: string) => void;
  onOpenRun: (runId: string) => void;
  onForm: (form: ScheduleForm) => void;
  onSubmitCreate: (declarativeValues?: Record<string, any>) => void;
  onSubmitUpdate: (declarativeValues?: Record<string, any>) => void;
}) {
  const { subview, items, total, page, loading, formReady, form, submitting } = props;

  if (subview === "create" || subview === "edit") {
    const mode = subview;
    return (
      <section>
        <div className="pde-toolbar">
          <h1>{mode === "create" ? "New scheduled run" : "Edit scheduled run"}</h1>
          <Btn onClick={() => props.onSubview("list")} icon="arrow-left">
            Back to list
          </Btn>
        </div>
        {!formReady ? (
          <p className="pde-muted">Loading schedule...</p>
        ) : (
          <ScheduleFormView
            key={mode === "edit" ? `edit-${form.id}` : "create"}
            mode={mode}
            form={form}
            profiles={props.profiles}
            timezones={props.timezones}
            submitting={submitting}
            adminMode={props.adminMode}
            declarativeContract={props.declarativeContract}
            preview={props.preview}
            previewError={props.previewError}
            onForm={props.onForm}
            onSubmit={(declarativeValues) =>
              mode === "create" ? props.onSubmitCreate(declarativeValues) : props.onSubmitUpdate(declarativeValues)
            }
          />
        )}
      </section>
    );
  }

  const pager = pageRange(total, page);

  return (
    <section>
      <div className="pde-toolbar pde-toolbar-end">
        <div className="pde-toolbar-right">
          {props.adminMode ? (
            <Btn onClick={() => props.onSubview("create")} icon="plus">
              New schedule
            </Btn>
          ) : null}
          <Btn onClick={props.onRefresh} disabled={loading} icon="redo">
            Refresh
          </Btn>
        </div>
      </div>

      <div className="pde-table-wrap">
        <table className="pde-schedules-table">
          <thead>
            <tr>
              {["Enabled", "Name", "Cron", "Timezone", "Next run", "Last run", ""].map((label) => (
                <th key={label}>{label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {items.length === 0 ? (
              <tr>
                <td colSpan={7} className="pde-muted">
                  {loading ? "Loading..." : "No scheduled runs yet."}
                </td>
              </tr>
            ) : (
              items.map((schedule: any) => (
                <tr key={schedule.id}>
                  <td>
                    <label
                      className="pde-toggle"
                      title={props.adminMode ? (schedule.enabled ? "Disable" : "Enable") : undefined}
                    >
                      <input
                        type="checkbox"
                        checked={!!schedule.enabled}
                        disabled={!props.adminMode}
                        onChange={() => props.onToggleEnabled(schedule)}
                      />
                    </label>
                  </td>
                  <td>
                    <div>{schedule.name}</div>
                    {schedule.description ? <div className="pde-muted pde-schedule-desc">{schedule.description}</div> : null}
                  </td>
                  <td className="pde-mono">{schedule.cron_expression}</td>
                  <td>{schedule.timezone}</td>
                  <td className="pde-mono">
                    {schedule.enabled ? fmtFireCountdown(schedule.next_fire_at) : <span className="pde-muted">paused</span>}
                  </td>
                  <td>
                    {schedule.last_fire_at ? (
                      <span
                        className="pde-schedule-last"
                        title={schedule.last_fire_error || fmt(schedule.last_fire_at)}
                      >
                        <span className="pde-muted">{fmtLastFire(schedule)}</span>
                        <span className="pde-muted">· {fmtAge(schedule.last_fire_at)}</span>
                        {schedule.last_run_id ? (
                          <button
                            type="button"
                            className="pde-nav-link pde-mono"
                            onClick={() => props.onOpenRun(String(schedule.last_run_id))}
                          >
                            view run
                          </button>
                        ) : null}
                      </span>
                    ) : (
                      <span className="pde-muted">never</span>
                    )}
                  </td>
                  <td>
                    <div className="pde-row-actions">
                      {props.adminMode ? (
                        <>
                          <Btn small onClick={() => props.onRunNow(String(schedule.id))} icon="play">
                            Run now
                          </Btn>
                          <Btn small onClick={() => props.onEdit(String(schedule.id))} icon="pencil-alt">
                            Edit
                          </Btn>
                        </>
                      ) : null}
                      <Btn small onClick={() => props.onHistory(String(schedule.id))} icon="history">
                        History
                      </Btn>
                      {props.adminMode ? (
                        <Btn small onClick={() => props.onDelete(String(schedule.id), schedule.name)} icon="times">
                          Delete
                        </Btn>
                      ) : null}
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <Pager
        page={page}
        total={total}
        loading={loading}
        hasPrev={pager.hasPrev}
        hasNext={pager.hasNext}
        label={pager.label}
        onPage={props.onPage}
      />
    </section>
  );
}

function ScheduleFormView(props: {
  mode: "create" | "edit";
  form: ScheduleForm;
  profiles: any[];
  timezones: string[];
  submitting: boolean;
  adminMode: boolean;
  declarativeContract: any | null;
  preview: string[];
  previewError: string;
  onForm: (form: ScheduleForm) => void;
  onSubmit: (declarativeValues?: Record<string, any>) => void;
}) {
  const { mode, form, timezones, submitting, declarativeContract } = props;
  const isDeclarative = !!declarativeContract;
  const templateId = form.templateId;
  const [runParamsEditable, setRunParamsEditable] = React.useState(mode === "create");
  // The loaded run parameters, restored when leaving the run-parameter editor without saving.
  const [runSnapshot] = React.useState(() => form.run);
  const runParamsLocked = mode === "edit" && !runParamsEditable;

  const patchRun = (run: CreateForm) => props.onForm({ ...form, run });

  const fields = (
    <>
      <label className="pde-toggle">
        <input
          type="checkbox"
          checked={form.enabled}
          onChange={(e: any) => props.onForm({ ...form, enabled: e.target.checked })}
        />
        Enabled
      </label>

      <Field label="Name">
        <input
          className="pde-input"
          type="text"
          value={form.name}
          required
          placeholder="Nightly deploy"
          onChange={(e: any) => props.onForm({ ...form, name: e.target.value })}
          style={{ width: "100%" }}
        />
      </Field>

      <Field label="Description">
        <input
          className="pde-input"
          type="text"
          value={form.description}
          placeholder="Optional"
          onChange={(e: any) => props.onForm({ ...form, description: e.target.value })}
          style={{ width: "100%" }}
        />
      </Field>

      <div className="pde-form-row">
        <Field label="Cron expression">
          <input
            className="pde-input pde-mono"
            type="text"
            value={form.cronExpression}
            required
            placeholder="0 2 * * *"
            onChange={(e: any) => props.onForm({ ...form, cronExpression: e.target.value })}
            style={{ width: "100%" }}
          />
        </Field>
        <Field label="Timezone">
          <select
            className="pde-select"
            value={form.timezone}
            onChange={(e: any) => props.onForm({ ...form, timezone: e.target.value })}
          >
            {timezones.map((zone) => (
              <option key={zone} value={zone}>
                {zone}
              </option>
            ))}
          </select>
        </Field>
        <Field label="If the previous run is still active">
          <select
            className="pde-select"
            value={form.overlapPolicy}
            onChange={(e: any) => props.onForm({ ...form, overlapPolicy: e.target.value })}
          >
            {OVERLAP_POLICIES.map((policy) => (
              <option key={policy.value} value={policy.value}>
                {policy.label}
              </option>
            ))}
          </select>
        </Field>
      </div>

      <FieldBlock label="Next fires">
        {props.previewError ? (
          <span className="pde-error pde-schedule-preview-error">{props.previewError}</span>
        ) : props.preview.length ? (
          <span className="pde-schedule-preview">{props.preview.map((iso) => fmt(iso)).join("  ·  ")}</span>
        ) : (
          <span className="pde-muted">Enter a cron expression to preview the next fire times.</span>
        )}
      </FieldBlock>

    </>
  );

  if (isDeclarative) {
    // DeclarativeRunTemplateFormView renders its own <form>; nesting it breaks submit handling.
    return (
      <>
        <div className="pde-form">{fields}</div>
        <DeclarativeRunTemplateFormView
          contract={declarativeContract}
          submitting={submitting}
          submitLabel={mode === "create" ? "Create schedule" : "Save changes"}
          fetchOptions={(fieldId, context) => fetchDeclarativeOptions(templateId, fieldId, context)}
          onSubmit={async (values) => props.onSubmit(values)}
        />
      </>
    );
  }

  const runParamsSection = runParamsLocked ? (
    <div className="pde-field">
      <RunParamsReadOnly run={form.run} profiles={props.profiles} />
      <div className="pde-row-actions">
        <Btn onClick={() => setRunParamsEditable(true)} icon="pencil-alt">
          Edit run parameters
        </Btn>
      </div>
    </div>
  ) : (
    <>
      <RunSettingsFields form={form.run} profiles={props.profiles} onForm={patchRun} adminMode={props.adminMode} />
      {mode === "edit" ? (
        <div className="pde-row-actions">
          <Btn
            onClick={() => {
              props.onForm({ ...form, run: runSnapshot });
              setRunParamsEditable(false);
            }}
            icon="times"
          >
            Cancel run parameter changes
          </Btn>
        </div>
      ) : null}
    </>
  );

  return (
    <form
      className="pde-form"
      onSubmit={(e: any) => {
        e.preventDefault();
        props.onSubmit();
      }}
    >
      {fields}
      {runParamsSection}
      <Btn primary type="submit" disabled={submitting}>
        {submitting
          ? mode === "create"
            ? "Creating..."
            : "Saving..."
          : mode === "create"
            ? "Create schedule"
            : "Save changes"}
      </Btn>
    </form>
  );
}

function RunParamsReadOnly(props: { run: CreateForm; profiles: any[] }) {
  const { run, profiles } = props;
  const profile = profiles.find((p: any) => p.id === run.profile_id);
  const rows = [
    { label: "Profile", value: run.profile_id || "default" },
    { label: "PDE image", value: run.pde_image || profile?.pde_image || "—" },
    { label: "Dry run", value: run.is_dry_run ? "true" : "false" },
    { label: "Log level", value: run.log_level || "—" },
  ];
  return (
    <>
      <div className="pde-var-list">
        {rows.map((row) => (
          <label className="pde-var-row" key={row.label}>
            <span className="pde-var-label">{row.label}</span>
            <input className="pde-input pde-var-value" type="text" value={row.value} readOnly />
          </label>
        ))}
      </div>
      <div className="pde-detail-sections pde-schedule-params-cards">
        <PipelineDataCard text={run.pipeline_data} />
        <VarsCard title="Pipeline vars" text={kvPairsToText(run.pipeline_vars)} />
        <VarsCard title="Secure vars" text={kvPairsToText(run.pipeline_vars_secure)} />
        <VarsCard title="Env vars" text={kvPairsToText(run.env_vars)} />
      </div>
    </>
  );
}
