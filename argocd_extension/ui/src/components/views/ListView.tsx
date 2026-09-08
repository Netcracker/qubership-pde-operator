import { fmt, fmtDuration, pageRange, shortId } from "../../lib/format";
import { canCancel, canRetry } from "../../lib/runs";
import { Badge, Btn, Field, Pager } from "../ui";

export function ListView(props: {
  runs: any[];
  total: number;
  page: number;
  searchQuery: string;
  templateFilter: string;
  templateName?: string;
  loading: boolean;
  canWrite?: boolean;
  onSearch: (v: string) => void;
  onClearTemplate: () => void;
  onPage: (page: number) => void;
  onRefresh: () => void;
  onOpen: (id: string) => void;
  onCancel: (id: string) => void;
  onRetry: (id: string) => void;
}) {
  const { runs, total, page, searchQuery, templateFilter, templateName, loading, canWrite = true } = props;
  const pager = pageRange(total, page);
  const title = templateFilter ? `History for "${templateName || templateFilter}"` : "Pipeline Runs";

  return (
    <section>
      <div className="pde-toolbar">
        <h1>{title}</h1>
        <div className="pde-toolbar-right">
          {templateFilter ? (
            <Btn onClick={props.onClearTemplate} icon="times">
              Clear
            </Btn>
          ) : null}
          <Btn onClick={props.onRefresh} disabled={loading} icon="redo">
            Refresh
          </Btn>
        </div>
      </div>

      <div className="pde-filters">
        <Field label="Search">
          <input
            className="pde-input"
            type="search"
            value={searchQuery}
            placeholder="Search status, profile, or name..."
            onChange={(e: any) => props.onSearch(e.target.value)}
            style={{ minWidth: 260, width: "100%" }}
          />
        </Field>
      </div>

      <div className="pde-table-wrap">
        <table>
          <thead>
            <tr>
              {["Status", "ID", "Profile", "Name", "Created", "Finished", "Duration", ""].map((label) => (
                <th key={label}>{label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {runs.length === 0 ? (
              <tr>
                <td colSpan={8} className="pde-muted">
                  {loading ? "Loading..." : "No runs yet."}
                </td>
              </tr>
            ) : (
              runs.map((run: any) => (
                <tr key={String(run.id)} className="pde-clickable" onClick={() => props.onOpen(String(run.id))}>
                  <td>
                    <Badge status={run.status} />
                  </td>
                  <td className="pde-mono">{shortId(run.id)}</td>
                  <td>{run.profile_id || "—"}</td>
                  <td>{run.name || "—"}</td>
                  <td className="pde-mono">{fmt(run.created_at)}</td>
                  <td className="pde-mono">{fmt(run.finished_at)}</td>
                  <td className="pde-mono">{fmtDuration(run)}</td>
                  <td onClick={(e: any) => e.stopPropagation()}>
                    {canWrite ? (
                      <div className="pde-row-actions">
                        <Btn small disabled={!canCancel(run)} onClick={() => props.onCancel(String(run.id))} icon="times-circle">
                          Cancel
                        </Btn>
                        <Btn small disabled={!canRetry(run)} onClick={() => props.onRetry(String(run.id))} icon="redo">
                          Retry
                        </Btn>
                      </div>
                    ) : null}
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
