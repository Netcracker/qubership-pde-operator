import type { ProfileForm, ProfileSubview } from "../../lib/types";
import { fmt, pageRange } from "../../lib/format";
import { Btn, Field, Pager } from "../ui";

export function ProfilesView(props: {
  subview: ProfileSubview;
  profiles: any[];
  total: number;
  page: number;
  loading: boolean;
  formReady: boolean;
  profileForm: ProfileForm;
  submitting: boolean;
  onSubview: (next: ProfileSubview) => void;
  onPage: (page: number) => void;
  onRefresh: () => void;
  onEdit: (id: string) => void;
  onDelete: (id: string) => void;
  onForm: (form: ProfileForm) => void;
  onSubmitCreate: () => void;
  onSubmitUpdate: () => void;
}) {
  const { subview, profiles, total, page, loading, formReady, profileForm, submitting } = props;

  if (subview === "create" || subview === "edit") {
    const mode = subview;
    return (
      <section>
        <div className="pde-toolbar">
          <h1>{mode === "create" ? "New profile" : "Edit profile"}</h1>
          <Btn onClick={() => props.onSubview("list")} icon="arrow-left">
            Back to list
          </Btn>
        </div>
        {!formReady ? (
          <p className="pde-muted">Loading profile...</p>
        ) : (
          <ProfileFormView
            mode={mode}
            form={profileForm}
            submitting={submitting}
            onForm={props.onForm}
            onSubmit={mode === "create" ? props.onSubmitCreate : props.onSubmitUpdate}
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
          <Btn onClick={() => props.onSubview("create")} icon="plus">
            New profile
          </Btn>
          <Btn onClick={props.onRefresh} disabled={loading} icon="redo">
            Refresh
          </Btn>
        </div>
      </div>

      <div className="pde-table-wrap">
        <table>
          <thead>
            <tr>
              {["ID", "PDE image", "Created", "Updated", ""].map((label) => (
                <th key={label}>{label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {profiles.length === 0 ? (
              <tr>
                <td colSpan={5} className="pde-muted">
                  {loading ? "Loading..." : "No profiles."}
                </td>
              </tr>
            ) : (
              profiles.map((p: any) => (
                <tr key={p.id}>
                  <td>{p.id}</td>
                  <td className="pde-mono pde-wrap">{p.pde_image}</td>
                  <td className="pde-mono">{fmt(p.created_at)}</td>
                  <td className="pde-mono">{fmt(p.updated_at)}</td>
                  <td>
                    <div className="pde-row-actions">
                      <Btn small onClick={() => props.onEdit(p.id)} icon="pencil-alt">
                        Edit
                      </Btn>
                      <Btn small onClick={() => props.onDelete(p.id)} disabled={p.id === "default"} icon="times">
                        Delete
                      </Btn>
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

function ProfileFormView(props: {
  mode: "create" | "edit";
  form: ProfileForm;
  submitting: boolean;
  onForm: (form: ProfileForm) => void;
  onSubmit: () => void;
}) {
  const { mode, form, submitting } = props;
  return (
    <form
      className="pde-form"
      onSubmit={(e: any) => {
        e.preventDefault();
        props.onSubmit();
      }}
    >
      <Field label="Profile ID">
        <input
          className="pde-input"
          type="text"
          value={form.id}
          disabled={mode === "edit"}
          required
          placeholder="team-a"
          onChange={(e: any) => props.onForm({ ...form, id: e.target.value })}
          style={{ width: "100%" }}
        />
      </Field>
      <Field label="PDE image">
        <input
          className="pde-input"
          type="text"
          value={form.pde_image}
          required
          onChange={(e: any) => props.onForm({ ...form, pde_image: e.target.value })}
          style={{ width: "100%" }}
        />
      </Field>
      <Field label="Env vars (JSON)">
        <textarea
          className="pde-textarea"
          rows={8}
          value={form.envVarsText}
          required
          onChange={(e: any) => props.onForm({ ...form, envVarsText: e.target.value })}
        />
      </Field>
      <Field label="Job resources (JSON; {} = inherit operator defaults)">
        <textarea
          className="pde-textarea"
          rows={8}
          value={form.resourcesText}
          required
          placeholder='{} or {"requests":{"memory":"512Mi"}}'
          onChange={(e: any) => props.onForm({ ...form, resourcesText: e.target.value })}
        />
      </Field>
      <Btn primary type="submit" disabled={submitting}>
        {submitting ? (mode === "create" ? "Creating..." : "Saving...") : mode === "create" ? "Create profile" : "Save changes"}
      </Btn>
    </form>
  );
}
