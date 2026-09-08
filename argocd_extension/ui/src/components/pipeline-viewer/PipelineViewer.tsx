import { Background, Controls, ReactFlow, ReactFlowProvider, useReactFlow } from "@xyflow/react";
import { pipelineEdgeTypes } from "./edges";
import { layoutPipelineReport } from "./layout";
import { pipelineNodeTypes } from "./nodes";
import { StageDetailPanel } from "./StageDetailPanel";
import type { PipelineReport, StageDetail } from "./types";

function FitViewOnLayout(props: { layoutKey: string }) {
  const { fitView } = useReactFlow();
  React.useEffect(() => {
    const timer = window.setTimeout(() => fitView({ padding: 0.12, duration: 200 }), 0);
    return () => window.clearTimeout(timer);
  }, [props.layoutKey, fitView]);
  return null;
}

function enrichNodes(
  layoutNodes: ReturnType<typeof layoutPipelineReport>["nodes"],
  edges: ReturnType<typeof layoutPipelineReport>["edges"],
  toggleCollapse: (groupId: string) => void,
  selectStage: (detail: StageDetail) => void,
  selectedId: string | null,
) {
  const incoming = new Set(edges.map((e) => e.target));
  const outgoing = new Set(edges.map((e) => e.source));
  return layoutNodes.map((node) => {
    const base = {
      ...node.data,
      showTarget: incoming.has(node.id),
      showSource: outgoing.has(node.id),
    };
    if (node.type === "stage" || node.type === "nestedPipeline") {
      const detail = (node.data as { detail?: StageDetail }).detail;
      const data: Record<string, unknown> = {
        ...base,
        selected: !!detail && detail.id === selectedId,
        onSelect: detail ? () => selectStage(detail) : undefined,
      };
      if (node.type === "nestedPipeline") {
        const groupId = String((node.data as { groupId: string }).groupId);
        data.onToggle = () => toggleCollapse(groupId);
      }
      return { ...node, data };
    }
    return { ...node, data: base };
  });
}

export function PipelineViewer(props: { report: PipelineReport }) {
  const [collapsed, setCollapsed] = React.useState<Set<string>>(() => new Set());
  const [selected, setSelected] = React.useState<StageDetail | null>(null);

  React.useEffect(() => {
    setSelected(null);
  }, [props.report]);

  React.useEffect(() => {
    if (!selected) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setSelected(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [selected]);

  const toggleCollapse = React.useCallback((groupId: string) => {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(groupId)) next.delete(groupId);
      else next.add(groupId);
      return next;
    });
  }, []);

  const selectStage = React.useCallback((detail: StageDetail) => {
    setSelected(detail);
  }, []);

  const { nodes: layoutNodes, edges } = React.useMemo(
    () => layoutPipelineReport(props.report, { collapsed }),
    [props.report, collapsed],
  );

  const selectedId = selected?.id ?? null;
  const nodes = React.useMemo(
    () => enrichNodes(layoutNodes, edges, toggleCollapse, selectStage, selectedId),
    [layoutNodes, edges, toggleCollapse, selectStage, selectedId],
  );

  const layoutKey = `${nodes.length}:${edges.length}:${collapsed.size}`;

  if (!nodes.length) {
    return <p className="pde-muted">No stages in report.</p>;
  }

  return (
    <div className="pde-pv-shell">
      <ReactFlowProvider>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={pipelineNodeTypes}
          edgeTypes={pipelineEdgeTypes}
          noPanClassName="nopan"
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable={false}
          panOnScroll={false}
          zoomOnScroll
          preventScrolling
          minZoom={0.05}
          maxZoom={2}
          onPaneClick={() => setSelected(null)}
          proOptions={{ hideAttribution: true }}
        >
          <Background gap={18} size={1} color="#d8e0d4" />
          <Controls showInteractive={false} />
          <FitViewOnLayout layoutKey={layoutKey} />
        </ReactFlow>
      </ReactFlowProvider>
      {selected ? <StageDetailPanel detail={selected} onClose={() => setSelected(null)} /> : null}
    </div>
  );
}
