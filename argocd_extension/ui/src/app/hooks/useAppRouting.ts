import { ensureCanonicalDetailPath, initialRoute, navigate, onRouteChange, parseRoute, pathFor, type RouteState } from "../routing";
import type { CatalogSubview, CreateMode, DetailSubview, ProfileSubview, Tab } from "../../lib/types";

export type RouteSideEffects = {
  onCreateRoute: () => void;
  onCatalogCreateRoute: () => void;
  onCatalogEditRoute: (catalogId: string) => void;
  onProfilesCreateRoute: () => void;
  onProfilesEditRoute: (profileId: string) => void;
  onRetryRoute: (runId: string) => void;
  onSettingsRoute: () => void;
};

export type GoFn = (next: Partial<RouteState> & Pick<RouteState, "tab">, opts?: { replace?: boolean }) => void;

export function useAppRouting(effectsRef: { current: RouteSideEffects }) {
  const initial = React.useMemo(() => initialRoute(), []);
  const [tab, setTab] = React.useState<Tab>(initial.tab);
  const [createMode, setCreateMode] = React.useState<CreateMode>(initial.createMode);
  const [runId, setRunId] = React.useState(initial.runId);
  const [templateId, setTemplateId] = React.useState(initial.templateId);
  const [profileSubview, setProfileSubview] = React.useState<ProfileSubview>(initial.profileSubview);
  const [catalogSubview, setCatalogSubview] = React.useState<CatalogSubview>(initial.catalogSubview);
  const [detailSubview, setDetailSubview] = React.useState<DetailSubview>(initial.detailSubview);

  const go = React.useCallback<GoFn>((next, { replace = false } = {}) => {
    const route: RouteState = {
      tab: next.tab,
      createMode: next.createMode ?? "create",
      runId: next.runId ?? "",
      templateId: next.templateId ?? "",
      profileSubview: next.profileSubview ?? "list",
      profileId: next.profileId ?? "",
      catalogSubview: next.catalogSubview ?? "list",
      catalogId: next.catalogId ?? "",
      detailSubview: next.detailSubview ?? "info",
    };
    navigate(pathFor(route), { replace });
    setTab(route.tab);
    setCreateMode(route.createMode);
    setRunId(route.runId);
    setTemplateId(route.templateId);
    setProfileSubview(route.profileSubview);
    setCatalogSubview(route.catalogSubview);
    setDetailSubview(route.detailSubview);
  }, []);

  const applyBrowserRoute = React.useCallback(() => {
    ensureCanonicalDetailPath();
    const route = parseRoute();
    setTab(route.tab);
    setCreateMode(route.createMode);
    setRunId(route.runId);
    setTemplateId(route.templateId);
    setProfileSubview(route.profileSubview);
    setCatalogSubview(route.catalogSubview);
    setDetailSubview(route.detailSubview);
    const effects = effectsRef.current;
    if (route.tab === "create" && route.createMode === "create" && !route.templateId) {
      effects.onCreateRoute();
    }
    if (route.tab === "catalog" && route.catalogSubview === "create") effects.onCatalogCreateRoute();
    if (route.tab === "catalog" && route.catalogSubview === "edit" && route.catalogId) {
      effects.onCatalogEditRoute(route.catalogId);
    }
    if (route.tab === "profiles" && route.profileSubview === "create") effects.onProfilesCreateRoute();
    if (route.tab === "profiles" && route.profileSubview === "edit" && route.profileId) {
      effects.onProfilesEditRoute(route.profileId);
    }
    if (route.tab === "create" && route.createMode === "retry" && route.runId) effects.onRetryRoute(route.runId);
    if (route.tab === "settings") effects.onSettingsRoute();
  }, [effectsRef]);

  React.useEffect(() => {
    const effects = effectsRef.current;
    if (initial.tab === "create" && initial.createMode === "create" && !initial.templateId) {
      effects.onCreateRoute();
    }
    if (initial.tab === "catalog" && initial.catalogSubview === "create") {
      effects.onCatalogCreateRoute();
    }
    if (initial.tab === "catalog" && initial.catalogSubview === "edit" && initial.catalogId) {
      effects.onCatalogEditRoute(initial.catalogId);
    }
    if (initial.tab === "profiles" && initial.profileSubview === "create") {
      effects.onProfilesCreateRoute();
    }
    if (initial.tab === "profiles" && initial.profileSubview === "edit" && initial.profileId) {
      effects.onProfilesEditRoute(initial.profileId);
    }
    if (initial.tab === "create" && initial.createMode === "retry" && initial.runId) {
      effects.onRetryRoute(initial.runId);
    }
    if (initial.tab === "settings") effects.onSettingsRoute();
    return onRouteChange(applyBrowserRoute);
  }, [applyBrowserRoute, effectsRef, initial]);

  return {
    initial,
    tab,
    createMode,
    runId,
    templateId,
    profileSubview,
    catalogSubview,
    detailSubview,
    setProfileSubview,
    setCatalogSubview,
    go,
  };
}
