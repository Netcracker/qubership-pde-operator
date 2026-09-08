import type { DetailSubview, LogStatus, ReportStatus } from "../../lib/types";
import { ansiToHtml } from "../../lib/ansi";
import { fmt, fmtDuration, fmtTemplateRef, parseRunProgress, scrollLogToEnd } from "../../lib/format";
import { canCancel, canRetry } from "../../lib/runs";
import { PipelineViewer } from "../pipeline-viewer/PipelineViewer";
import { Badge, Btn, FinishCodeBadge, ProgressBar } from "../ui";

function MetaItem({ label, children, wide }: { label: string; children: any; wide?: boolean }) {
  return (
    <div className={wide ? "pde-wide" : undefined}>
      <dt>{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}

function MetaSubsection({ children }: { children: any }) {
  return (
    <div className="pde-detail-subsection">
      <dl className="pde-meta pde-meta-compact">{children}</dl>
    </div>
  );
}

function DetailMetaCard({ children }: { children: any }) {
  return (
    <section className="pde-detail-card">
      <div className="pde-detail-grid">{children}</div>
    </section>
  );
}

function LogConsole({ text, logStatus }: { text: string; logStatus: LogStatus }) {
  const ref = React.useRef<HTMLPreElement>(null);
  const html = React.useMemo(() => ansiToHtml(text || ""), [text]);

  React.useEffect(() => {
    if (logStatus !== "ready" || !text) return;
    scrollLogToEnd(() => ref.current);
  }, [text, logStatus]);

  return <pre ref={ref} className="pde-log" dangerouslySetInnerHTML={{ __html: html }} />;
}

function MetaSection({ children }: { children: any }) {
  return (
    <section className="pde-detail-card">
      <dl className="pde-meta">{children}</dl>
    </section>
  );
}

function ToolbarSep() {
  return (
    <span className="pde-tab-sep" aria-hidden="true">
      |
    </span>
  );
}

function DetailTabBar(props: { subview: DetailSubview; onSubview: (s: DetailSubview) => void }) {
  const items: { id: DetailSubview; label: string }[] = [
    { id: "info", label: "Info" },
    { id: "logs", label: "Logs" },
    { id: "viewer", label: "Viewer" },
  ];
  return (
    <nav className="pde-tabs pde-detail-tabs">
      {items.map((item) => (
        <button
          key={item.id}
          type="button"
          className={`pde-tab${props.subview === item.id ? " is-active" : ""}`}
          onClick={() => props.onSubview(item.id)}
        >
          {item.label}
        </button>
      ))}
    </nav>
  );
}

function NavLink(props: { onClick: () => void; children: any }) {
  return (
    <button type="button" className="pde-nav-link pde-mono pde-wrap" onClick={props.onClick}>
      {props.children}
    </button>
  );
}

export function DetailView(props: {
  detail: any;
  loading: boolean;
  adminMode?: boolean;
  canWrite?: boolean;
  subview: DetailSubview;
  logText: string;
  logStatus: LogStatus;
  logError: string;
  report: any;
  reportStatus: ReportStatus;
  reportError: string;
  onRefresh: () => void;
  onSubview: (s: DetailSubview) => void;
  onOpenRetryOf: (id: string) => void;
  onOpenFromTemplate: (id: string) => void;
  onCancel: (id: string) => void;
  onRetry: (id: string) => void;
  onDownload: (runId: string, kind: string) => void;
}) {
  const { detail, loading, logText, logStatus, logError, subview, adminMode = false, canWrite = true } = props;

  if (!detail && loading) return <p className="pde-muted">Loading run...</p>;
  if (!detail) return <p className="pde-muted">Select a run from the list.</p>;

  const hasRetryVars = !!detail.retry_vars?.trim();
  const progress = parseRunProgress(detail.progress_json);

  return (
    <section>
      <div className="pde-toolbar">
        <h1 className="pde-detail-title">
          Run <span className="pde-mono">{String(detail.id)}</span>
          <Badge status={detail.status} />
          {progress ? <ProgressBar progress={progress} compact /> : null}
        </h1>
        <div className="pde-toolbar-right">
          <Btn onClick={props.onRefresh} disabled={loading} icon="redo">
            Refresh
          </Btn>
          <ToolbarSep />
          {adminMode ? (
            <>
              <Btn onClick={() => props.onDownload(String(detail.id), "log")} icon="file-alt">
                Log
              </Btn>
              <Btn onClick={() => props.onDownload(String(detail.id), "state")} icon="database">
                State
              </Btn>
            </>
          ) : null}
          <Btn onClick={() => props.onDownload(String(detail.id), "x_debug")} icon="bug">
            {adminMode ? "x_debug" : "Get troubleshooting package"}
          </Btn>
          {adminMode ? (
            <Btn onClick={() => props.onDownload(String(detail.id), "report")} icon="file">
              Report
            </Btn>
          ) : null}
          <ToolbarSep />
          {canWrite ? (
            <>
              <Btn onClick={() => props.onCancel(String(detail.id))} disabled={!canCancel(detail)} icon="times-circle">
                Cancel
              </Btn>
              <Btn onClick={() => props.onRetry(String(detail.id))} disabled={!canRetry(detail)} icon="redo">
                Retry
              </Btn>
            </>
          ) : null}
        </div>
      </div>

      <DetailTabBar subview={subview} onSubview={props.onSubview} />

      {subview === "info" ? (
        <div className="pde-detail-sections">
          <DetailMetaCard>
            <MetaSubsection>
              <MetaItem label="Name">{detail.name || "—"}</MetaItem>
              <MetaItem label="Status">
                <span className="pde-status-badges">
                  <Badge status={detail.status} />
                  {detail.finish_code ? (
                    <FinishCodeBadge code={detail.finish_code} message={detail.finish_message} />
                  ) : null}
                </span>
              </MetaItem>
              <MetaItem label="Profile">{detail.profile_id || "—"}</MetaItem>
              <MetaItem label="PDE image" wide>
                <span className="pde-mono pde-wrap">{detail.pde_image || "—"}</span>
              </MetaItem>
            </MetaSubsection>

            <MetaSubsection>
              <MetaItem label="Created">
                <span className="pde-mono">{fmt(detail.created_at)}</span>
              </MetaItem>
              <MetaItem label="Started">
                <span className="pde-mono">{fmt(detail.started_at)}</span>
              </MetaItem>
              <MetaItem label="Finished">
                <span className="pde-mono">{fmt(detail.finished_at)}</span>
              </MetaItem>
              <MetaItem label="Duration">
                <span className="pde-mono">{fmtDuration(detail)}</span>
              </MetaItem>
            </MetaSubsection>

            <MetaSubsection>
              <MetaItem label="Dry run">{detail.is_dry_run ? "Yes" : "No"}</MetaItem>
              <MetaItem label="Log level">{detail.log_level || "—"}</MetaItem>
            </MetaSubsection>

            <MetaSubsection>
              <MetaItem label="From template">
                {detail.created_from_template_id ? (
                  <NavLink onClick={() => props.onOpenFromTemplate(String(detail.created_from_template_id))}>
                    {fmtTemplateRef(detail.created_from_template_id, detail.created_from_template_name)}
                  </NavLink>
                ) : (
                  "—"
                )}
              </MetaItem>
              <MetaItem label="Retry of">
                {detail.retry_of_run_id ? (
                  <NavLink onClick={() => props.onOpenRetryOf(String(detail.retry_of_run_id))}>
                    {String(detail.retry_of_run_id)}
                  </NavLink>
                ) : (
                  "—"
                )}
              </MetaItem>
            </MetaSubsection>
          </DetailMetaCard>

          <MetaSection>
            <MetaItem label="Pipeline data" wide>
              <pre className="pde-detail-pre">{detail.pipeline_data || "—"}</pre>
            </MetaItem>
            <MetaItem label="Pipeline vars" wide>
              <pre className="pde-detail-pre">{detail.pipeline_vars || "—"}</pre>
            </MetaItem>
            {hasRetryVars ? (
              <MetaItem label="Retry vars" wide>
                <pre className="pde-detail-pre">{detail.retry_vars}</pre>
              </MetaItem>
            ) : null}
          </MetaSection>
        </div>
      ) : null}

      {subview === "logs" ? (
        <div className="pde-panel">
          {logStatus === "loading" || logStatus === "idle" ? <p className="pde-muted">Loading logs...</p> : null}
          {logStatus === "not_ready" ? (
            <p className="pde-muted">Logs not ready yet — the Job may still be running or has not uploaded artifacts.</p>
          ) : null}
          {logStatus === "error" ? <p className="pde-error">{logError}</p> : null}
          {logStatus === "ready" ? <LogConsole text={logText || ""} logStatus={logStatus} /> : null}
        </div>
      ) : null}

      {subview === "viewer" ? (
        <div className="pde-panel pde-panel-viewer">
          {props.reportStatus === "loading" || props.reportStatus === "idle" ? (
            <p className="pde-muted">Loading pipeline report...</p>
          ) : null}
          {props.reportStatus === "not_ready" ? (
            <p className="pde-muted">Report not ready yet — the Job may still be running or has not uploaded artifacts.</p>
          ) : null}
          {props.reportStatus === "error" ? <p className="pde-error">{props.reportError}</p> : null}
          {props.reportStatus === "ready" && props.report ? <PipelineViewer report={props.report} /> : null}
        </div>
      ) : null}
    </section>
  );
}
