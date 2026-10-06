import { apiJson } from "../api/client";
import type { CreateForm, TemplateForm } from "./types";
import {
  createFormToPayload,
  emptyCreateForm,
  ensureKvPairs,
  parseKvPairs,
  recordToKvPairs,
} from "./runs";

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
    ...createFormToPayload(form),
  };
}

/** Dynamic enum options for a declarative template field (see DeclarativeRunTemplateFormView). */
export async function fetchDeclarativeOptions(
  templateId: string,
  fieldId: string,
  context: Record<string, any>,
): Promise<{ value: string; label: string }[]> {
  if (!templateId) return [];
  const data = (await apiJson(`/run-templates/${templateId}/declarative/options`, {
    method: "POST",
    body: JSON.stringify({ fieldId, context }),
  })) as any;
  return (data.options || []).map((o: any) => ({ value: o.value, label: o.label }));
}
