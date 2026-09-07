import React from "react";
import { apiJson } from "../../api/client";
import { errMsg } from "../../lib/format";
import type { CleanupForm } from "../../lib/types";
import type { AppMessages } from "./useAppMessages";
import type { UserPreferencesState } from "./useUserPreferences";
import { getHost } from "../../host/registry";

const DEFAULT_CLEANUP_DAYS = 30;

type UseSettingsArgs = {
  messages: AppMessages;
  preferences: UserPreferencesState;
};

export function useSettings({ messages, preferences }: UseSettingsArgs) {
  const { setError, setFlash } = messages;
  const [cleanupForm, setCleanupForm] = React.useState<CleanupForm>({ older_than_days: DEFAULT_CLEANUP_DAYS });
  const [cleanupSubmitting, setCleanupSubmitting] = React.useState(false);
  const [cleanupResult, setCleanupResult] = React.useState("");
  const [importSubmitting, setImportSubmitting] = React.useState(false);
  const [importResult, setImportResult] = React.useState("");

  const resetSettingsForm = React.useCallback(() => {
    setCleanupResult("");
    setImportResult("");
    setCleanupForm({ older_than_days: DEFAULT_CLEANUP_DAYS });
  }, []);

  const submitCleanup = React.useCallback(async () => {
    setCleanupSubmitting(true);
    setError("");
    setCleanupResult("");
    try {
      const days = Math.max(0, Math.round(Number(cleanupForm.older_than_days)));
      if (!Number.isFinite(days)) throw new Error("Days must be a positive integer");
      const olderThan = new Date(Date.now() - days * 24 * 60 * 60 * 1000).toISOString();
      const result = (await apiJson("/manage/cleanup", {
        method: "POST",
        body: JSON.stringify({ older_than: olderThan }),
      })) as any;
      const message = `Deleted ${result.deleted} run(s)` + (result.failed ? `, failed ${result.failed}` : "");
      setCleanupResult(message);
      setFlash(message);
    } catch (e) {
      setError(errMsg(e));
    } finally {
      setCleanupSubmitting(false);
    }
  }, [cleanupForm.older_than_days, setError, setFlash]);

  const importConfig = React.useCallback(
    async (file: File, mode: "merge" | "replace") => {
      if (mode === "replace") {
        const ok = window.confirm(
          "Replace all templates and non-default profiles with the contents of this file? The default profile is kept and updated if present in the file.",
        );
        if (!ok) return;
      }
      setImportSubmitting(true);
      setError("");
      setImportResult("");
      try {
        const host = getHost();
        const formData = new FormData();
        formData.append("file", file);
        formData.append("mode", mode);
        const res = await fetch(`${host.apiBase}/manage/config/import`, {
          method: "POST",
          headers: host.authHeaders(),
          credentials: host.credentials,
          body: formData,
        });
        if (!res.ok) {
          const text = await res.text();
          let detail = res.statusText;
          try {
            const body = text ? JSON.parse(text) : null;
            if (body && typeof body === "object" && "detail" in body) detail = String(body.detail);
            else if (text.trim()) detail = text.trim();
          } catch {
            if (text.trim()) detail = text.trim();
          }
          throw new Error(detail);
        }
        const message = mode === "replace" ? "Config replaced" : "Config merged";
        setImportResult(message);
        setFlash(message);      } catch (e) {
        setError(errMsg(e));
      } finally {
        setImportSubmitting(false);
      }
    },
    [setError, setFlash],
  );

  const clearStoredState = React.useCallback(() => {
    if (!window.confirm("Clear all saved UI settings from this browser?")) return;
    preferences.resetPreferences();
    setFlash("Saved UI settings cleared");
  }, [preferences, setFlash]);

  return {
    preferences: preferences.preferences,
    setAdminMode: preferences.setAdminMode,
    setAutoRefresh: preferences.setAutoRefresh,
    setAutoRefreshIntervalMs: preferences.setAutoRefreshIntervalMs,
    cleanupForm,
    cleanupSubmitting,
    cleanupResult,
    importSubmitting,
    importResult,
    setCleanupForm,
    resetSettingsForm,
    submitCleanup,
    importConfig,
    clearStoredState,
  };
}

export type SettingsState = ReturnType<typeof useSettings>;
