export const RAIL_W = 4;
const RAIL_LINE_LEFT = 1;
const RAIL_LINE_RIGHT = 3;

export function isRailNodeId(id: string) {
  return id.endsWith("/split") || id.endsWith("/merge");
}

export function railSourceX(nodeX: number) {
  return nodeX + RAIL_LINE_RIGHT - 1;
}

export function railTargetX(nodeX: number) {
  return nodeX + RAIL_LINE_LEFT;
}
