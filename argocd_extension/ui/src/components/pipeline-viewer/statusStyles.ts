type StageStatusStyle = {
  fill: string;
  border: string;
  text: string;
};

const DEFAULT: StageStatusStyle = {
  fill: "#e8ebe6",
  border: "#ccd6dd",
  text: "#1c1f1a",
};

const BY_STATUS: Record<string, StageStatusStyle> = {
  SUCCESS: { fill: "#d9eee3", border: "#7fbf9a", text: "#1f6b4a" },
  FAILED: { fill: "#f3dede", border: "#d48888", text: "#8b2e2e" },
  SKIPPED: { fill: "#dadada", border: "#b8c0bb", text: "#6b736d" },
  CANCELLED: { fill: "#ebe3e8", border: "#a892a4", text: "#5c4a58" },
  IN_PROGRESS: { fill: "#dce8f4", border: "#7aa3c4", text: "#2a4d6e" },
  NOT_STARTED: { fill: "#eef1ee", border: "#b8c4bc", text: "#5c6458" },
  QUEUED: { fill: "#eef1ee", border: "#b8c4bc", text: "#5c6458" },
};

export function stageStatusStyle(status?: string | null): StageStatusStyle {
  if (!status) return DEFAULT;
  return BY_STATUS[status] || DEFAULT;
}
