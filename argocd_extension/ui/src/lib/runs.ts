import type { CreateForm, KeyValuePair, RetryForm } from "./types";

export function canCancel(run: any) {
  return run && !run.cancel_requested_at && ["IN_PROGRESS", "NOT_STARTED", "QUEUED"].includes(run.status);
}

export function canRetry(run: any) {
  return run && (run.status === "FAILED" || run.status === "CANCELLED");
}

export function splitMultilineEntries(text: string): string[] {
  const out: string[] = [];
  for (const raw of String(text || "").split(/[\n\r;]/)) {
    const line = raw.trim();
    if (line) out.push(line);
  }
  return out;
}

/** Normalize pipeline_data to one entry per line. */
export function normalizePipelineData(text: string): string {
  return splitMultilineEntries(text).join("\n");
}

export function parseKvPairs(text: string | null | undefined): KeyValuePair[] {
  if (!text || !String(text).trim()) return [];
  const pairs: KeyValuePair[] = [];
  for (const line of splitMultilineEntries(text)) {
    if (line.startsWith("#") || !line.includes("=")) continue;
    const idx = line.indexOf("=");
    const key = line.slice(0, idx).trim();
    if (!key) continue;
    pairs.push({ key, value: line.slice(idx + 1) });
  }
  return pairs;
}

export function kvPairsToText(pairs: KeyValuePair[] | null | undefined): string | null {
  if (!pairs?.length) return null;
  const lines: string[] = [];
  for (const p of pairs) {
    const key = (p.key || "").trim();
    if (!key) continue;
    lines.push(`${key}=${p.value ?? ""}`);
  }
  return lines.length ? lines.join("\n") : null;
}

export function kvPairsToRecord(pairs: KeyValuePair[] | null | undefined): Record<string, string> | null {
  if (!pairs?.length) return null;
  const result: Record<string, string> = {};
  for (const p of pairs) {
    const key = (p.key || "").trim();
    if (!key) continue;
    result[key] = p.value ?? "";
  }
  return Object.keys(result).length ? result : null;
}

export function recordToKvPairs(env: Record<string, unknown> | null | undefined): KeyValuePair[] {
  if (!env || typeof env !== "object") return [];
  return Object.entries(env).map(([key, v]) => ({ key, value: v == null ? "" : String(v) }));
}

export function emptyKvPair(): KeyValuePair {
  return { key: "", value: "" };
}

/** Keep at least one editable row in the UI. */
export function ensureKvPairs(pairs: KeyValuePair[]): KeyValuePair[] {
  return pairs.length ? pairs : [emptyKvPair()];
}

export function emptyCreateForm(): CreateForm {
  return {
    profile_id: "default",
    pipeline_data: "",
    pipeline_vars: [emptyKvPair()],
    pipeline_vars_secure: [emptyKvPair()],
    is_dry_run: false,
    log_level: "INFO",
    env_vars: [emptyKvPair()],
    pde_image: "",
  };
}

export function emptyRetryForm(): RetryForm {
  return { retry_vars: [emptyKvPair()], pde_image: "" };
}
