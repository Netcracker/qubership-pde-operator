import { getHost } from "../host/registry";

function apiUrl(path: string) {
  const { apiBase } = getHost();
  return `${apiBase}${path.startsWith("/") ? path : `/${path}`}`;
}

function requestHeaders(extra?: HeadersInit): Record<string, string> {
  const host = getHost();
  return {
    "Content-Type": "application/json",
    ...host.authHeaders(),
    ...(extra as Record<string, string> | undefined),
  };
}

export async function apiJson(path: string, init?: RequestInit) {
  const host = getHost();
  const response = await fetch(apiUrl(path), {
    ...init,
    headers: { ...requestHeaders(), ...(init?.headers as Record<string, string> | undefined) },
    credentials: host.credentials,
  });
  const text = await response.text();
  const body = text ? (() => { try { return JSON.parse(text); } catch { return text; } })() : null;
  if (!response.ok) {
    const detail =
      body && typeof body === "object" && "detail" in body
        ? (body as any).detail
        : typeof body === "string" && body.trim()
          ? body.trim()
          : response.statusText;
    const err: any = new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    err.status = response.status;
    throw err;
  }
  return body;
}

export async function apiText(path: string) {
  const host = getHost();
  const response = await fetch(apiUrl(path), {
    headers: host.authHeaders(),
    credentials: host.credentials,
  });
  if (!response.ok) {
    if (response.status === 404) {
      const err: any = new Error("not_found");
      err.status = 404;
      throw err;
    }
    const err: any = new Error(`HTTP ${response.status}`);
    err.status = response.status;
    throw err;
  }
  return await response.text();
}

export async function downloadArtifact(runId: string, kind: string) {
  const host = getHost();
  const response = await fetch(apiUrl(`/runs/${runId}/artifacts/${kind}`), {
    headers: host.authHeaders(),
    credentials: host.credentials,
  });
  if (!response.ok) {
    const detail = await response.text();
    const err: any = new Error(detail || `Download failed (${response.status})`);
    err.status = response.status;
    throw err;
  }
  const blob = await response.blob();
  const disposition = response.headers.get("Content-Disposition") || "";
  const match = /filename="([^"]+)"/.exec(disposition);
  const filename = match ? match[1] : `${kind}.bin`;
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}
