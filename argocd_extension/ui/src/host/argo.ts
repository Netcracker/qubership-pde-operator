import type { HostConfig } from "./types";
import { EXT_PATH } from "../lib/constants";

type PdeExtRuntime = {
  application?: string;
  project?: string;
  extensionName?: string;
};

const DEFAULT_APPLICATION = "argocd:pde-operator";
const DEFAULT_PROJECT = "default";
const DEFAULT_EXTENSION_NAME = "pde-argo-extension";

function runtimeConfig(): Required<PdeExtRuntime> {
  const raw = (globalThis as any).__PDE_EXT__ as PdeExtRuntime | undefined;
  return {
    application: raw?.application || DEFAULT_APPLICATION,
    project: raw?.project || DEFAULT_PROJECT,
    extensionName: raw?.extensionName || DEFAULT_EXTENSION_NAME,
  };
}

export const argoHost: HostConfig = {
  get apiBase() {
    return `/extensions/${runtimeConfig().extensionName}`;
  },
  routePrefix: EXT_PATH,
  credentials: "same-origin",
  tokenField: false,
  authHeaders() {
    const cfg = runtimeConfig();
    return {
      "Argocd-Application-Name": cfg.application,
      "Argocd-Project-Name": cfg.project,
    };
  },
  getToken() {
    return "";
  },
  setToken(_token: string) {},
};
