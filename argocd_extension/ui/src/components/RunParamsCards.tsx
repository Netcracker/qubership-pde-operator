import { parseKvPairs, splitMultilineEntries } from "../lib/runs";

export function MetaItem({ label, children, wide }: { label: string; children: any; wide?: boolean }) {
  return (
    <div className={wide ? "pde-wide" : undefined}>
      <dt>{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}

export function MetaSubsection({ children }: { children: any }) {
  return (
    <div className="pde-detail-subsection">
      <dl className="pde-meta pde-meta-compact">{children}</dl>
    </div>
  );
}

export function DetailMetaCard({ children }: { children: any }) {
  return (
    <section className="pde-detail-card">
      <div className="pde-detail-grid">{children}</div>
    </section>
  );
}

export function FoldCard(props: { title: string; children: any }) {
  return (
    <details className="pde-detail-card pde-detail-fold" open>
      <summary className="pde-detail-fold-summary">{props.title}</summary>
      <div className="pde-detail-fold-body">{props.children}</div>
    </details>
  );
}

export function PipelineDataCard({ text }: { text?: string | null }) {
  const entries = splitMultilineEntries(text || "");
  return (
    <FoldCard title="Pipeline data">
      {entries.length ? (
        <ul className="pde-data-list">
          {entries.map((entry, index) => (
            <li key={`${index}-${entry}`}>
              <code className="pde-data-entry">{entry}</code>
            </li>
          ))}
        </ul>
      ) : (
        <span className="pde-muted">—</span>
      )}
    </FoldCard>
  );
}

export function VarsCard({ title, text }: { title: string; text?: string | null }) {
  const pairs = parseKvPairs(text);
  return (
    <FoldCard title={title}>
      {pairs.length ? (
        <div className="pde-var-list">
          {pairs.map((pair, index) => (
            <label className="pde-var-row" key={`${index}-${pair.key}`}>
              <span className="pde-var-label pde-mono">{pair.key}</span>
              <input className="pde-input pde-var-value" type="text" value={pair.value} readOnly />
            </label>
          ))}
        </div>
      ) : (
        <span className="pde-muted">—</span>
      )}
    </FoldCard>
  );
}
