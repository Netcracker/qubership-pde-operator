import type { Edge, Node } from "@xyflow/react";

export type PipelineReport = {
  kind?: string;
  apiVersion?: string;
  id?: string;
  name?: string;
  status?: string;
  stages?: PipelineStage[];
};

export type StageParamSide = {
  params?: Record<string, unknown>;
  params_secure?: Record<string, unknown>;
  files?: Record<string, unknown>;
};

export type PipelineStage = {
  id: string;
  name: string;
  type: string;
  status?: string;
  startedAt?: string | null;
  finishedAt?: string | null;
  time?: string | null;
  command?: string | null;
  input?: StageParamSide | null;
  output?: StageParamSide | null;
  parallelStages?: PipelineStage[];
  nestedPipeline?: PipelineReport;
};

/** Fields shown in the stage detail side panel. */
export type StageDetail = {
  id: string;
  name: string;
  type: string;
  status?: string;
  startedAt?: string | null;
  finishedAt?: string | null;
  time?: string | null;
  command?: string | null;
  input?: StageParamSide | null;
  output?: StageParamSide | null;
};

export function toStageDetail(stage: PipelineStage): StageDetail {
  return {
    id: stage.id,
    name: stage.name,
    type: stage.type,
    status: stage.status,
    startedAt: stage.startedAt,
    finishedAt: stage.finishedAt,
    time: stage.time,
    command: stage.command,
    input: stage.input,
    output: stage.output,
  };
}

export type LayoutOptions = {
  collapsed: Set<string>;
};

export type SegmentLayout = {
  width: number;
  height: number;
  nodes: Node[];
  edges: Edge[];
  entries: string[];
  exits: string[];
};
