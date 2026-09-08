export const EXT_TITLE = "Pipelines";
export const EXT_PATH = "/pde-operator";
export const EXT_ICON = "fa-wave-square";

export const PAGE_SIZE = 20;
export const DEFAULT_PDE_IMAGE = "ghcr.io/netcracker/qubership-pipelines-declarative-executor:v2.2.1";

export const STATUSES = ["QUEUED", "NOT_STARTED", "SKIPPED", "IN_PROGRESS", "SUCCESS", "FAILED", "CANCELLED"] as const;

export const PLACEHOLDER_PIPELINE_DATA = "https://raw.githubusercontent.com/..../pipeline.yaml;";
export const PLACEHOLDER_KV_KEY = "KEY";
export const PLACEHOLDER_KV_VALUE = "value";
