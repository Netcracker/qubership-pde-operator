import {
  createFormToPayload,
  ensureKvPairs,
  normalizePipelineData,
  parseKvPairs,
  recordToKvPairs,
} from "./runs";
import type { CreateForm, ScheduleForm } from "./types";

/** Mirrors the backend's schedule_trigger_ref / schedule_id_from_trigger. */
const SCHEDULE_TRIGGER_PREFIX = "schedule:";

export function scheduleTriggerRef(scheduleId: string): string {
  return `${SCHEDULE_TRIGGER_PREFIX}${scheduleId}`;
}

export function isScheduledRun(triggeredBy: unknown): boolean {
  return typeof triggeredBy === "string" && triggeredBy.startsWith(SCHEDULE_TRIGGER_PREFIX);
}

export function scheduleIdFromTrigger(triggeredBy: unknown): string {
  return isScheduledRun(triggeredBy) ? String(triggeredBy).slice(SCHEDULE_TRIGGER_PREFIX.length) : "";
}

export const OVERLAP_POLICIES = [
  { value: "allow", label: "Run anyway" },
  { value: "skip", label: "Skip" },
];

export const LAST_FIRE_LABELS: Record<string, string> = {
  success: "Triggered",
  failed: "Failed to trigger",
  skipped_overlap: "Skipped (previous run active)",
  skipped_missed: "Missed (operator was down)",
};

export function emptyScheduleForm(timezone: string): ScheduleForm {
  return {
    id: "",
    name: "",
    description: "",
    cronExpression: "",
    timezone,
    enabled: true,
    overlapPolicy: "allow",
    templateId: "",
    run: {
      profile_id: "default",
      pipeline_data: "",
      pipeline_vars: [{ key: "", value: "" }],
      pipeline_vars_secure: [{ key: "", value: "" }],
      is_dry_run: false,
      log_level: "INFO",
      env_vars: [{ key: "", value: "" }],
      pde_image: "",
    },
  };
}

/** Secure values arrive masked; the same markers are sent back untouched to keep the stored secrets. */
export function scheduleToForm(schedule: any): ScheduleForm {
  return {
    id: String(schedule.id || ""),
    name: schedule.name || "",
    description: schedule.description || "",
    cronExpression: schedule.cron_expression || "",
    timezone: schedule.timezone || "UTC",
    enabled: schedule.enabled !== false,
    overlapPolicy: schedule.overlap_policy || "allow",
    templateId: schedule.created_from_template_id ? String(schedule.created_from_template_id) : "",
    run: {
      profile_id: schedule.profile_id || "default",
      pipeline_data: normalizePipelineData(schedule.pipeline_data || ""),
      pipeline_vars: ensureKvPairs(parseKvPairs(schedule.pipeline_vars)),
      pipeline_vars_secure: ensureKvPairs(parseKvPairs(schedule.pipeline_vars_secure)),
      is_dry_run: !!schedule.is_dry_run,
      log_level: schedule.log_level || "INFO",
      env_vars: ensureKvPairs(recordToKvPairs(schedule.env_vars)),
      pde_image: schedule.pde_image || "",
    },
  };
}

/** Request body for create/update. Declarative schedules send values for the server to flatten. */
export function schedulePayload(
  form: ScheduleForm,
  options: { declarativeValues?: Record<string, any> } = {},
): Record<string, any> {
  const schedule = {
    name: form.name.trim(),
    description: form.description.trim() || null,
    cron_expression: form.cronExpression.trim(),
    timezone: form.timezone,
    enabled: form.enabled,
    overlap_policy: form.overlapPolicy,
    created_from_template_id: form.templateId || null,
  };
  if (options.declarativeValues) {
    return { ...schedule, declarative_values: options.declarativeValues };
  }
  return { ...schedule, ...createFormToPayload(form.run) };
}

export function applyTemplateToScheduleForm(form: ScheduleForm, template: any, runForm: CreateForm): ScheduleForm {
  return {
    ...form,
    name: form.name || template.name || "",
    description: form.description || template.description || "",
    templateId: String(template.id || ""),
    run: runForm,
  };
}

/** "in 3h 20m" / "due now" for a schedule's next fire time. */
export function fmtFireCountdown(value: unknown, now = Date.now()): string {
  if (!value) return "—";
  const target = new Date(String(value)).getTime();
  if (Number.isNaN(target)) return "—";
  const seconds = Math.round((target - now) / 1000);
  if (seconds <= 0) return "due now";
  if (seconds < 60) return `in ${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `in ${minutes}m`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `in ${hours}h ${minutes % 60}m`;
  return `in ${Math.floor(hours / 24)}d ${hours % 24}h`;
}

/** "21h ago" / "3d ago" for the last fire time. */
export function fmtAge(value: unknown, now = Date.now()): string {
  if (!value) return "";
  const target = new Date(String(value)).getTime();
  if (Number.isNaN(target)) return "";
  const seconds = Math.round((now - target) / 1000);
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

export function fmtLastFire(schedule: any): string {
  if (!schedule?.last_fire_at) return "never";
  const label = LAST_FIRE_LABELS[schedule.last_fire_status] || schedule.last_fire_status || "";
  return label || "—";
}
