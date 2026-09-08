import type { HostConfig } from "./types";

const TOKEN_KEY = "pde_operator_api_token";

export const standaloneHost: HostConfig = {
  apiBase: "/api/v1",
  routePrefix: "/ui",
  credentials: "same-origin",
  tokenField: true,
  authHeaders() {
    const token = localStorage.getItem(TOKEN_KEY) || "";
    return token ? { Authorization: `Bearer ${token}` } : {};
  },
  getToken() {
    return localStorage.getItem(TOKEN_KEY) || "";
  },
  setToken(token: string) {
    const trimmed = token.trim();
    if (trimmed) localStorage.setItem(TOKEN_KEY, trimmed);
    else localStorage.removeItem(TOKEN_KEY);
  },
};
