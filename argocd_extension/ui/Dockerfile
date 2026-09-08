# Package the prebuilt Argo CD extension JS bundle for the argocd-server init
# container. The React bundle is built once in CI (build-ui job) and shared with
# the operator image; this stage only copies the extension bundle.
#
# Build context: argocd_extension/ui
#   docker build -f argocd_extension/ui/Dockerfile -t pde-argo-extension-ui:<tag> argocd_extension/ui

FROM busybox:1.38
RUN mkdir -p /extensions
COPY dist/extension-pde-argo-extension.js /extensions/
COPY copy-extensions.sh /copy-extensions.sh
RUN chmod +x /copy-extensions.sh
ENTRYPOINT ["/copy-extensions.sh"]
