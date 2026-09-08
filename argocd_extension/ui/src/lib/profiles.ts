import { DEFAULT_PDE_IMAGE } from "./constants";
import type { ProfileForm } from "./types";

export function emptyProfileForm(): ProfileForm {
  return {
    id: "",
    pde_image: DEFAULT_PDE_IMAGE,
    envVarsText: "{}",
    resourcesText: "{}",
  };
}

export function profileToForm(profile: any): ProfileForm {
  return {
    id: profile.id,
    pde_image: profile.pde_image,
    envVarsText: JSON.stringify(profile.env_vars || {}, null, 2),
    resourcesText: JSON.stringify(profile.resources || {}, null, 2),
  };
}

export function profilePayload(form: ProfileForm, mode: "create" | "edit") {
  const base = {
    pde_image: form.pde_image.trim(),
    env_vars: parseProfileJsonField(form.envVarsText, "Env vars"),
    resources: parseProfileJsonField(form.resourcesText, "Resources"),
  };
  if (mode === "create") return { id: form.id.trim(), ...base };
  return base;
}

export function parseProfileJsonField(text: string, label: string) {
  try {
    const value = JSON.parse(text);
    if (value === null || typeof value !== "object" || Array.isArray(value)) {
      throw new Error(`${label} must be a JSON object`);
    }
    return value;
  } catch (e: any) {
    if (e instanceof SyntaxError) throw new Error(`${label} must be valid JSON`);
    throw e;
  }
}
