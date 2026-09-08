export const KNOWN_INTERFACES = ["Profiles", "ClusterNamespaces", "GitFiles"] as const;

export type FieldType = "string" | "checkbox" | "select";
export type SelectType = "single" | "multi";
export type BindTo = "pipeline_var" | "env_var" | "pipeline_data" | "is_dry_run" | "log_level" | "profile";

export type DeclarativeField = {
  name: string;
  value?: any;
  description?: string | null;
  options?: string[] | null;
  field_type: FieldType;
  select_type?: SelectType;
  required?: boolean;
  required_condition?: string | null;
  hide_condition?: string | null;
  hidden?: boolean;
  readonly?: boolean;
  secure?: boolean;
  placeholder?: string | null;
  label: string;
  bind_to?: BindTo;
  validators?: Array<{ type: "pattern"; value: string; message: string }>;
  interface?: string | null;
  data?: Record<string, any>;
};

export type DeclarativeRunTemplate = {
  name: string;
  fields: DeclarativeField[];
};

export function isKnownInterface(name: string | null | undefined): boolean {
  return !!name && (KNOWN_INTERFACES as readonly string[]).includes(name);
}
