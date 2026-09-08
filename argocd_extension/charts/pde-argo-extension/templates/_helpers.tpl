{{- define "pde-argo-extension.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "pde-argo-extension.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{- define "pde-argo-extension.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "pde-argo-extension.labels" -}}
helm.sh/chart: {{ include "pde-argo-extension.chart" . }}
app.kubernetes.io/name: {{ include "pde-argo-extension.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: pde-argo-extension
{{- end }}

{{- define "pde-argo-extension.selectorLabels" -}}
app.kubernetes.io/name: {{ include "pde-argo-extension.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/component: backend
{{- end }}

{{- define "pde-argo-extension.backendName" -}}
{{- printf "%s-backend" (include "pde-argo-extension.fullname" .) }}
{{- end }}

{{- define "pde-argo-extension.argocdNamespace" -}}
{{- .Values.argocd.namespace | default "argocd" }}
{{- end }}

{{- define "pde-argo-extension.extensionName" -}}
{{- .Values.extension.name | default "pde-argo-extension" }}
{{- end }}

{{- define "pde-argo-extension.uiConfigMapName" -}}
{{- printf "%s-ui-config" (include "pde-argo-extension.fullname" .) }}
{{- end }}

{{- define "pde-argo-extension.backendRbacConfigMapName" -}}
{{- printf "%s-backend-rbac" (include "pde-argo-extension.fullname" .) }}
{{- end }}

{{- define "pde-argo-extension.backendServiceUrl" -}}
{{- printf "http://%s.%s.svc:%v" (include "pde-argo-extension.backendName" .) (include "pde-argo-extension.argocdNamespace" .) (.Values.extension.port | int) }}
{{- end }}
