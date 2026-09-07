import React from "react";
import { PLACEHOLDER_KV_KEY, PLACEHOLDER_KV_VALUE, PLACEHOLDER_PIPELINE_DATA } from "../../lib/constants";
import type { CatalogSubview, CreateForm, TemplateForm } from "../../lib/types";
import { fmt, pageRange } from "../../lib/format";
import { Btn, Field, FieldBlock, KeyValueEditor, Pager, TemplateKindBadge } from "../ui";

export function CatalogView(props: {
  subview: CatalogSubview;
  adminMode: boolean;
  canWrite?: boolean;
  templates: any[];
  total: number;
  page: number;
  loading: boolean;
  formReady: boolean;
  query: string;
  tagFilter: string;
  templateForm: TemplateForm;
  profiles: any[];
  submitting: boolean;
  onQuery: (v: string) => void;
  onTagFilter: (v: string) => void;
  onSubview: (next: CatalogSubview) => void;
  onPage: (page: number) => void;
  onRefresh: () => void;
  onOpen: (id: string) => void;
  onHistory: (id: string) => void;
  onEdit: (id: string) => void;
  onDelete: (id: string, name?: string) => void;
  onForm: (form: TemplateForm) => void;
  onSubmitCreate: () => void;
  onSubmitUpdate: () => void;
  uploadingDeclarative?: boolean;
  onUploadDeclarativeTemplate?: (file: File) => void;
}) {
  const {
    subview,
    templates,
    total,
    page,
    loading,
    formReady,
    query,
    tagFilter,
    templateForm,
    profiles,
    submitting,
    canWrite = true,
  } = props;

  if ((subview === "create" || subview === "edit") && !props.adminMode) {
    return null;
  }

  if (subview === "create" || subview === "edit") {
    const mode = subview;
    return (
      <section>
        <div className="pde-toolbar">
          <h1>{mode === "create" ? "New run template" : "Edit run template"}</h1>
          <Btn onClick={() => props.onSubview("list")} icon="arrow-left">
            Back to catalog
          </Btn>
        </div>
        {!formReady ? (
          <p className="pde-muted">Loading template...</p>
        ) : (
          <TemplateFormView
            mode={mode}
            form={templateForm}
            profiles={profiles}
            submitting={submitting}
            onForm={props.onForm}
            onSubmit={mode === "create" ? props.onSubmitCreate : props.onSubmitUpdate}
          />
        )}
      </section>
    );
  }

  const pager = pageRange(total, page);
  const uploadInputRef = React.useRef<HTMLInputElement>(null);

  return (
    <section>
      <div className="pde-toolbar pde-toolbar-end">
        <div className="pde-toolbar-right">
          {props.adminMode ? (
            <Btn onClick={() => props.onSubview("create")} icon="plus">
              New Simple Template
            </Btn>
          ) : null}
          {props.adminMode && props.onUploadDeclarativeTemplate ? (
            <>
              <Btn
                onClick={() => uploadInputRef.current?.click()}
                disabled={props.uploadingDeclarative}
                icon="file-alt"
              >
                New Declarative Template
              </Btn>
              <input
                ref={uploadInputRef}
                type="file"
                accept=".yaml,.yml"
                style={{ display: "none" }}
                onChange={(e: any) => {
                  const file: File | undefined = e.target.files?.[0];
                  if (!file || !props.onUploadDeclarativeTemplate) return;
                  props.onUploadDeclarativeTemplate(file);
                  e.target.value = "";
                }}
              />
            </>
          ) : null}
          <Btn onClick={props.onRefresh} disabled={loading} icon="redo">
            Refresh
          </Btn>
        </div>
      </div>

      <div className="pde-toolbar" style={{ marginTop: 0 }}>
        <input
          className="pde-input"
          type="search"
          value={query}
          placeholder="Search name, id, description, tags..."
          onChange={(e: any) => props.onQuery(e.target.value)}
          style={{ minWidth: 220, flex: 1 }}
        />
        <input
          className="pde-input"
          type="text"
          value={tagFilter}
          placeholder="Exact tag"
          onChange={(e: any) => props.onTagFilter(e.target.value)}
          style={{ width: 140 }}
        />
      </div>

      <div className="pde-table-wrap">
        <table>
          <thead>
            <tr>
              {["Name", "Tags", "Profile", "Updated", ""].map((label) => (
                <th key={label || "actions"}>{label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {templates.length === 0 ? (
              <tr>
                <td colSpan={5} className="pde-muted">
                  {loading ? "Loading..." : "No run templates yet."}
                </td>
              </tr>
            ) : (
              templates.map((t: any) => (
                <tr
                  key={t.id}
                  className={canWrite ? "pde-clickable" : undefined}
                  onClick={canWrite ? () => props.onOpen(t.id) : undefined}
                >
                  <td>
                    <div className="pde-template-title">
                      <TemplateKindBadge kind={t.template_kind} />
                      <div>
                        <div>{t.name}</div>
                        {t.description ? <div className="pde-muted pde-wrap">{t.description}</div> : null}
                      </div>
                    </div>
                  </td>
                  <td>{(t.tags || []).join(", ") || "—"}</td>
                  <td className="pde-mono">{t.profile_id}</td>
                  <td className="pde-mono">{fmt(t.updated_at)}</td>
                  <td onClick={(e: any) => e.stopPropagation()}>
                    <div className="pde-row-actions">
                      {canWrite ? (
                        <Btn small onClick={(e: any) => { e.stopPropagation(); props.onOpen(t.id); }} icon="play">
                          Run
                        </Btn>
                      ) : null}
                      <Btn
                        small
                        onClick={(e: any) => {
                          e.stopPropagation();
                          props.onHistory(t.id);
                        }}
                        icon="history"
                      >
                        History
                      </Btn>
                      {props.adminMode && t.template_kind !== "declarative" ? (
                        <Btn small onClick={() => props.onEdit(t.id)} icon="pencil-alt">
                          Edit
                        </Btn>
                      ) : null}
                      {props.adminMode ? (
                        <Btn small onClick={() => props.onDelete(t.id, t.name)} icon="times">
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

function TemplateFormView(props: {
  mode: "create" | "edit";
  form: TemplateForm;
  profiles: any[];
  submitting: boolean;
  onForm: (form: TemplateForm) => void;
  onSubmit: () => void;
}) {
  const { mode, form, profiles, submitting } = props;
  return (
    <form
      className="pde-form"
      onSubmit={(e: any) => {
        e.preventDefault();
        props.onSubmit();
      }}
    >
      <Field label="Name">
        <input
          className="pde-input"
          type="text"
          value={form.name}
          required
          onChange={(e: any) => props.onForm({ ...form, name: e.target.value })}
          style={{ width: "100%" }}
        />
      </Field>
      <Field label="Description">
        <textarea
          className="pde-textarea"
          rows={2}
          value={form.description}
          onChange={(e: any) => props.onForm({ ...form, description: e.target.value })}
        />
      </Field>
      <Field label="Tags (comma-separated)">
        <input
          className="pde-input"
          type="text"
          value={form.tagsText}
          placeholder="deploy, nightly"
          onChange={(e: any) => props.onForm({ ...form, tagsText: e.target.value })}
          style={{ width: "100%" }}
        />
      </Field>
      <RunSettingsFields
        form={form}
        profiles={profiles}
        onForm={(next) => props.onForm({ ...form, ...next })}
        adminMode
      />
      <Btn primary type="submit" disabled={submitting || !form.pipeline_data.trim() || !form.name.trim()}>
        {submitting ? "Saving..." : mode === "create" ? "Create template" : "Save template"}
      </Btn>
    </form>
  );
}

/** Shared create-run / template settings fields. */
export function RunSettingsFields(props: {
  form: CreateForm;
  profiles: any[];
  onForm: (form: CreateForm) => void;
  adminMode?: boolean;
}) {
  const { form, profiles, adminMode = false } = props;
  return (
    <>
      <div className="pde-form-row pde-form-row-top">
        <Field label="Profile">
          <select
            className="pde-select"
            value={form.profile_id}
            onChange={(e: any) => props.onForm({ ...form, profile_id: e.target.value })}
          >
            {profiles.length ? (
              profiles.map((p: any) => (
                <option key={p.id} value={p.id}>
                  {p.id}
                </option>
              ))
            ) : (
              <option value="default">default</option>
            )}
          </select>
        </Field>
        <label className="pde-toggle">
          <input
            type="checkbox"
            checked={form.is_dry_run}
            onChange={(e: any) => props.onForm({ ...form, is_dry_run: e.target.checked })}
          />
          Dry run
        </label>
        <Field label="Log level">
          <select
            className="pde-select"
            value={form.log_level}
            onChange={(e: any) => props.onForm({ ...form, log_level: e.target.value })}
          >
            {["INFO", "DEBUG", "WARNING", "ERROR"].map((lvl) => (
              <option key={lvl} value={lvl}>
                {lvl}
              </option>
            ))}
          </select>
        </Field>
      </div>
      <Field label="Pipeline data">
        <textarea
          className="pde-textarea"
          rows={3}
          required
          value={form.pipeline_data}
          onChange={(e: any) => props.onForm({ ...form, pipeline_data: e.target.value })}
          placeholder={PLACEHOLDER_PIPELINE_DATA}
        />
      </Field>
      <FieldBlock label="Pipeline vars">
        <KeyValueEditor
          pairs={form.pipeline_vars}
          onChange={(pipeline_vars) => props.onForm({ ...form, pipeline_vars })}
          keyPlaceholder={PLACEHOLDER_KV_KEY}
          valuePlaceholder={PLACEHOLDER_KV_VALUE}
        />
      </FieldBlock>
      <FieldBlock label="Pipeline vars (secure)">
        <KeyValueEditor
          pairs={form.pipeline_vars_secure}
          onChange={(pipeline_vars_secure) => props.onForm({ ...form, pipeline_vars_secure })}
          keyPlaceholder={PLACEHOLDER_KV_KEY}
          valuePlaceholder={PLACEHOLDER_KV_VALUE}
        />
      </FieldBlock>
      {adminMode ? (
        <>
          <FieldBlock label="Override env vars (optional, highest priority)">
            <KeyValueEditor
              pairs={form.env_vars}
              onChange={(env_vars) => props.onForm({ ...form, env_vars })}
              keyPlaceholder={PLACEHOLDER_KV_KEY}
              valuePlaceholder={PLACEHOLDER_KV_VALUE}
            />
          </FieldBlock>
          <Field label="PDE image override (optional)">
            <input
              className="pde-input"
              type="text"
              value={form.pde_image}
              onChange={(e: any) => props.onForm({ ...form, pde_image: e.target.value })}
              placeholder="Leave empty to use profile image"
              style={{ width: "100%" }}
            />
          </Field>
        </>
      ) : null}
    </>
  );
}
