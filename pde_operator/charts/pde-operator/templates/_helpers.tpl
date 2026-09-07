{{/*
Expand the name of the chart.
*/}}
{{- define "pde-operator.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "pde-operator.fullname" -}}
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

{{- define "pde-operator.labels" -}}
helm.sh/chart: {{ include "pde-operator.chart" . }}
{{ include "pde-operator.selectorLabels" . }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: pde-operator
{{- end }}

{{- define "pde-operator.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "pde-operator.selectorLabels" -}}
app.kubernetes.io/name: {{ include "pde-operator.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{- define "pde-operator.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "pde-operator.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{- define "pde-operator.k8sNamespace" -}}
{{- if .Values.operator.k8sNamespace }}
{{- .Values.operator.k8sNamespace }}
{{- else }}
{{- .Release.Namespace }}
{{- end }}
{{- end }}

{{- define "pde-operator.serviceName" -}}
{{- include "pde-operator.fullname" . }}
{{- end }}

{{- define "pde-operator.operatorBaseUrl" -}}
{{- if .Values.operator.operatorBaseUrl }}
{{- .Values.operator.operatorBaseUrl }}
{{- else }}
{{- printf "http://%s.%s.svc:%v" (include "pde-operator.serviceName" .) .Release.Namespace (.Values.service.port | int) }}
{{- end }}
{{- end }}

{{- define "pde-operator.executionUrlBase" -}}
{{- if .Values.operator.executionUrlBase }}
{{- .Values.operator.executionUrlBase }}
{{- else }}
{{- include "pde-operator.operatorBaseUrl" . }}
{{- end }}
{{- end }}

{{- define "pde-operator.postgresHost" -}}
{{- if .Values.postgres.enabled }}
{{- printf "%s-postgres" (include "pde-operator.fullname" .) }}
{{- else }}
{{- required "postgres.external.host is required when postgres.enabled=false" .Values.postgres.external.host }}
{{- end }}
{{- end }}

{{- define "pde-operator.postgresPort" -}}
{{- if .Values.postgres.enabled }}
{{- .Values.postgres.port | int }}
{{- else }}
{{- .Values.postgres.external.port | int }}
{{- end }}
{{- end }}

{{- define "pde-operator.postgresUser" -}}
{{- if .Values.postgres.enabled }}
{{- .Values.postgres.auth.username }}
{{- else }}
{{- .Values.postgres.external.username }}
{{- end }}
{{- end }}

{{- define "pde-operator.postgresPassword" -}}
{{- if .Values.postgres.enabled }}
{{- .Values.postgres.auth.password }}
{{- else }}
{{- required "postgres.external.password is required when postgres.enabled=false" .Values.postgres.external.password }}
{{- end }}
{{- end }}

{{- define "pde-operator.postgresDatabase" -}}
{{- if .Values.postgres.enabled }}
{{- .Values.postgres.auth.database }}
{{- else }}
{{- required "postgres.external.database is required when postgres.enabled=false" .Values.postgres.external.database }}
{{- end }}
{{- end }}

{{- define "pde-operator.databaseUrl" -}}
{{- printf "postgresql+asyncpg://%s:%s@%s:%v/%s" (include "pde-operator.postgresUser" .) (include "pde-operator.postgresPassword" .) (include "pde-operator.postgresHost" .) (include "pde-operator.postgresPort" .) (include "pde-operator.postgresDatabase" .) }}
{{- end }}

{{- define "pde-operator.minioEndpoint" -}}
{{- if .Values.minio.enabled }}
{{- printf "http://%s-minio:%v" (include "pde-operator.fullname" .) (.Values.minio.apiPort | int) }}
{{- else }}
{{- required "minio.external.endpoint is required when minio.enabled=false" .Values.minio.external.endpoint }}
{{- end }}
{{- end }}

{{- define "pde-operator.minioAccessKey" -}}
{{- if .Values.minio.enabled }}
{{- .Values.minio.auth.rootUser }}
{{- else }}
{{- required "minio.external.accessKey is required when minio.enabled=false" .Values.minio.external.accessKey }}
{{- end }}
{{- end }}

{{- define "pde-operator.minioSecretKey" -}}
{{- if .Values.minio.enabled }}
{{- .Values.minio.auth.rootPassword }}
{{- else }}
{{- required "minio.external.secretKey is required when minio.enabled=false" .Values.minio.external.secretKey }}
{{- end }}
{{- end }}

{{- define "pde-operator.minioBucket" -}}
{{- if .Values.minio.enabled }}
{{- .Values.minio.bucket }}
{{- else }}
{{- default "pde-artifacts" .Values.minio.external.bucket }}
{{- end }}
{{- end }}

{{- define "pde-operator.externalSecretsName" -}}
{{- if .Values.externalSecrets.name }}
{{- .Values.externalSecrets.name }}
{{- else }}
{{- printf "%s-external-secrets" (include "pde-operator.fullname" .) }}
{{- end }}
{{- end }}

{{- define "pde-operator.jobRuntimeConfigMapName" -}}
{{- if .Values.jobRuntime.name }}
{{- .Values.jobRuntime.name }}
{{- else }}
{{- printf "%s-job-runtime" (include "pde-operator.fullname" .) }}
{{- end }}
{{- end }}
