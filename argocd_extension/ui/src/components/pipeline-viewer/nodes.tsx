import { Handle, Position } from "@xyflow/react";
import { stageStatusStyle } from "./statusStyles";
import type { StageDetail } from "./types";

type HandleFlags = { showTarget?: boolean; showSource?: boolean };
type Selectable = { detail?: StageDetail; selected?: boolean; onSelect?: () => void };

type StageNodeData = { label: string; status: string } & HandleFlags & Selectable;

export function StageNode({ data }: { data: StageNodeData }) {
  const style = stageStatusStyle(data.status);
  const className = ["pde-pv-stage", "nopan", data.selected ? "is-selected" : "", data.onSelect ? "is-clickable" : ""]
    .filter(Boolean)
    .join(" ");
  return (
    <div
      className={className}
      title={data.label}
      role={data.onSelect ? "button" : undefined}
      tabIndex={data.onSelect ? 0 : undefined}
      onClick={data.onSelect}
      onKeyDown={(e: any) => {
        if (!data.onSelect) return;
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          data.onSelect();
        }
      }}
      style={{ background: style.fill, borderColor: style.border, color: style.text }}
    >
      {data.showTarget ? <Handle type="target" position={Position.Left} className="pde-pv-handle" /> : null}
      <span className="pde-pv-stage-label">{data.label}</span>
      {data.showSource ? <Handle type="source" position={Position.Right} className="pde-pv-handle" /> : null}
    </div>
  );
}

type NestedPipelineData = {
  label: string;
  status: string;
  groupId: string;
  collapsed: boolean;
  onToggle?: () => void;
} & HandleFlags &
  Selectable;

export function NestedPipelineNode({ data }: { data: NestedPipelineData }) {
  const style = stageStatusStyle(data.status);
  const headerClass = [
    "pde-pv-group-header",
    "nopan",
    data.selected ? "is-selected" : "",
    data.onSelect ? "is-clickable" : "",
  ]
    .filter(Boolean)
    .join(" ");
  return (
    <div className="pde-pv-group" style={{ borderColor: style.border }}>
      {data.showTarget ? <Handle type="target" position={Position.Left} className="pde-pv-handle" /> : null}
      <div
        className={headerClass}
        style={{ background: style.fill, color: style.text }}
        title={data.label}
        role={data.onSelect ? "button" : undefined}
        tabIndex={data.onSelect ? 0 : undefined}
        onClick={data.onSelect}
        onKeyDown={(e: any) => {
          if (!data.onSelect) return;
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            data.onSelect();
          }
        }}
      >
        <button
          type="button"
          className="pde-pv-collapse"
          onClick={(e: any) => {
            e.stopPropagation();
            data.onToggle?.();
          }}
          aria-expanded={!data.collapsed}
        >
          {data.collapsed ? "▸" : "▾"}
        </button>
        <span className="pde-pv-group-title">{data.label}</span>
      </div>
      {data.showSource ? <Handle type="source" position={Position.Right} className="pde-pv-handle" /> : null}
    </div>
  );
}

type RailNodeData = { branchCenters: number[]; variant: "split" | "merge" } & HandleFlags;

export function RailNode({ data }: { data: RailNodeData }) {
  const split = data.variant === "split";
  return (
    <div className="pde-pv-rail">
      <div className="pde-pv-rail-line" aria-hidden="true" />
      {split && data.showTarget ? (
        <Handle type="target" position={Position.Left} id="in" className="pde-pv-handle-rail" style={{ top: "50%" }} />
      ) : null}
      {data.branchCenters.map((center, i) => (
        <Handle
          key={i}
          type={split ? "source" : "target"}
          position={split ? Position.Right : Position.Left}
          id={split ? `s${i}` : `t${i}`}
          className="pde-pv-handle-rail"
          style={{ top: center }}
        />
      ))}
      {!split && data.showSource ? (
        <Handle type="source" position={Position.Right} id="out" className="pde-pv-handle-rail" style={{ top: "50%" }} />
      ) : null}
    </div>
  );
}

export const pipelineNodeTypes = {
  stage: StageNode,
  nestedPipeline: NestedPipelineNode,
  rail: RailNode,
};
