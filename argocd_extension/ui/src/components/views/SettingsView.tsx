import React from "react";
import type { CleanupForm } from "../../lib/types";
import type { UserPreferences } from "../../lib/userPreferences";
import { Btn } from "../ui";

function SettingsRow(props: { label: string; description?: string; alwaysShowDescription?: boolean; children: any }) {
  const tooltip = props.alwaysShowDescription ? undefined : props.description;

  return (
    <div className="pde-settings-row">
      <div className="pde-settings-row-main" title={tooltip}>
        <span className="pde-settings-row-label">{props.label}</span>
        <div className="pde-settings-row-control">{props.children}</div>
      </div>
      {props.alwaysShowDescription && props.description ? (
        <p className="pde-settings-row-desc pde-settings-row-desc-visible">{props.description}</p>
      ) : null}
    </div>
  );
}

function SettingsSwitch(props: { checked: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <label className="pde-settings-switch">
      <input
        type="checkbox"
        checked={props.checked}
        aria-label={props.label}
        onChange={(e: any) => props.onChange(e.target.checked)}
      />
      <span className="pde-settings-switch-slider" aria-hidden="true" />
    </label>
  );
}

export function SettingsView(props: {
  preferences: UserPreferences;
  cleanupForm: CleanupForm;
  submitting: boolean;
  result: string;
  importSubmitting?: boolean;
  importResult?: string;
  canWrite?: boolean;
  onAdminMode: (v: boolean) => void;
  onAutoRefresh: (v: boolean) => void;
  onAutoRefreshIntervalMs: (v: number) => void;
  onCleanupForm: (form: CleanupForm) => void;
  onSubmitCleanup: () => void;
  onImportConfig?: (file: File, mode: "merge" | "replace") => void;
  onClearStoredState: () => void;
}) {
  const {
    preferences,
    cleanupForm,
    submitting,
    result,
    importSubmitting = false,
    importResult = "",
    canWrite = true,
  } = props;
  const importInputRef = React.useRef<HTMLInputElement>(null);
  const importModeRef = React.useRef<"merge" | "replace">("merge");

  return (
    <section className="pde-settings">
      <div className="pde-settings-section">
        <h2 className="pde-settings-section-title">General</h2>
        <div className="pde-settings-rows">
          {canWrite ? (
            <SettingsRow label="Admin Mode" description="Show template management, profiles, and other advanced controls.">
              <SettingsSwitch checked={preferences.adminMode} onChange={props.onAdminMode} label="Admin Mode" />
            </SettingsRow>
          ) : null}

          <SettingsRow label="Auto Refresh" description="Automatically refresh list and run detail views on an interval.">
            <SettingsSwitch checked={preferences.autoRefresh} onChange={props.onAutoRefresh} label="Auto Refresh" />
          </SettingsRow>

          <SettingsRow label="Auto Refresh Interval (ms)" description="Polling interval for auto refresh. Allowed range: 1000–300000 ms.">
            <input
              className="pde-input pde-settings-input"
              type="number"
              min={1000}
              max={300000}
              step={500}
              value={preferences.autoRefreshIntervalMs}
              onChange={(e: any) => props.onAutoRefreshIntervalMs(Number(e.target.value))}
            />
          </SettingsRow>

          <SettingsRow label="Reset UI state" description="Reset UI preferences saved in this browser (settings above).">
            <Btn onClick={props.onClearStoredState} icon="trash">
              Clear
            </Btn>
          </SettingsRow>
        </div>
      </div>

      {canWrite ? (
        <>
          <div className="pde-settings-section">
            <h2 className="pde-settings-section-title">Config import</h2>
            <div className="pde-settings-rows">
              <SettingsRow
                label="Load configs"
                description="Import a multi-document YAML with Profile, SimpleRunTemplate, and/or `.ui-variables` declarative templates. Merge upserts profiles and always adds templates. Replace wipes templates and non-default profiles first (default profile is kept)."
                alwaysShowDescription
              >
                <div className="pde-settings-cleanup-form">
                  <Btn
                    onClick={() => {
                      importModeRef.current = "merge";
                      importInputRef.current?.click();
                    }}
                    disabled={importSubmitting || !props.onImportConfig}
                    icon="upload"
                  >
                    {importSubmitting ? "Loading..." : "Merge"}
                  </Btn>
                  <Btn
                    onClick={() => {
                      importModeRef.current = "replace";
                      importInputRef.current?.click();
                    }}
                    disabled={importSubmitting || !props.onImportConfig}
                    icon="sync"
                  >
                    {importSubmitting ? "Loading..." : "Replace all & load"}
                  </Btn>
                  <input
                    ref={importInputRef}
                    type="file"
                    accept=".yaml,.yml"
                    style={{ display: "none" }}
                    onChange={(e: any) => {
                      const file: File | undefined = e.target.files?.[0];
                      if (!file || !props.onImportConfig) return;
                      props.onImportConfig(file, importModeRef.current);
                      e.target.value = "";
                    }}
                  />
                </div>
              </SettingsRow>
            </div>
            {importResult ? <p className="pde-settings-result">{importResult}</p> : null}
          </div>

          <div className="pde-settings-section">
            <h2 className="pde-settings-section-title">Cleanup</h2>
            <div className="pde-settings-rows">
              <SettingsRow
                label="Manual cleanup"
                description="Remove runs older than N days and their artifacts."
                alwaysShowDescription
              >
                <form
                  className="pde-settings-cleanup-form"
                  onSubmit={(e: any) => {
                    e.preventDefault();
                    props.onSubmitCleanup();
                  }}
                >
                  <input
                    className="pde-input pde-settings-input pde-settings-input-days"
                    type="number"
                    min={0}
                    step={1}
                    value={cleanupForm.older_than_days}
                    required
                    aria-label="Older than (days)"
                    onChange={(e: any) => props.onCleanupForm({ older_than_days: Number(e.target.value) })}
                  />
                  <span className="pde-settings-input-suffix">days</span>
                  <Btn primary type="submit" disabled={submitting}>
                    {submitting ? "Cleaning..." : "Run cleanup"}
                  </Btn>
                </form>
              </SettingsRow>
            </div>
            {result ? <p className="pde-settings-result">{result}</p> : null}
          </div>
        </>
      ) : null}
    </section>
  );
}
