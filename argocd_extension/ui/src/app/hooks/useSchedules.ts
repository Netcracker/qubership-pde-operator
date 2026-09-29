import { apiJson } from "../../api/client";
import { errMsg, paginatedQuery } from "../../lib/format";
import { applyTemplateToScheduleForm, emptyScheduleForm, schedulePayload, scheduleToForm } from "../../lib/schedules";
import { templateToCreateForm } from "../../lib/templates";
import type { CreateForm, ScheduleForm, ScheduleSubview } from "../../lib/types";
import type { AppMessages } from "./useAppMessages";
import type { GoFn } from "./useAppRouting";

type UseSchedulesArgs = {
  tab: string;
  scheduleSubview: ScheduleSubview;
  go: GoFn;
  messages: AppMessages;
};

const PREVIEW_DEBOUNCE_MS = 350;

function browserTimezone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  } catch {
    return "UTC";
  }
}

export function useSchedules({ tab, scheduleSubview, go, messages }: UseSchedulesArgs) {
  const { setError, setFlash } = messages;
  const [items, setItems] = React.useState<any[]>([]);
  const [total, setTotal] = React.useState(0);
  const [page, setPage] = React.useState(0);
  const [loading, setLoading] = React.useState(false);
  const [form, setForm] = React.useState<ScheduleForm>(() => emptyScheduleForm(browserTimezone()));
  const [formReady, setFormReady] = React.useState(scheduleSubview !== "edit");
  const [submitting, setSubmitting] = React.useState(false);
  const [profiles, setProfiles] = React.useState<any[]>([]);
  const [timezones, setTimezones] = React.useState<string[]>([]);
  const [declarativeContract, setDeclarativeContract] = React.useState<any | null>(null);
  const [preview, setPreview] = React.useState<string[]>([]);
  const [previewError, setPreviewError] = React.useState("");
  const listLoadSeqRef = React.useRef(0);
  const editLoadSeqRef = React.useRef(0);
  const timezonesLoadedRef = React.useRef(false);

  const resetScheduleForm = React.useCallback(() => {
    editLoadSeqRef.current += 1;
    setForm(emptyScheduleForm(browserTimezone()));
    setDeclarativeContract(null);
    setFormReady(true);
    setPreview([]);
    setPreviewError("");
  }, []);

  const loadList = React.useCallback(
    async ({ page: pageOverride }: { page?: number } = {}) => {
      const seq = ++listLoadSeqRef.current;
      const p = pageOverride ?? page;
      setLoading(true);
      try {
        const data = (await apiJson(`/schedules?${paginatedQuery(p)}`)) as any;
        if (seq !== listLoadSeqRef.current) return;
        setItems(data.items || []);
        setTotal(data.total || 0);
        if (pageOverride != null) setPage(pageOverride);
        setError("");
      } catch (e) {
        if (seq !== listLoadSeqRef.current) return;
        setError(errMsg(e));
      } finally {
        if (seq === listLoadSeqRef.current) setLoading(false);
      }
    },
    [page, setError],
  );

  const loadProfiles = React.useCallback(async () => {
    try {
      const data = (await apiJson("/profiles?limit=500")) as any;
      setProfiles(data.items || []);
    } catch {
      setProfiles([]);
    }
  }, []);

  const loadTimezones = React.useCallback(async () => {
    if (timezonesLoadedRef.current) return;
    timezonesLoadedRef.current = true;
    try {
      const data = (await apiJson("/schedules/timezones")) as any;
      setTimezones(data.timezones || []);
    } catch (e) {
      timezonesLoadedRef.current = false;
      setError(errMsg(e));
    }
  }, [setError]);

  const loadFromTemplate = React.useCallback(
    async (templateId: string) => {
      if (!templateId) return;
      setError("");
      try {
        const template = await apiJson(`/run-templates/${templateId}`);
        const tpl = template as any;
        if (tpl?.template_kind === "declarative") {
          setDeclarativeContract(tpl.declarative_spec || null);
          setForm((prev) => ({
            ...applyTemplateToScheduleForm(prev, tpl, prev.run),
            name: prev.name || tpl.name || "",
          }));
          return;
        }
        setDeclarativeContract(null);
        const runForm = templateToCreateForm(tpl) as CreateForm;
        setForm((prev) => applyTemplateToScheduleForm(prev, tpl, runForm));
      } catch (e) {
        setError(errMsg(e));
      }
    },
    [setError],
  );

  const loadScheduleForEdit = React.useCallback(
    async (id: string): Promise<boolean> => {
      const seq = ++editLoadSeqRef.current;
      setError("");
      setFormReady(false);
      setDeclarativeContract(null);
      try {
        const schedule = await apiJson(`/schedules/${id}`);
        if (seq !== editLoadSeqRef.current) return false;
        setForm(scheduleToForm(schedule));
        setFormReady(true);
        return true;
      } catch (e) {
        if (seq !== editLoadSeqRef.current) return false;
        setError(errMsg(e));
        setFormReady(true);
        return false;
      }
    },
    [setError],
  );

  const openScheduleCreate = React.useCallback(
    (templateId = "") => {
      resetScheduleForm();
      go({ tab: "schedules", scheduleSubview: "create", templateId });
      if (templateId) void loadFromTemplate(templateId);
    },
    [go, loadFromTemplate, resetScheduleForm],
  );

  const openScheduleEdit = React.useCallback(
    async (id: string) => {
      go({ tab: "schedules", scheduleSubview: "edit", scheduleId: id });
      await loadScheduleForEdit(id);
    },
    [go, loadScheduleForEdit],
  );

  const openScheduleHistory = React.useCallback(
    (id: string) => {
      go({ tab: "list", scheduleId: id });
    },
    [go],
  );

  const submitSchedule = React.useCallback(
    async (mode: "create" | "edit", declarativeValues?: Record<string, any>) => {
      setSubmitting(true);
      setError("");
      try {
        const payload = schedulePayload(form, { declarativeValues });

        if (mode === "create") {
          await apiJson("/schedules", { method: "POST", body: JSON.stringify(payload) });
          setFlash("Schedule created");
        } else {
          await apiJson(`/schedules/${form.id}`, { method: "PUT", body: JSON.stringify(payload) });
          setFlash("Schedule updated");
        }
        // Returning to the list subview re-runs its load effect; no explicit fetch needed here.
        setPage(0);
        go({ tab: "schedules", scheduleSubview: "list" });
      } catch (e) {
        setError(errMsg(e));
      } finally {
        setSubmitting(false);
      }
    },
    [form, go, setError, setFlash],
  );

  const deleteSchedule = React.useCallback(
    async (id: string, name: string) => {
      if (!window.confirm(`Delete schedule "${name || id}"? Its stored secrets are removed too.`)) return;
      setError("");
      try {
        await apiJson(`/schedules/${id}`, { method: "DELETE" });
        setFlash("Schedule deleted");
        await loadList();
      } catch (e) {
        setError(errMsg(e));
      }
    },
    [loadList, setError, setFlash],
  );

  const toggleEnabled = React.useCallback(
    async (schedule: any) => {
      setError("");
      try {
        const action = schedule.enabled ? "disable" : "enable";
        const updated = await apiJson(`/schedules/${schedule.id}/${action}`, { method: "POST" });
        setItems((prev) => prev.map((s) => (s.id === schedule.id ? updated : s)));
        setFlash(schedule.enabled ? "Schedule disabled" : "Schedule enabled");
      } catch (e) {
        setError(errMsg(e));
      }
    },
    [setError, setFlash],
  );

  const runNow = React.useCallback(
    async (id: string) => {
      setError("");
      try {
        const run = (await apiJson(`/schedules/${id}/trigger`, { method: "POST" })) as any;
        setFlash("Run started");
        go({ tab: "detail", runId: String(run.id), detailSubview: "info" });
      } catch (e) {
        setError(errMsg(e));
      }
    },
    [go, setError, setFlash],
  );

  React.useEffect(() => {
    if (tab === "schedules" && scheduleSubview === "list") loadList();
  }, [tab, scheduleSubview, loadList]);

  React.useEffect(() => {
    if (tab !== "schedules") return;
    void loadTimezones();
    void loadProfiles();
  }, [tab, loadProfiles, loadTimezones]);

  React.useEffect(() => {
    if (tab !== "schedules" || scheduleSubview === "list") return;
    const cron = form.cronExpression.trim();
    if (!cron) {
      setPreview([]);
      setPreviewError("");
      return;
    }
    const timer = setTimeout(() => {
      void (async () => {
        try {
          const data = (await apiJson("/schedules/preview", {
            method: "POST",
            body: JSON.stringify({ cron_expression: cron, timezone: form.timezone, count: 3 }),
          })) as any;
          setPreview(data.next_fire_times || []);
          setPreviewError("");
        } catch (e) {
          setPreview([]);
          setPreviewError(errMsg(e));
        }
      })();
    }, PREVIEW_DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [tab, scheduleSubview, form.cronExpression, form.timezone]);

  return {
    items,
    total,
    page,
    loading,
    form,
    formReady,
    submitting,
    profiles,
    timezones,
    declarativeContract,
    preview,
    previewError,
    setPage,
    setForm,
    resetScheduleForm,
    loadList,
    loadFromTemplate,
    loadScheduleForEdit,
    openScheduleCreate,
    openScheduleEdit,
    openScheduleHistory,
    submitSchedule,
    deleteSchedule,
    toggleEnabled,
    runNow,
  };
}

export type SchedulesState = ReturnType<typeof useSchedules>;
