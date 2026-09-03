#!/usr/bin/env bash
# Starts the ADK web UI with trace export to Langfuse Cloud.
# The agent code contains zero tracing logic — everything below is
# standard OpenTelemetry configuration read by `adk web` at startup.
set -euo pipefail
cd "$(dirname "$0")"

if [[ ! -f .env ]]; then
  echo "Missing .env — copy .env.example to .env and fill in your keys." >&2
  exit 1
fi
set -a
source .env
set +a

# Langfuse OTLP endpoint: Basic auth = base64("publicKey:secretKey").
# Header values in OTEL_* env vars must be URL-encoded, hence %20 for the space.
LANGFUSE_AUTH="$(printf '%s' "${LANGFUSE_PUBLIC_KEY}:${LANGFUSE_SECRET_KEY}" | base64)"
export OTEL_SERVICE_NAME="${OTEL_SERVICE_NAME:-adk-demo-agent}"
export OTEL_EXPORTER_OTLP_TRACES_ENDPOINT="${LANGFUSE_HOST}/api/public/otel/v1/traces"
export OTEL_EXPORTER_OTLP_TRACES_HEADERS="Authorization=Basic%20${LANGFUSE_AUTH},x-langfuse-ingestion-version=4"

# Gemini via Vertex AI (uses Application Default Credentials).
export GOOGLE_GENAI_USE_VERTEXAI=TRUE

exec uv run adk web agents
