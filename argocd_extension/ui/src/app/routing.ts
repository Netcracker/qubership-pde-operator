import { getHost } from "../host/registry";
import type { CatalogSubview, CreateMode, DetailSubview, ProfileSubview, Tab } from "../lib/types";

export type RouteState = {
  tab: Tab;
  createMode: CreateMode;
  runId: string;
  templateId: string;
  profileSubview: ProfileSubview;
  profileId: string;
  catalogSubview: CatalogSubview;
  catalogId: string;
  detailSubview: DetailSubview;
};

const DETAIL_SUBVIEWS = new Set<DetailSubview>(["info", "logs", "viewer"]);

function routePrefix(): string {
  return getHost().routePrefix;
}

export function appPathname(): string {
  const base = document.querySelector("head > base")?.getAttribute("href")?.replace(/\/$/, "") || "";
  let path = window.location.pathname;
  if (base && path.startsWith(base)) {
    path = path.slice(base.length) || "/";
  }
  return path.replace(/\/$/, "") || "/";
}

function emptyRoute(): RouteState {
  return {
    tab: "catalog",
    createMode: "create",
    runId: "",
    templateId: "",
    profileSubview: "list",
    profileId: "",
    catalogSubview: "list",
    catalogId: "",
    detailSubview: "info",
  };
}

export function parseRoute(pathname = appPathname()): RouteState {
  const prefix = routePrefix();
  const rest = pathname === prefix || pathname.startsWith(prefix + "/") ? pathname.slice(prefix.length) : "";
  const parts = rest.split("/").filter(Boolean);
  const empty = emptyRoute();

  if (parts[0] === "catalog") {
    if (parts[1] === "new") {
      return { ...empty, tab: "catalog", catalogSubview: "create" };
    }
    if (parts[1] && parts[2] === "edit") {
      return { ...empty, tab: "catalog", catalogSubview: "edit", catalogId: parts[1] };
    }
    return { ...empty, tab: "catalog", catalogSubview: "list" };
  }
  if (parts[0] === "runs" && parts[1] && parts[1] !== "template") {
    const sub = parts[2];
    const detailSubview: DetailSubview = DETAIL_SUBVIEWS.has(sub as DetailSubview) ? (sub as DetailSubview) : "info";
    return { ...empty, tab: "detail", runId: parts[1], detailSubview };
  }
  if (parts[0] === "create" && parts[1] === "from" && parts[2]) {
    return { ...empty, tab: "create", createMode: "create", templateId: parts[2] };
  }
  if (parts[0] === "create") {
    return { ...empty, tab: "create", createMode: "create" };
  }
  if (parts[0] === "retry" && parts[1]) {
    return { ...empty, tab: "create", createMode: "retry", runId: parts[1] };
  }
  if (parts[0] === "profiles") {
    if (parts[1] === "new") {
      return { ...empty, tab: "profiles", profileSubview: "create" };
    }
    if (parts[1] && parts[2] === "edit") {
      return { ...empty, tab: "profiles", profileSubview: "edit", profileId: parts[1] };
    }
    return { ...empty, tab: "profiles", profileSubview: "list" };
  }
  if (parts[0] === "settings") {
    return { ...empty, tab: "settings" };
  }
  if (parts[0] === "runs") {
    if (parts[1] === "template" && parts[2]) {
      return { ...empty, tab: "list", templateId: parts[2] };
    }
    return { ...empty, tab: "list" };
  }
  return empty;
}

export function pathFor(state: Partial<RouteState> & Pick<RouteState, "tab">): string {
  const prefix = routePrefix();
  const createMode = state.createMode || "create";
  const runId = state.runId || "";
  const templateId = state.templateId || "";
  const profileSubview = state.profileSubview || "list";
  const profileId = state.profileId || "";
  const catalogSubview = state.catalogSubview || "list";
  const catalogId = state.catalogId || "";
  const detailSubview = state.detailSubview || "info";

  switch (state.tab) {
    case "catalog":
      if (catalogSubview === "create") return `${prefix}/catalog/new`;
      if (catalogSubview === "edit" && catalogId) return `${prefix}/catalog/${catalogId}/edit`;
      return `${prefix}/catalog`;
    case "detail":
      return runId ? `${prefix}/runs/${runId}/${detailSubview}` : `${prefix}/runs`;
    case "create":
      if (createMode === "retry" && runId) return `${prefix}/retry/${runId}`;
      if (templateId) return `${prefix}/create/from/${templateId}`;
      return `${prefix}/create`;
    case "profiles":
      if (profileSubview === "create") return `${prefix}/profiles/new`;
      if (profileSubview === "edit" && profileId) return `${prefix}/profiles/${profileId}/edit`;
      return `${prefix}/profiles`;
    case "settings":
      return `${prefix}/settings`;
    case "list":
    default:
      if (state.templateId) return `${prefix}/runs/template/${state.templateId}`;
      return `${prefix}/runs`;
  }
}

function browserPath(appPath: string): string {
  const base = document.querySelector("head > base")?.getAttribute("href")?.replace(/\/$/, "") || "";
  return `${base}${appPath}` || appPath;
}

export function navigate(appPath: string, { replace = false } = {}) {
  const url = browserPath(appPath) + window.location.search + window.location.hash;
  if (replace) window.history.replaceState(null, "", url);
  else window.history.pushState(null, "", url);
}

export function ensureCanonicalListPath() {
  const prefix = routePrefix();
  const path = appPathname();
  if (path === prefix || path === `${prefix}/`) {
    navigate(`${prefix}/catalog`, { replace: true });
  }
}

/** `/runs/{id}` -> `/runs/{id}/info` so shared links always include the detail sub-tab. */
export function ensureCanonicalDetailPath() {
  const prefix = routePrefix();
  const path = appPathname();
  const rest = path === prefix || path.startsWith(prefix + "/") ? path.slice(prefix.length) : "";
  const parts = rest.split("/").filter(Boolean);
  if (parts[0] === "runs" && parts[1] && !parts[2]) {
    navigate(`${prefix}/runs/${parts[1]}/info`, { replace: true });
  }
}

export function onRouteChange(handler: () => void) {
  window.addEventListener("popstate", handler);
  return () => window.removeEventListener("popstate", handler);
}

export function initialRoute(): RouteState {
  ensureCanonicalListPath();
  ensureCanonicalDetailPath();
  return parseRoute();
}
