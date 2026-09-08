import { BaseEdge, useInternalNode, type EdgeProps } from "@xyflow/react";
import { isRailNodeId, railSourceX, railTargetX } from "./railMetrics";

function orthogonalPath(sx: number, sy: number, tx: number, ty: number) {
  if (Math.abs(sy - ty) < 2) return `M ${sx},${sy} L ${tx},${ty}`;
  if (sx <= tx) {
    const midX = sx + (tx - sx) / 2;
    return `M ${sx},${sy} L ${midX},${sy} L ${midX},${ty} L ${tx},${ty}`;
  }
  const midX = sx - (sx - tx) / 2;
  return `M ${sx},${sy} L ${midX},${sy} L ${midX},${ty} L ${tx},${ty}`;
}

/** Left-to-right pipeline edges: horizontal, optional vertical, horizontal — no diagonals. */
export function OrthogonalEdge(props: EdgeProps) {
  const { source, target, sourceX, sourceY, targetX, targetY, markerEnd, style } = props;
  const sourceNode = useInternalNode(source);
  const targetNode = useInternalNode(target);

  const sx = sourceNode && isRailNodeId(source) ? railSourceX(sourceNode.internals.positionAbsolute.x) : sourceX;
  const tx = targetNode && isRailNodeId(target) ? railTargetX(targetNode.internals.positionAbsolute.x) : targetX;

  return (
    <BaseEdge
      path={orthogonalPath(sx, sourceY, tx, targetY)}
      markerEnd={markerEnd}
      style={{ strokeLinecap: "butt", ...style }}
    />
  );
}

export const pipelineEdgeTypes = {
  orthogonal: OrthogonalEdge,
};
