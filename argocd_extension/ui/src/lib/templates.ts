import type { CreateForm, TemplateForm } from "./types";
import { emptyCreateForm, ensureKvPairs, kvPairsToRecord, kvPairsToText, normalizePipelineData, parseKvPairs, recordToKvPairs } from "./runs";

export function parseTagsText(text: string): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const part of (text || "").split(/[,\n]/)) {
    const tag = part.trim();
    if (!tag || seen.has(tag)) continue;
    seen.add(tag);
    out.push(tag);
  }
  return out;
}

export function tagsToText(tags: string[] | null | undefined): string {
  return (tags || []).join(", ");
}

export function emptyTemplateForm(): TemplateForm {
  return {
    id: "",
    name: "",
    description: "",
    tagsText: "",
    ...emptyCreateForm(),
  };
}

export function templateToForm(template: any): TemplateForm {
  return {
    id: template.id || "",
    name: template.name || "",
    description: template.description || "",
    tagsText: tagsToText(template.tags),
    profile_id: template.profile_id || "default",
    pipeline_data: template.pipeline_data || "",
    pipeline_vars: ensureKvPairs(parseKvPairs(template.pipeline_vars)),
    pipeline_vars_secure: ensureKvPairs(parseKvPairs(template.pipeline_vars_secure)),
    is_dry_run: !!template.is_dry_run,
    log_level: template.log_level || "INFO",
    env_vars: ensureKvPairs(recordToKvPairs(template.env_vars)),
    pde_image: template.pde_image || "",
  };
}

export function templateToCreateForm(template: any): CreateForm {
  const form = templateToForm(template);
  return {
    profile_id: form.profile_id,
    pipeline_data: form.pipeline_data,
    pipeline_vars: form.pipeline_vars,
    pipeline_vars_secure: form.pipeline_vars_secure,
    is_dry_run: form.is_dry_run,
    log_level: form.log_level,
    env_vars: form.env_vars,
    pde_image: form.pde_image,
  };
}

export function templatePayload(form: TemplateForm) {
  return {
    name: form.name.trim(),
    description: form.description.trim() || null,
    tags: parseTagsText(form.tagsText),
    profile_id: form.profile_id || "default",
    pipeline_data: normalizePipelineData(form.pipeline_data),
    pipeline_vars: kvPairsToText(form.pipeline_vars),
    pipeline_vars_secure: kvPairsToText(form.pipeline_vars_secure),
    is_dry_run: form.is_dry_run,
    log_level: form.log_level,
    env_vars: kvPairsToRecord(form.env_vars),
    pde_image: form.pde_image.trim() || null,
  };
}
