import type { HostConfig } from "./types";

let host: HostConfig | null = null;

export function configureHost(config: HostConfig) {
  host = config;
}

export function getHost(): HostConfig {
  if (!host) throw new Error("UI host is not configured");
  return host;
}
