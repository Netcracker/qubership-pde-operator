import { getHost } from "../host/registry";

type ApiError = Error & { status?: number };

function isArgoExtension(): boolean {
  try {
    return !getHost().tokenField;
  } catch {
    return true;
  }
}

function isNetworkError(e: ApiError): boolean {
  if (e.status) return false;
  const msg = (e.message || "").toLowerCase();
  return (
    e instanceof TypeError ||
    msg.includes("failed to fetch") ||
    msg.includes("networkerror") ||
    msg.includes("load failed") ||
    msg.includes("network request failed")
  );
}

function parseHttpStatus(e: ApiError): number | undefined {
  if (typeof e.status === "number") return e.status;
  const match = /^HTTP (\d+)$/.exec(e.message || "");
  return match ? Number(match[1]) : undefined;
}

function argoExtensionBackendMessage(): string {
  return [
    "Cannot connect to the PDE Operator extension backend.",
    "Ensure pde-argo-extension is installed in this Argo CD instance and argocd-server was restarted after setup.",
    "This UI also expects pde-operator to be installed and managed by this Argo CD instance.",
  ].join("\n\n");
}

function argoOperatorUnreachableMessage(): string {
  return [
    "The extension backend cannot reach pde-operator.",
    "pde-operator should be installed and managed by this Argo CD instance — verify the Application is synced and healthy.",
  ].join("\n\n");
}

function argoPermissionMessage(status: number): string {
  return [
    `Permission denied (HTTP ${status}).`,
    "Your Argo CD admin must grant extension invoke access and applications/get on the pde-operator Application managed by this instance.",
  ].join("\n\n");
}

function argoWriteForbiddenMessage(): string {
  return [
    "You do not have write access to PDE Operator.",
    "Your Argo CD admin must add your username or IdP group to the pde-argo-extension-backend-rbac ConfigMap (writeUsers / writeGroups).",
  ].join("\n\n");
}

function standaloneConnectionMessage(): string {
  return "Cannot reach the PDE Operator API. Check that the API server is running and the browser can connect to it.";
}

function standalonePermissionMessage(status: number): string {
  return `Authentication failed (HTTP ${status}). Set a valid API token in the field above.`;
}

export function friendlyApiErrMsg(e: unknown): string | null {
  if (!(e instanceof Error)) return null;
  const err = e as ApiError;
  const status = parseHttpStatus(err);
  const msg = (err.message || "").trim();
  const argo = isArgoExtension();

  if (isNetworkError(err)) {
    return argo ? argoExtensionBackendMessage() : standaloneConnectionMessage();
  }

  if (status === 401 || status === 403) {
    if (argo && msg === "write_forbidden") return argoWriteForbiddenMessage();
    return argo ? argoPermissionMessage(status) : standalonePermissionMessage(status);
  }

  if (status === 502 || msg === "operator request failed" || msg === "operator_unreachable") {
    return argo ? argoOperatorUnreachableMessage() : standaloneConnectionMessage();
  }

  if (status === 503 || status === 504) {
    return argo
      ? [
          `PDE Operator is temporarily unavailable (HTTP ${status}).`,
          "pde-operator should be installed and managed by this Argo CD instance — check that it is running and healthy.",
        ].join("\n\n")
      : standaloneConnectionMessage();
  }

  return null;
}

export function errMsg(e: unknown) {
  return friendlyApiErrMsg(e) ?? (e instanceof Error ? e.message : String(e));
}
