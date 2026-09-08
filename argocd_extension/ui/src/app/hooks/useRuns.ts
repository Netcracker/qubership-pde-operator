import { apiJson, apiText, downloadArtifact } from "../../api/client";
import { errMsg, paginatedQuery } from "../../lib/format";
import type { UserPreferences } from "../../lib/userPreferences";
import { emptyCreateForm, emptyRetryForm, ensureKvPairs, kvPairsToRecord, kvPairsToText, normalizePipelineData, parseKvPairs } from "../../lib/runs";
import { templateToCreateForm } from "../../lib/templates";
import type { CreateForm, LogStatus, ReportStatus, RetryForm } from "../../lib/types";
import type { AppMessages } from "./useAppMessages";
import type { GoFn } from "./useAppRouting";

type UseRunsArgs = {
  tab: string;
  createMode: string;
  runId: string;
  templateId: string;
  detailSubview: string;
  go: GoFn;
  messages: AppMessages;
  preferences: UserPreferences;
};

type ArtifactLoadOpts = { quiet?: boolean; sourceUpdatedAt?: string | null };

function shouldReloadArtifact(status: LogStatus, updatedAt: string | null, lastLoadedAt: string | null): boolean {
  if (status === "loading") return false;
  if (status === "ready" && updatedAt === lastLoadedAt) return false;
  return true;
}

export function useRuns({ tab, createMode, runId, templateId, detailSubview, go, messages, preferences }: UseRunsArgs) {
  const { setError, setFlash } = messages;
  const [runs, setRuns] = React.useState<any[]>([]);
  const [total, setTotal] = React.useState(0);
  const [page, setPage] = React.useState(0);
  const [searchQuery, setSearchQuery] = React.useState("");
  const [debouncedSearchQuery, setDebouncedSearchQuery] = React.useState("");
  const [templateName, setTemplateName] = React.useState("");
  const lastTemplateFilterIdRef = React.useRef("");
  const [listLoading, setListLoading] = React.useState(false);
  const [detailLoading, setDetailLoading] = React.useState(false);
  const [detail, setDetail] = React.useState<any>(null);
  const [logText, setLogText] = React.useState("");
  const [logStatus, setLogStatus] = React.useState<LogStatus>("idle");
  const [logError, setLogError] = React.useState("");
  const [report, setReport] = React.useState<any>(null);
  const [reportStatus, setReportStatus] = React.useState<ReportStatus>("idle");
  const [reportError, setReportError] = React.useState("");
  const lastLogUpdatedAtRef = React.useRef<string | null>(null);
  const lastReportUpdatedAtRef = React.useRef<string | null>(null);
  const logLoadSeqRef = React.useRef(0);
  const reportLoadSeqRef = React.useRef(0);
  const [profileOptions, setProfileOptions] = React.useState<any[]>([]);
  const [form, setForm] = React.useState<CreateForm>(emptyCreateForm());
  const [retryForm, setRetryForm] = React.useState<RetryForm>(emptyRetryForm());
  const [submitting, setSubmitting] = React.useState(false);
  const [templateKind, setTemplateKind] = React.useState<"simple" | "declarative">("simple");
  const [declarativeContract, setDeclarativeContract] = React.useState<any | null>(null);
  const [activeTemplateId, setActiveTemplateId] = React.useState("");
  const [activeTemplateName, setActiveTemplateName] = React.useState("");
  const [formReady, setFormReady] = React.useState(!templateId);

  const resetDetail = React.useCallback(() => {
    logLoadSeqRef.current += 1;
    reportLoadSeqRef.current += 1;
    setDetail(null);
    setLogText("");
    setLogStatus("idle");
    setLogError("");
    setReport(null);
    setReportStatus("idle");
    setReportError("");
    lastLogUpdatedAtRef.current = null;
    lastReportUpdatedAtRef.current = null;
  }, []);

  const resetCreateForm = React.useCallback(() => {
    setForm(emptyCreateForm());
    setTemplateKind("simple");
    setDeclarativeContract(null);
    setActiveTemplateId("");
    setActiveTemplateName("");
    setFormReady(true);
  }, []);

  React.useEffect(() => {
    const t = setTimeout(() => setDebouncedSearchQuery(searchQuery), 250);
    return () => clearTimeout(t);
  }, [searchQuery]);

  const templateFilterId = tab === "list" ? templateId || "" : "";
  const effectivePage = page;

  const loadRuns = React.useCallback(
    async ({ quiet = false } = {}) => {
      if (!quiet) setListLoading(true);
      try {
        const params = paginatedQuery(effectivePage);
        if (debouncedSearchQuery.trim()) params.set("q", debouncedSearchQuery.trim());
        if (templateFilterId) params.set("created_from_template_id", templateFilterId);
        const data = (await apiJson(`/runs?${params}`)) as any;
        setRuns(data.items || []);
        setTotal(data.total || 0);
        if (!quiet) setError("");
      } catch (e) {
        if (!quiet) setError(errMsg(e));
      } finally {
        if (!quiet) setListLoading(false);
      }
    },
    [debouncedSearchQuery, effectivePage, setError, templateFilterId],
  );

  const clearTemplateFilter = React.useCallback(() => {
    setPage(0);
    go({ tab: "list", templateId: "" });
  }, [go]);

  const loadDetail = React.useCallback(
    async (id: string, { quiet = false } = {}) => {
      if (!quiet) setDetailLoading(true);
      try {
        const data = await apiJson(`/runs/${id}`);
        setDetail(data);
        if (!quiet) setError("");
        return data;
      } catch (e) {
        if (!quiet) setError(errMsg(e));
        return null;
      } finally {
        if (!quiet) setDetailLoading(false);
      }
    },
    [setError],
  );

  const loadLog = React.useCallback(async (id: string, { quiet = false, sourceUpdatedAt = null }: ArtifactLoadOpts = {}) => {
    const seq = ++logLoadSeqRef.current;
    setLogStatus((prev) => {
      if (quiet && prev === "not_ready") return prev;
      return "loading";
    });
    if (!quiet) setLogError("");
    try {
      const text = await apiText(`/runs/${id}/artifacts/log`);
      if (seq !== logLoadSeqRef.current) return;
      setLogText(text);
      setLogStatus("ready");
      if (sourceUpdatedAt) lastLogUpdatedAtRef.current = sourceUpdatedAt;
    } catch (e: any) {
      if (seq !== logLoadSeqRef.current) return;
      if (e?.status === 404 || e?.message === "not_found") {
        setLogText("");
        setLogStatus("not_ready");
        return;
      }
      setLogStatus("error");
      setLogError(errMsg(e));
    }
  }, []);

  const loadReport = React.useCallback(async (id: string, { quiet = false, sourceUpdatedAt = null }: ArtifactLoadOpts = {}) => {
    const seq = ++reportLoadSeqRef.current;
    setReportStatus((prev) => {
      if (quiet && prev === "not_ready") return prev;
      return "loading";
    });
    if (!quiet) setReportError("");
    try {
      const data = await apiJson(`/runs/${id}/artifacts/report`);
      if (seq !== reportLoadSeqRef.current) return;
      setReport(data);
      setReportStatus("ready");
      if (sourceUpdatedAt) lastReportUpdatedAtRef.current = sourceUpdatedAt;
    } catch (e: any) {
      if (seq !== reportLoadSeqRef.current) return;
      if (e?.status === 404 || e?.message === "not_found") {
        setReport(null);
        setReportStatus("not_ready");
        return;
      }
      setReportStatus("error");
      setReportError(errMsg(e));
    }
  }, []);

  const loadProfileOptions = React.useCallback(async () => {
    try {
      const data = (await apiJson("/profiles?limit=500")) as any;
      const items = data.items || [];
      setProfileOptions(items);
      setForm((prev) => {
        if (items.length && !items.some((p: any) => p.id === prev.profile_id)) {
          return { ...prev, profile_id: items[0].id };
        }
        return prev;
      });
      return items;
    } catch {
      setProfileOptions([]);
      return [];
    }
  }, []);

  const loadFromTemplate = React.useCallback(
    async (id: string) => {
      setError("");
      setFormReady(false);
      setActiveTemplateId(id);
      setActiveTemplateName("");
      try {
        const [template, profiles] = await Promise.all([
          apiJson(`/run-templates/${id}`) as Promise<any>,
          loadProfileOptions(),
        ]);
        if (template?.template_kind === "declarative") {
          setTemplateKind("declarative");
          setDeclarativeContract(template.declarative_spec || null);
          setForm(emptyCreateForm());
          setActiveTemplateName(template.name || id);
          setFormReady(true);
          return;
        }

        setTemplateKind("simple");
        setDeclarativeContract(null);
        let next = templateToCreateForm(template);
        const profileExists = profiles.some((p: any) => p.id === next.profile_id);
        if (!profileExists) {
          next = { ...next, profile_id: "default" };
          setFlash(`Profile "${template.profile_id}" is missing; remapped to default`);
        }
        setForm(next);
        setActiveTemplateName(template.name || id);
        setFormReady(true);
      } catch (e) {
        setError(errMsg(e));
        resetCreateForm();
      }
    },
    [loadProfileOptions, resetCreateForm, setError, setFlash],
  );

  const loadRetryForm = React.useCallback(
    async (id: string) => {
      setFormReady(false);
      setRetryForm(emptyRetryForm());
      try {
        const run = (await apiJson(`/runs/${id}`)) as any;
        setDetail(run);
        setRetryForm({ retry_vars: ensureKvPairs(parseKvPairs(run.retry_vars)), pde_image: "" });
        setError("");
        setFormReady(true);
      } catch (e) {
        setError(errMsg(e));
        setFormReady(true);
      }
    },
    [setError],
  );

  const openDetail = React.useCallback(
    (id: string, subview: "info" | "logs" | "viewer" = "info") => {
      resetDetail();
      go({ tab: "detail", runId: id, detailSubview: subview });
    },
    [go, resetDetail],
  );

  const openRetry = React.useCallback(
    (id: string) => {
      go({ tab: "create", createMode: "retry", runId: id });
      void loadRetryForm(id);
    },
    [go, loadRetryForm],
  );

  const openFromTemplate = React.useCallback(
    (id: string) => {
      go({ tab: "create", createMode: "create", templateId: id });
    },
    [go],
  );

  const handleDownload = React.useCallback(
    async (id: string, kind: string) => {
      setError("");
      try {
        await downloadArtifact(id, kind);
      } catch (e) {
        setError(errMsg(e));
      }
    },
    [setError],
  );

  const cancelRun = React.useCallback(
    async (id: string) => {
      setError("");
      try {
        await apiJson(`/runs/${id}/cancel`, { method: "POST" });
        setFlash("Cancel requested");
        if (tab === "detail") await loadDetail(id);
        else await loadRuns();
      } catch (e) {
        setError(errMsg(e));
      }
    },
    [loadDetail, loadRuns, setError, setFlash, tab],
  );

  const submitCreate = React.useCallback(async (declarativeValues?: Record<string, any>) => {
    setSubmitting(true);
    setError("");
    try {
      if (createMode === "retry") {
        const run = (await apiJson(`/runs/${runId}/retry`, {
          method: "POST",
          body: JSON.stringify({
            retry_vars: kvPairsToText(retryForm.retry_vars),
            pde_image: retryForm.pde_image.trim() || null,
          }),
        })) as any;
        setFlash("Retry started");
        openDetail(String(run.id));
      } else {
        if (templateKind === "declarative") {
          const tplId = activeTemplateId || templateId || "";
          await apiJson(`/run-templates/${tplId}/declarative-runs`, {
            method: "POST",
            body: JSON.stringify({ values: declarativeValues || {} }),
          });
        } else {
          await apiJson("/runs", {
            method: "POST",
            body: JSON.stringify({
              profile_id: form.profile_id || "default",
              pipeline_data: normalizePipelineData(form.pipeline_data),
              pipeline_vars: kvPairsToText(form.pipeline_vars),
              pipeline_vars_secure: kvPairsToText(form.pipeline_vars_secure),
              is_dry_run: form.is_dry_run,
              log_level: form.log_level,
              env_vars: kvPairsToRecord(form.env_vars),
              pde_image: form.pde_image.trim() || null,
              created_from_template_id: activeTemplateId || templateId || null,
            }),
          });
        }
        setFlash("Run created");
        setPage(0);
        go({ tab: "list" });
        await loadRuns();
      }
    } catch (e) {
      setError(errMsg(e));
    } finally {
      setSubmitting(false);
    }
  }, [
    activeTemplateId,
    createMode,
    form,
    go,
    loadRuns,
    openDetail,
    retryForm,
    runId,
    setError,
    setFlash,
    templateKind,
    templateId,
  ]);

  React.useEffect(() => {
    if (tab === "list") loadRuns();
  }, [tab, loadRuns]);

  React.useEffect(() => {
    if (tab !== "list") return;
    if (lastTemplateFilterIdRef.current !== templateFilterId) {
      lastTemplateFilterIdRef.current = templateFilterId;
      setPage(0);
    }
  }, [tab, templateFilterId]);

  React.useEffect(() => {
    if (tab !== "list") {
      setTemplateName("");
      return;
    }
    if (!templateId) {
      setTemplateName("");
      return;
    }

    let cancelled = false;
    void (async () => {
      try {
        const tpl = await apiJson(`/run-templates/${templateId}`) as any;
        if (cancelled) return;
        setTemplateName(tpl?.name || String(templateId));
      } catch {
        if (cancelled) return;
        setTemplateName(String(templateId));
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [tab, templateId]);

  React.useEffect(() => {
    if (tab === "detail" && runId) loadDetail(runId);
  }, [tab, runId, loadDetail]);

  React.useEffect(() => {
    if (tab !== "detail" || !runId) return;
    logLoadSeqRef.current += 1;
    reportLoadSeqRef.current += 1;
    setLogText("");
    setLogStatus("idle");
    setLogError("");
    setReport(null);
    setReportStatus("idle");
    setReportError("");
    lastLogUpdatedAtRef.current = null;
    lastReportUpdatedAtRef.current = null;
  }, [runId]);

  React.useEffect(() => {
    if (tab !== "detail" || !runId || detailSubview !== "logs" || !detail) return;
    const ts = detail.log_updated_at ?? null;
    if (!shouldReloadArtifact(logStatus, ts, lastLogUpdatedAtRef.current)) return;
    void loadLog(runId, { quiet: logStatus === "not_ready", sourceUpdatedAt: ts });
  }, [tab, runId, detailSubview, detail?.log_updated_at, logStatus, loadLog]);

  React.useEffect(() => {
    if (tab !== "detail" || !runId || detailSubview !== "viewer" || !detail) return;
    const ts = detail.report_updated_at ?? null;
    if (!shouldReloadArtifact(reportStatus, ts, lastReportUpdatedAtRef.current)) return;
    void loadReport(runId, { quiet: reportStatus === "not_ready", sourceUpdatedAt: ts });
  }, [tab, runId, detailSubview, detail?.report_updated_at, reportStatus, loadReport]);

  React.useLayoutEffect(() => {
    if (tab === "create" && createMode === "create" && templateId) {
      setFormReady(false);
    }
  }, [tab, createMode, templateId]);

  React.useEffect(() => {
    if (tab === "create" && createMode === "create" && templateId) {
      void loadFromTemplate(templateId);
    }
  }, [tab, createMode, templateId, loadFromTemplate]);

  React.useEffect(() => {
    if (tab === "create" && createMode === "create" && !templateId) loadProfileOptions();
  }, [tab, createMode, templateId, loadProfileOptions]);

  React.useEffect(() => {
    if (!preferences.autoRefresh) return;
    const timer = setInterval(() => {
      void (async () => {
        if (tab === "list") {
          loadRuns({ quiet: true });
          return;
        }
        if (tab === "detail" && runId) {
          const data = await loadDetail(runId, { quiet: true });
          if (!data) return;
          if (detailSubview === "logs") {
            const ts = data.log_updated_at ?? null;
            if (shouldReloadArtifact(logStatus, ts, lastLogUpdatedAtRef.current)) {
              void loadLog(runId, { quiet: true, sourceUpdatedAt: ts });
            }
          }
          if (detailSubview === "viewer") {
            const ts = data.report_updated_at ?? null;
            if (shouldReloadArtifact(reportStatus, ts, lastReportUpdatedAtRef.current)) {
              void loadReport(runId, { quiet: true, sourceUpdatedAt: ts });
            }
          }
        }
      })();
    }, preferences.autoRefreshIntervalMs);
    return () => clearInterval(timer);
  }, [
    preferences.autoRefresh,
    preferences.autoRefreshIntervalMs,
    tab,
    runId,
    detailSubview,
    logStatus,
    reportStatus,
    loadRuns,
    loadDetail,
    loadLog,
    loadReport,
  ]);

  return {
    runs,
    total,
    page,
    searchQuery,
    templateFilter: templateFilterId,
    templateName,
    listLoading,
    detailLoading,
    detail,
    logText,
    logStatus,
    logError,
    report,
    reportStatus,
    reportError,
    profileOptions,
    form,
    retryForm,
    submitting,
    formReady,
    templateKind,
    declarativeContract,
    activeTemplateId,
    activeTemplateName,
    setPage,
    setSearchQuery,
    clearTemplateFilter,
    setForm,
    setRetryForm,
    resetDetail,
    resetCreateForm,
    loadRuns,
    loadDetail,
    loadLog,
    loadReport,
    loadProfileOptions,
    loadFromTemplate,
    loadRetryForm,
    openDetail,
    openRetry,
    openFromTemplate,
    handleDownload,
    cancelRun,
    submitCreate,
  };
}

export type RunsState = ReturnType<typeof useRuns>;
