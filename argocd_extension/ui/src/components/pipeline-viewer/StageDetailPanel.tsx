import { Badge } from "../ui";
import { fmt } from "../../lib/format";
import type { StageDetail, StageParamSide } from "./types";

const PARAM_SECTIONS = [
  { key: "params", label: "Params" },
  { key: "params_secure", label: "Secure params" },
  { key: "files", label: "Files" },
] as const satisfies ReadonlyArray<{ key: keyof StageParamSide; label: string }>;

function isNonEmptyValue(value: unknown): boolean {
  if (value == null) return false;
  if (Array.isArray(value)) return value.length > 0;
  if (typeof value === "object") {
    const entries = Object.values(value as Record<string, unknown>);
    return entries.length > 0 && entries.some(isNonEmptyValue);
  }
  return true;
}

function sideHasContent(side?: StageParamSide | null) {
  if (!side) return false;
  return PARAM_SECTIONS.some(({ key }) => isNonEmptyValue(side[key]));
}

function formatJson(value: unknown) {
  return JSON.stringify(value, null, 2);
}

function DetailField(props: { label: string; children: any }) {
  return (
    <>
      <dt>{props.label}</dt>
      <dd>{props.children}</dd>
    </>
  );
}

function ParamSideSection(props: { title: string; side: StageParamSide }) {
  const sections = PARAM_SECTIONS.filter(({ key }) => isNonEmptyValue(props.side[key]));
  if (!sections.length) return null;

  return (
    <details className="pde-pv-detail-fold">
      <summary className="pde-pv-detail-fold-summary">{props.title}</summary>
      <div className="pde-pv-detail-fold-body">
        {sections.map(({ key, label }) => (
          <details key={key} className="pde-pv-detail-fold pde-pv-detail-fold-nested">
            <summary className="pde-pv-detail-fold-summary">{label}</summary>
            <pre className="pde-pv-detail-code">{formatJson(props.side[key])}</pre>
          </details>
        ))}
      </div>
    </details>
  );
}

export function StageDetailPanel(props: { detail: StageDetail; onClose: () => void }) {
  const { detail, onClose } = props;
  const command = detail.command != null && String(detail.command).trim() !== "" ? String(detail.command) : null;
  const showInput = sideHasContent(detail.input);
  const showOutput = sideHasContent(detail.output);

  return (
    <aside className="pde-pv-detail" aria-label="Stage details">
      <div className="pde-pv-detail-header">
        <h2 className="pde-pv-detail-title" title={detail.name}>
          {detail.name || "Stage"}
        </h2>
        <button type="button" className="pde-pv-detail-close" onClick={onClose} aria-label="Close stage details">
          ×
        </button>
      </div>
      <div className="pde-pv-detail-body">
        <dl className="pde-pv-detail-meta">
          <DetailField label="Status">
            <Badge status={detail.status || ""} />
          </DetailField>
          <DetailField label="Started">
            <span className="pde-mono">{fmt(detail.startedAt)}</span>
          </DetailField>
          <DetailField label="Finished">
            <span className="pde-mono">{fmt(detail.finishedAt)}</span>
          </DetailField>
          <DetailField label="Time">
            <span className="pde-mono">{detail.time || "—"}</span>
          </DetailField>
          <DetailField label="Type">
            <span className="pde-mono">{detail.type || "—"}</span>
          </DetailField>
          {command ? (
            <DetailField label="Command">
              <pre className="pde-pv-detail-code">{command}</pre>
            </DetailField>
          ) : null}
        </dl>
        {showInput ? <ParamSideSection title="Input" side={detail.input!} /> : null}
        {showOutput ? <ParamSideSection title="Output" side={detail.output!} /> : null}
      </div>
    </aside>
  );
}
