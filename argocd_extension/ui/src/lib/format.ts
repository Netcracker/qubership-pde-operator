import { PAGE_SIZE } from "./constants";

export function pageRange(total: number, page: number, pageSize = PAGE_SIZE) {
  const start = total === 0 ? 0 : page * pageSize + 1;
  const end = Math.min(total, (page + 1) * pageSize);
  return {
    start,
    end,
    label: total === 0 ? "0 items" : `${start}–${end} of ${total}`,
    hasPrev: page > 0,
    hasNext: end < total,
  };
}

export function paginatedQuery(page: number, pageSize = PAGE_SIZE) {
  return new URLSearchParams({ offset: String(page * pageSize), limit: String(pageSize) });
}

export { errMsg } from "./apiErrors";

export function shortId(id: unknown) {
  return id ? String(id).slice(0, 8) : "";
}

export function fmtTemplateRef(templateId: unknown, name?: string | null) {
  if (!templateId) return "—";
  const id = String(templateId);
  if (name) return `${name} (${id})`;
  return id;
}

export function fmt(value: unknown) {
  if (!value) return "—";
  try {
    return new Date(String(value)).toLocaleString();
  } catch {
    return String(value);
  }
}

export type RunProgress = { completed: number; total: number; percent: number };

export function parseRunProgress(progress: unknown): RunProgress | null {
  if (!progress || typeof progress !== "object") return null;
  const total = Number((progress as { stagesTotal?: unknown }).stagesTotal);
  const completed = Number((progress as { stagesCompleted?: unknown }).stagesCompleted);
  if (!Number.isFinite(total) || total <= 0 || !Number.isFinite(completed)) return null;
  const safeCompleted = Math.min(Math.max(0, Math.round(completed)), Math.round(total));
  const safeTotal = Math.round(total);
  return { completed: safeCompleted, total: safeTotal, percent: Math.round((safeCompleted / safeTotal) * 100) };
}

export function fmtDuration(run: any) {
  if (!run?.started_at || !run?.finished_at) return "—";
  const start = new Date(run.started_at).getTime();
  const end = new Date(run.finished_at).getTime();
  if (Number.isNaN(start) || Number.isNaN(end) || end < start) return "—";
  let secs = Math.floor((end - start) / 1000);
  const hours = Math.floor(secs / 3600);
  secs %= 3600;
  const mins = Math.floor(secs / 60);
  secs %= 60;
  const parts: string[] = [];
  if (hours) parts.push(`${hours}h`);
  if (mins) parts.push(`${mins}m`);
  if (secs || parts.length === 0) parts.push(`${secs}s`);
  return parts.join(" ");
}

/** Scroll a log panel to the bottom; retries until layout height is stable (ANSI HTML render). */
export function scrollLogToEnd(getEl: () => HTMLElement | null, attempt = 0) {
  requestAnimationFrame(() => {
    const el = getEl();
    if (!el) {
      if (attempt < 40) scrollLogToEnd(getEl, attempt + 1);
      return;
    }
    el.scrollTop = el.scrollHeight;
    const remaining = el.scrollHeight - el.clientHeight - el.scrollTop;
    if (el.scrollHeight === 0 || remaining > 2) {
      if (attempt < 40) scrollLogToEnd(getEl, attempt + 1);
    }
  });
}

export function defaultCleanupOlderThan() {
  const d = new Date();
  d.setDate(d.getDate() - 30);
  d.setSeconds(0, 0);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}
