import type { Edge, Node } from "@xyflow/react";
import { RAIL_W } from "./railMetrics";
import type { LayoutOptions, PipelineReport, PipelineStage, SegmentLayout } from "./types";
import { toStageDetail } from "./types";

const LEAF_W = 168;
const LEAF_H = 44;
const GAP_X = 72;
const GAP_Y = 16;
const GROUP_PAD = 20;
const HEADER_H = 32;
const MIN_GROUP_W = 140;
const RAIL_GAP = 56;

const LOCKED_NODE = { draggable: false, selectable: false, connectable: false } as const;

type LayoutCtx = {
  path: string;
  offsetX: number;
  offsetY: number;
  parentId?: string;
  collapsed: Set<string>;
};

function makeEdge(source: string, target: string, sourceHandle?: string, targetHandle?: string): Edge {
  return {
    id: `${source}:${sourceHandle || ""}->${target}:${targetHandle || ""}`,
    source,
    target,
    sourceHandle,
    targetHandle,
    type: "orthogonal",
    style: { stroke: "#8496a1", strokeWidth: 1.5 },
  };
}

function connectSegments(fromExits: string[], toEntries: string[], edges: Edge[]) {
  for (const source of fromExits) {
    for (const target of toEntries) {
      const sourceHandle = source.endsWith("/merge") ? "out" : undefined;
      const targetHandle = target.endsWith("/split") ? "in" : undefined;
      edges.push(makeEdge(source, target, sourceHandle, targetHandle));
    }
  }
}

function layoutLeaf(stage: PipelineStage, nodeId: string, x: number, y: number, parentId?: string): SegmentLayout {
  const node: Node = {
    ...LOCKED_NODE,
    id: nodeId,
    type: "stage",
    position: { x, y },
    parentId,
    extent: parentId ? "parent" : undefined,
    data: { label: stage.name, status: stage.status || "", detail: toStageDetail(stage) },
    style: { width: LEAF_W, height: LEAF_H },
  };
  return { width: LEAF_W, height: LEAF_H, nodes: [node], edges: [], entries: [nodeId], exits: [nodeId] };
}

function makeRailNode(
  id: string,
  variant: "split" | "merge",
  x: number,
  y: number,
  height: number,
  branchCenters: number[],
  parentId?: string,
): Node {
  return {
    ...LOCKED_NODE,
    id,
    type: "rail",
    position: { x, y },
    parentId,
    extent: parentId ? "parent" : undefined,
    data: { branchCenters, variant },
    style: { width: RAIL_W, height: Math.max(height, LEAF_H) },
    zIndex: 1,
  };
}

function layoutParallelBlock(
  stage: PipelineStage,
  pathPrefix: string,
  x: number,
  y: number,
  parentId: string | undefined,
  collapsed: Set<string>,
): SegmentLayout {
  const children = stage.parallelStages || [];
  const splitId = `${pathPrefix}/split`;
  const mergeId = `${pathPrefix}/merge`;
  const childX = x + RAIL_GAP + RAIL_W;
  let childY = y;
  let maxChildW = 0;
  const nodes: Node[] = [];
  const edges: Edge[] = [];
  const branchCenters: number[] = [];

  for (let i = 0; i < children.length; i++) {
    const child = children[i];
    const childId = `${pathPrefix}/${child.id}`;
    const placed = layoutStage(child, childId, childX, childY, parentId, collapsed);
    nodes.push(...placed.nodes);
    edges.push(...placed.edges);
    branchCenters.push(childY + placed.height / 2 - y);
    for (const entry of placed.entries) edges.push(makeEdge(splitId, entry, `s${i}`));
    for (const exit of placed.exits) edges.push(makeEdge(exit, mergeId, undefined, `t${i}`));
    childY += placed.height + GAP_Y;
    maxChildW = Math.max(maxChildW, placed.width);
  }

  const height = children.length ? childY - y - GAP_Y : LEAF_H;
  const mergeX = childX + maxChildW + RAIL_GAP;

  nodes.push(
    makeRailNode(splitId, "split", x, y, height, branchCenters, parentId),
    makeRailNode(mergeId, "merge", mergeX, y, height, branchCenters, parentId),
  );

  const width = children.length ? mergeX + RAIL_W - x : RAIL_W;

  return { width, height: Math.max(height, LEAF_H), nodes, edges, entries: [splitId], exits: [mergeId] };
}

function layoutNestedPipeline(
  stage: PipelineStage,
  groupId: string,
  x: number,
  y: number,
  parentId: string | undefined,
  collapsed: Set<string>,
): SegmentLayout {
  const nested = stage.nestedPipeline!;
  const isCollapsed = collapsed.has(groupId);
  const label = nested.name || stage.name;
  const status = nested.status || stage.status || "";

  let groupW = MIN_GROUP_W;
  let groupH = HEADER_H + GROUP_PAD * 2;
  const nodes: Node[] = [];
  const edges: Edge[] = [];

  if (!isCollapsed && nested.stages?.length) {
    const inner = layoutStages(nested.stages, {
      path: `${groupId}/nested`,
      offsetX: GROUP_PAD,
      offsetY: HEADER_H + GROUP_PAD,
      parentId: groupId,
      collapsed,
    });
    nodes.push(...inner.nodes);
    edges.push(...inner.edges);
    groupW = Math.max(inner.width + GROUP_PAD * 2, MIN_GROUP_W);
    groupH = HEADER_H + GROUP_PAD * 2 + inner.height;
  }

  nodes.unshift({
    ...LOCKED_NODE,
    id: groupId,
    type: "nestedPipeline",
    position: { x, y },
    parentId,
    extent: parentId ? "parent" : undefined,
    data: { label, status, groupId, collapsed: isCollapsed, detail: toStageDetail(stage) },
    style: { width: groupW, height: groupH },
    zIndex: 0,
  });

  return { width: groupW, height: groupH, nodes, edges, entries: [groupId], exits: [groupId] };
}

function layoutStage(
  stage: PipelineStage,
  nodeId: string,
  x: number,
  y: number,
  parentId: string | undefined,
  collapsed: Set<string>,
): SegmentLayout {
  if (stage.type === "PARALLEL_BLOCK" && stage.parallelStages?.length) {
    return layoutParallelBlock(stage, nodeId, x, y, parentId, collapsed);
  }
  if (stage.type === "ATLAS_PIPELINE_TRIGGER" && stage.nestedPipeline) {
    return layoutNestedPipeline(stage, nodeId, x, y, parentId, collapsed);
  }
  return layoutLeaf(stage, nodeId, x, y, parentId);
}

function layoutStages(stages: PipelineStage[], ctx: LayoutCtx): SegmentLayout {
  let x = ctx.offsetX;
  const y = ctx.offsetY;
  const nodes: Node[] = [];
  const edges: Edge[] = [];
  let prevExits: string[] = [];
  let maxHeight = 0;
  let firstEntries: string[] = [];

  for (let i = 0; i < stages.length; i++) {
    const stage = stages[i];
    const nodeId = `${ctx.path}/${stage.id}`;
    const placed = layoutStage(stage, nodeId, x, y, ctx.parentId, ctx.collapsed);
    nodes.push(...placed.nodes);
    edges.push(...placed.edges);

    if (i === 0) firstEntries = placed.entries;
    if (prevExits.length) connectSegments(prevExits, placed.entries, edges);

    x += placed.width + GAP_X;
    maxHeight = Math.max(maxHeight, placed.height);
    prevExits = placed.exits;
  }

  const width = stages.length ? x - ctx.offsetX - GAP_X : 0;
  return {
    width,
    height: maxHeight,
    nodes,
    edges,
    entries: firstEntries,
    exits: prevExits,
  };
}

export function layoutPipelineReport(report: PipelineReport, options: LayoutOptions): { nodes: Node[]; edges: Edge[] } {
  const stages = report.stages || [];
  if (!stages.length) return { nodes: [], edges: [] };
  const result = layoutStages(stages, {
    path: "root",
    offsetX: 24,
    offsetY: 24,
    collapsed: options.collapsed,
  });
  return { nodes: result.nodes, edges: result.edges };
}
