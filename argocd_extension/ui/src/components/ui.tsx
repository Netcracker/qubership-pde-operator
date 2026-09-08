import type { RunProgress } from "../lib/format";
import type { KeyValuePair, Tab } from "../lib/types";

export function ProgressBar({ progress, compact }: { progress: RunProgress; compact?: boolean }) {
  return (
    <div
      className={`pde-progress${compact ? " pde-progress-compact" : ""}`}
      title={`${progress.percent}% (${progress.completed}/${progress.total})`}
    >
      <div className="pde-progress-track">
        <div className="pde-progress-fill" style={{ width: `${progress.percent}%` }} />
        <span className="pde-progress-pct">{progress.percent}%</span>
      </div>
      <span className="pde-progress-count">
        {progress.completed}/{progress.total}
      </span>
    </div>
  );
}

export function Badge({ status }: { status: string }) {
  return (
    <span className="pde-badge" data-status={status || undefined}>
      {status || "—"}
    </span>
  );
}

export function FinishCodeBadge({ code, message }: { code?: string | null; message?: string | null }) {
  if (!code) return <span>—</span>;
  return (
    <span className="pde-badge pde-badge-code" title={message || undefined}>
      {code}
    </span>
  );
}

export function TemplateKindBadge({ kind }: { kind?: string | null }) {
  const isDeclarative = kind === "declarative";
  const label = isDeclarative ? "Declarative" : "Simple";
  const icon = isDeclarative ? "sitemap" : "play";
  return (
    <span className="pde-kind-badge" data-kind={isDeclarative ? "declarative" : "simple"} title={label}>
      <i className={`fa fa-${icon}`} aria-hidden="true" />
      <span>{label}</span>
    </span>
  );
}

export function Btn(props: {
  onClick?: () => void;
  disabled?: boolean;
  primary?: boolean;
  small?: boolean;
  icon?: string;
  type?: "button" | "submit";
  children: any;
}) {
  const className = ["pde-btn", props.primary ? "pde-btn-primary" : "", props.small ? "pde-btn-sm" : ""]
    .filter(Boolean)
    .join(" ");
  const icon = !props.primary && props.icon ? props.icon : null;
  return (
    <button type={props.type || "button"} className={className} onClick={props.onClick} disabled={props.disabled}>
      {icon ? <i className={`fa fa-${icon}`} aria-hidden="true" /> : null}
      {props.children}
    </button>
  );
}

export function Field({ label, children }: { label: string; children: any }) {
  return (
    <label className="pde-field">
      {label}
      {children}
    </label>
  );
}

/** Block field (not a <label>) for controls with multiple inputs. */
export function FieldBlock({ label, children }: { label: string; children: any }) {
  return (
    <div className="pde-field">
      <span>{label}</span>
      {children}
    </div>
  );
}

export function KeyValueEditor(props: {
  pairs: KeyValuePair[];
  onChange: (pairs: KeyValuePair[]) => void;
  keyPlaceholder?: string;
  valuePlaceholder?: string;
}) {
  const { pairs, keyPlaceholder = "KEY", valuePlaceholder = "value" } = props;

  const updateAt = (index: number, patch: Partial<KeyValuePair>) => {
    props.onChange(pairs.map((p, i) => (i === index ? { ...p, ...patch } : p)));
  };

  return (
    <div className="pde-kv-list">
      {pairs.map((pair, index) => (
        <div className="pde-kv-row" key={index}>
          <input
            className="pde-input pde-kv-key"
            type="text"
            value={pair.key}
            placeholder={keyPlaceholder}
            onChange={(e: any) => updateAt(index, { key: e.target.value })}
            aria-label="Variable key"
          />
          <span className="pde-kv-eq" aria-hidden="true">
            =
          </span>
          <input
            className="pde-input pde-kv-value"
            type="text"
            value={pair.value}
            placeholder={valuePlaceholder}
            onChange={(e: any) => updateAt(index, { value: e.target.value })}
            aria-label="Variable value"
          />
          <button
            type="button"
            className="pde-btn pde-btn-sm pde-kv-remove"
            onClick={() => props.onChange(pairs.filter((_, i) => i !== index))}
            aria-label="Remove variable"
            title="Remove"
          >
            ×
          </button>
        </div>
      ))}
      <Btn small type="button" onClick={() => props.onChange([...pairs, { key: "", value: "" }])}>
        +
      </Btn>
    </div>
  );
}

export function StatusMessage(props: { kind: "flash" | "error"; text: string; onDismiss: () => void }) {
  if (!props.text) return null;
  return (
    <p className={props.kind === "flash" ? "pde-flash" : "pde-error"} onClick={props.onDismiss}>
      {props.text}
    </p>
  );
}

export function AutoRefreshToggle(props: { checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <label className="pde-toggle">
      <input type="checkbox" checked={props.checked} onChange={(e: any) => props.onChange(e.target.checked)} />
      Auto-refresh
    </label>
  );
}

export function Pager(props: {
  page: number;
  total: number;
  loading?: boolean;
  hasPrev: boolean;
  hasNext: boolean;
  label: string;
  onPage: (page: number) => void;
}) {
  const { page, loading, hasPrev, hasNext, label } = props;
  return (
    <div className="pde-pager">
      <Btn onClick={() => props.onPage(page - 1)} disabled={!hasPrev || loading} icon="chevron-left">
        Prev
      </Btn>
      <span className="pde-muted">{label}</span>
      <Btn onClick={() => props.onPage(page + 1)} disabled={!hasNext || loading} icon="chevron-right">
        Next
      </Btn>
    </div>
  );
}

export function TabBar(props: {
  tab: Tab;
  detailEnabled: boolean;
  adminMode?: boolean;
  canWrite?: boolean;
  onTab: (t: Tab) => void;
}) {
  const canWrite = props.canWrite !== false;
  const groups: { id: Tab; label: string; disabled?: boolean }[][] = [
    [{ id: "catalog", label: "Catalog" }],
    [
      ...(canWrite ? [{ id: "create" as Tab, label: "Create" }] : []),
      { id: "detail", label: "Details", disabled: !props.detailEnabled },
      { id: "list", label: "List" },
    ],
    [
      ...(props.adminMode ? [{ id: "profiles" as Tab, label: "Profiles" }] : []),
      { id: "settings", label: "Settings" },
    ],
  ];
  return (
    <nav className="pde-tabs">
      {groups.map((group, gi) => (
        <React.Fragment key={gi}>
          {gi > 0 ? <span className="pde-tab-sep" aria-hidden="true">|</span> : null}
          {group.map((item) => (
            <button
              key={item.id}
              type="button"
              className={`pde-tab${props.tab === item.id ? " is-active" : ""}`}
              disabled={item.disabled}
              onClick={() => props.onTab(item.id)}
            >
              {item.label}
            </button>
          ))}
        </React.Fragment>
      ))}
    </nav>
  );
}
