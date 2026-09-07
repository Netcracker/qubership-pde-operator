import { CatalogView } from "../components/views/CatalogView";
import { CreateView } from "../components/views/CreateView";
import { DetailView } from "../components/views/DetailView";
import { ListView } from "../components/views/ListView";
import { ProfilesView } from "../components/views/ProfilesView";
import { SettingsView } from "../components/views/SettingsView";
import { StatusMessage, TabBar } from "../components/ui";
import { useAppMessages } from "./hooks/useAppMessages";
import { useAppRouting, type RouteSideEffects } from "./hooks/useAppRouting";
import { useAuthToken } from "./hooks/useAuthToken";
import { useCapabilities } from "./hooks/useCapabilities";
import { useCatalog } from "./hooks/useCatalog";
import { useProfiles } from "./hooks/useProfiles";
import { useRuns } from "./hooks/useRuns";
import { useSettings } from "./hooks/useSettings";
import { useUserPreferences } from "./hooks/useUserPreferences";

export function PdeExtensionApp(_props: unknown) {
  const messages = useAppMessages();
  const { host, apiToken, saveToken } = useAuthToken();
  const capabilities = useCapabilities();
  const effectsRef = React.useRef<RouteSideEffects>({
    onCreateRoute: () => {},
    onCatalogCreateRoute: () => {},
    onCatalogEditRoute: () => {},
    onProfilesCreateRoute: () => {},
    onProfilesEditRoute: () => {},
    onRetryRoute: () => {},
    onSettingsRoute: () => {},
  });

  const routing = useAppRouting(effectsRef);
  const { tab, createMode, runId, templateId, profileSubview, catalogSubview, detailSubview, setProfileSubview, setCatalogSubview, go } =
    routing;

  const userPreferences = useUserPreferences();
  const runs = useRuns({ tab, createMode, runId, templateId, detailSubview, go, messages, preferences: userPreferences.preferences });
  const catalog = useCatalog({ tab, catalogSubview, go, messages });
  const profiles = useProfiles({
    tab,
    profileSubview,
    go,
    messages,
    onProfilesChanged: runs.loadProfileOptions,
  });
  const settings = useSettings({ messages, preferences: userPreferences });
  const canWrite = capabilities.canWrite;
  const adminMode = canWrite && userPreferences.preferences.adminMode;

  React.useEffect(() => {
    if (!capabilities.loaded) return;
    if (canWrite) return;
    if (tab === "create" || tab === "profiles") {
      go({ tab: "catalog", catalogSubview: "list" }, { replace: true });
      return;
    }
    if (tab === "catalog" && catalogSubview !== "list") {
      catalog.resetTemplateForm();
      go({ tab: "catalog", catalogSubview: "list" }, { replace: true });
    }
  }, [capabilities.loaded, canWrite, tab, catalogSubview, go, catalog.resetTemplateForm]);

  React.useEffect(() => {
    if (adminMode) return;
    if (tab === "profiles") {
      go({ tab: "catalog", catalogSubview: "list" }, { replace: true });
      return;
    }
    if (tab === "catalog" && catalogSubview !== "list") {
      catalog.resetTemplateForm();
      go({ tab: "catalog", catalogSubview: "list" }, { replace: true });
    }
  }, [adminMode, tab, catalogSubview, go, catalog.resetTemplateForm]);

  effectsRef.current = {
    onCreateRoute: runs.resetCreateForm,
    onCatalogCreateRoute: catalog.resetTemplateForm,
    onCatalogEditRoute: catalog.loadForEdit,
    onProfilesCreateRoute: profiles.resetProfileForm,
    onProfilesEditRoute: profiles.loadProfileForEdit,
    onRetryRoute: runs.loadRetryForm,
    onSettingsRoute: settings.resetSettingsForm,
  };

  return (
    <div className="pde-ext">
      <div className="pde-shell">
        {host.tokenField ? (
          <header className="pde-header">
            <label className="pde-token-field">
              API token
              <input
                className="pde-input"
                type="password"
                value={apiToken}
                placeholder="Bearer admin token"
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => saveToken(e.target.value)}
              />
            </label>
          </header>
        ) : null}

        <TabBar
          tab={tab}
          detailEnabled={!!runId}
          adminMode={adminMode}
          canWrite={canWrite}
          onTab={(next) => {
            if (next === "catalog") {
              catalog.resetTemplateForm();
              go({ tab: "catalog", catalogSubview: "list" });
            } else if (next === "list") go({ tab: "list" });
            else if (next === "detail") go({ tab: "detail", runId, detailSubview });
            else if (next === "create") {
              if (!canWrite) return;
              runs.resetCreateForm();
              go({ tab: "create", createMode: "create" });
            } else if (next === "profiles") {
              if (!adminMode) return;
              profiles.resetProfileForm();
              go({ tab: "profiles", profileSubview: "list" });
            } else if (next === "settings") {
              settings.resetSettingsForm();
              go({ tab: "settings" });
            }
          }}
        />

        <StatusMessage kind="flash" text={messages.flash} onDismiss={messages.clearFlash} />
        <StatusMessage kind="error" text={messages.error} onDismiss={messages.clearError} />

        {tab === "catalog" ? (
          <CatalogView
            subview={catalogSubview}
            adminMode={adminMode}
            canWrite={canWrite}
            templates={catalog.items}
            total={catalog.total}
            page={catalog.page}
            loading={catalog.loading}
            formReady={catalog.formReady}
            query={catalog.query}
            tagFilter={catalog.tagFilter}
            templateForm={catalog.templateForm}
            profiles={catalog.profiles}
            submitting={catalog.submitting}
            onQuery={catalog.setQuery}
            onTagFilter={catalog.setTagFilter}
            onSubview={(next) => {
              if (!adminMode && next !== "list") return;
              if (next === "list") {
                catalog.resetTemplateForm();
                go({ tab: "catalog", catalogSubview: "list" });
              } else if (next === "create") {
                catalog.resetTemplateForm();
                go({ tab: "catalog", catalogSubview: "create" });
              } else {
                setCatalogSubview(next);
              }
            }}
            onPage={catalog.setPage}
            onRefresh={() => catalog.loadList()}
            onOpen={catalog.openCreateRun}
            onHistory={catalog.openHistory}
            onEdit={catalog.openEdit}
            onDelete={catalog.deleteTemplate}
            uploadingDeclarative={catalog.uploadingDeclarative}
            onUploadDeclarativeTemplate={catalog.uploadDeclarativeTemplate}
            onForm={catalog.setTemplateForm}
            onSubmitCreate={() => catalog.submitTemplate("create")}
            onSubmitUpdate={() => catalog.submitTemplate("edit")}
          />
        ) : null}

        {tab === "list" ? (
          <ListView
            runs={runs.runs}
            total={runs.total}
            page={runs.page}
            searchQuery={runs.searchQuery}
            templateFilter={runs.templateFilter}
            templateName={runs.templateName}
            loading={runs.listLoading}
            canWrite={canWrite}
            onSearch={(v) => {
              runs.setPage(0);
              runs.setSearchQuery(v);
            }}
            onClearTemplate={runs.clearTemplateFilter}
            onPage={runs.setPage}
            onRefresh={() => runs.loadRuns()}
            onOpen={runs.openDetail}
            onCancel={runs.cancelRun}
            onRetry={runs.openRetry}
          />
        ) : null}

        {tab === "detail" ? (
          <DetailView
            detail={runs.detail}
            loading={runs.detailLoading}
            adminMode={adminMode}
            canWrite={canWrite}
            subview={detailSubview}
            logText={runs.logText}
            logStatus={runs.logStatus}
            logError={runs.logError}
            report={runs.report}
            reportStatus={runs.reportStatus}
            reportError={runs.reportError}
            onRefresh={() => {
              if (!runId) return;
              void runs.loadDetail(runId).then((data) => {
                if (detailSubview === "logs") void runs.loadLog(runId, { sourceUpdatedAt: data?.log_updated_at ?? null });
                if (detailSubview === "viewer") void runs.loadReport(runId, { sourceUpdatedAt: data?.report_updated_at ?? null });
              });
            }}
            onSubview={(next) => go({ tab: "detail", runId, detailSubview: next })}
            onOpenRetryOf={runs.openDetail}
            onOpenFromTemplate={runs.openFromTemplate}
            onCancel={runs.cancelRun}
            onRetry={runs.openRetry}
            onDownload={runs.handleDownload}
          />
        ) : null}

        {tab === "create" && canWrite ? (
          <CreateView
            mode={createMode}
            form={runs.form}
            retryForm={runs.retryForm}
            profiles={runs.profileOptions}
            submitting={runs.submitting}
            formReady={runs.formReady}
            templateId={runs.activeTemplateId || templateId}
            templateName={runs.activeTemplateName}
            templateKind={runs.templateKind}
            declarativeContract={runs.declarativeContract}
            adminMode={adminMode}
            onForm={runs.setForm}
            onRetryForm={runs.setRetryForm}
            onSubmit={runs.submitCreate}
          />
        ) : null}

        {tab === "profiles" && adminMode ? (
          <ProfilesView
            subview={profileSubview}
            profiles={profiles.profileItems}
            total={profiles.profileTotal}
            page={profiles.profilePage}
            loading={profiles.profileLoading}
            profileForm={profiles.profileForm}
            formReady={profiles.profileFormReady}
            submitting={profiles.profileSubmitting}
            onSubview={(next) => {
              if (next === "list") {
                profiles.resetProfileForm();
                go({ tab: "profiles", profileSubview: "list" });
              } else if (next === "create") {
                profiles.resetProfileForm();
                go({ tab: "profiles", profileSubview: "create" });
              } else {
                setProfileSubview(next);
              }
            }}
            onPage={profiles.setProfilePage}
            onRefresh={() => profiles.loadProfileList()}
            onEdit={profiles.openProfileEdit}
            onDelete={profiles.deleteProfile}
            onForm={profiles.setProfileForm}
            onSubmitCreate={() => profiles.submitProfile("create")}
            onSubmitUpdate={() => profiles.submitProfile("edit")}
          />
        ) : null}

        {tab === "settings" ? (
          <SettingsView
            preferences={settings.preferences}
            cleanupForm={settings.cleanupForm}
            submitting={settings.cleanupSubmitting}
            result={settings.cleanupResult}
            importSubmitting={settings.importSubmitting}
            importResult={settings.importResult}
            canWrite={canWrite}
            onAdminMode={settings.setAdminMode}
            onAutoRefresh={settings.setAutoRefresh}
            onAutoRefreshIntervalMs={settings.setAutoRefreshIntervalMs}
            onCleanupForm={settings.setCleanupForm}
            onSubmitCleanup={settings.submitCleanup}
            onImportConfig={settings.importConfig}
            onClearStoredState={settings.clearStoredState}
          />
        ) : null}
      </div>
    </div>
  );
}
