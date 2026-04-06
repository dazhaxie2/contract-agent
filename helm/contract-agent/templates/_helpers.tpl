{{/*
公共模板助手函数
*/}}

{{- define "contract-agent.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "contract-agent.fullname" -}}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- printf "%s" $name | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "contract-agent.labels" -}}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: contract-agent
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}

{{- define "contract-agent.selectorLabels" -}}
app.kubernetes.io/name: {{ include "contract-agent.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
