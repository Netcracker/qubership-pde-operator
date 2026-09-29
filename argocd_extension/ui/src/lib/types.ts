export type Tab = "catalog" | "list" | "detail" | "create" | "profiles" | "schedules" | "settings";
export type CreateMode = "create" | "retry";
export type ProfileSubview = "list" | "create" | "edit";
export type CatalogSubview = "list" | "create" | "edit";
export type ScheduleSubview = "list" | "create" | "edit";
export type DetailSubview = "info" | "logs" | "viewer";
export type LogStatus = "idle" | "loading" | "ready" | "not_ready" | "error";
export type ReportStatus = LogStatus;

export type KeyValuePair = { key: string; value: string };

export type CreateForm = {
  profile_id: string;
  pipeline_data: string;
  pipeline_vars: KeyValuePair[];
  pipeline_vars_secure: KeyValuePair[];
  is_dry_run: boolean;
  log_level: string;
  env_vars: KeyValuePair[];
  pde_image: string;
};

export type TemplateForm = CreateForm & {
  id: string; // set after load for edit; server-generated on create
  name: string;
  description: string;
  tagsText: string;
};

export type RetryForm = {
  retry_vars: KeyValuePair[];
  pde_image: string;
};

export type ScheduleForm = {
  id: string; // set after load for edit; server-generated on create
  name: string;
  description: string;
  cronExpression: string;
  timezone: string;
  enabled: boolean;
  overlapPolicy: string;
  templateId: string; // set when started from a catalog template
  run: CreateForm;
};

export type ProfileForm = {
  id: string;
  pde_image: string;
  envVarsText: string;
  resourcesText: string;
};

export type CleanupForm = {
  older_than_days: number;
};
