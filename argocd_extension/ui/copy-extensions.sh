#!/bin/sh
# Copy UI bundle into argocd-server emptyDir and emit a separate runtime config script.
# Env comes from ConfigMap pde-argo-extension-ui-config via envFrom.configMapRef.
set -e

js_escape() {
  printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
}

APP="${PDE_ANCHOR_APPLICATION:-argocd:pde-operator}"
PROJ="${PDE_ANCHOR_PROJECT:-default}"
EXT="${PDE_EXTENSION_NAME:-pde-argo-extension}"

mkdir -p /tmp/extensions

printf 'window.__PDE_EXT__={"application":"%s","project":"%s","extensionName":"%s"};\n' \
  "$(js_escape "$APP")" "$(js_escape "$PROJ")" "$(js_escape "$EXT")" \
  > /tmp/extensions/extension-00-pde-argo-extension-config.js

cp -f /extensions/extension-pde-argo-extension.js /tmp/extensions/extension-pde-argo-extension.js
