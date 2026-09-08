# PDE extension UI

Shared React UI for **Argo CD** (system extension) and **PDE Operator** (`/ui` when `ui.enabled`).

## Docker

- Operator image: `pde_operator/Dockerfile` (build context = repository root; copies prebuilt `dist/standalone` -> `uv sync`)
- Extension image: `docker build -f argocd_extension/ui/Dockerfile argocd_extension/ui` (build context = `argocd_extension/ui`)

## Routes

| Host     | Prefix              | API                                                |
|----------|---------------------|----------------------------------------------------|
| Argo     | `/pde-operator/...` | `/extensions/<name>` + Argo headers from ConfigMap |
| Operator | `/ui/...`           | `/api/v1` + Bearer token field                     |

Tabs: List, Details, Create, Profiles, Settings.

Argo host config is emitted at pod start as `extension-00-pde-config.js` (`window.__PDE_EXT__`) from
ConfigMap `pde-argo-extension-ui-config` via init-container `envFrom.configMapRef` - see
[argocd_extension/README.md](../README.md) (manual Argo patches + UI ConfigMap).

## React (important)

Shared UI (`app/`, `components/`, ...) must use **global** `React` (`React.useState`, JSX) in source - never `import ... from "react"` except in standalone-only bootstrap/entry files.

- **Argo extension:** webpack `externals` map `react` / `react-dom` / `react/jsx-runtime` to Argo host globals (`window.React`, `window.ReactDOM`, `window.ReactJSXRuntime`). A small banner sets `window.__PDE_JSX_RUNTIME__` with a `React.createElement` fallback for pre–React 19 hosts.
- **Standalone:** `host/bootstrap-standalone-react.ts` imports React and assigns `globalThis.React`; only the standalone entry may import `react` / `react-dom`.
