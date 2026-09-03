# Google ADK → Langfuse Cloud (zero agent code changes)

Minimal demo: a no-code [Google ADK](https://google.github.io/adk-docs/)
agent — defined 100% declaratively in YAML via [ADK Agent Config](https://google.github.io/adk-docs/agents/config/)
(`agents/demo_agent/root_agent.yaml`), using the built-in `google_search`
tool, with no Python at all — runs in the built-in `adk web` UI, and every
conversation is traced to [Langfuse Cloud](https://cloud.langfuse.com)
— full span tree, model calls, tool calls, and token usage.

The key point: **the agent contains zero observability code.** ADK is
OpenTelemetry-instrumented internally and honors the standard `OTEL_*`
environment variables, and Langfuse natively ingests OTLP (HTTP/protobuf).
The entire integration is two environment variables set in `run.sh`:

```
OTEL_EXPORTER_OTLP_TRACES_ENDPOINT = <LANGFUSE_HOST>/api/public/otel/v1/traces
OTEL_EXPORTER_OTLP_TRACES_HEADERS  = Authorization=Basic%20<base64(pk:sk)>,x-langfuse-ingestion-version=4
```

```
adk web (agent + browser UI)
   │  OTLP traces (HTTP/protobuf), configured purely via env vars
   ▼
Langfuse Cloud  /api/public/otel
```

## Prerequisites

- [uv](https://docs.astral.sh/uv/) and the `gcloud` CLI
- A Langfuse Cloud account (free tier is fine)
- A GCP project with billing and the Vertex AI API enabled

## Setup

1. **Langfuse**: create a project at [cloud.langfuse.com](https://cloud.langfuse.com)
   (or the US region), then *Project Settings → API Keys → Create new API keys*.

2. **Google Cloud** (Gemini via Vertex AI):

   ```sh
   gcloud auth login
   gcloud auth application-default login
   gcloud config set project YOUR_PROJECT_ID
   gcloud services enable aiplatform.googleapis.com
   ```

3. **Configure**:

   ```sh
   cp .env.example .env   # then fill in Langfuse keys + GCP project
   ```

## Run

```sh
./run.sh
```

Open http://localhost:8000, pick `demo_agent`, and ask something that needs
current information, e.g. *"What's the weather in Hamburg right now?"*.
The trace appears in Langfuse Cloud under *Tracing → Traces* within a few
seconds.

## Notes

- Because trace export is plain OTLP configured by environment, the same
  pattern applies to ADK agents deployed elsewhere (Cloud Run, Agent Engine):
  set the same two env vars on the deployment — no agent changes.
- For production you may want an OpenTelemetry Collector between the agent
  and Langfuse (buffering/retry, credential isolation, fan-out to Cloud
  Trace and Langfuse simultaneously). It is deliberately omitted here to
  keep the demo minimal.
