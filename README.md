# Google agents → Langfuse Cloud

Two variants of getting agent traces into [Langfuse Cloud](https://cloud.langfuse.com)
without modifying the agent, matching the two kinds of "no-code" agents
on Google Cloud:

| Variant | For | Fidelity | Status |
|---|---|---|---|
| [`adk-otel-direct/`](adk-otel-direct/) | ADK agents (local `adk web`, Cloud Run, `adk deploy agent_engine`) | Full OTLP span tree, tokens, cost | **Verified end-to-end** (locally + on Vertex AI Agent Engine) |
| [`agent-designer-logsink/`](agent-designer-logsink/) | Gemini Enterprise Agent Designer agents (no env-var control) | Content only, reconstructed from Cloud Logging | Prototype; pipeline verified with synthetic logs |

**Preferred**: `adk-otel-direct` — two `OTEL_*` environment variables,
zero infrastructure. Use the logging-sink pipeline only where the
runtime offers no OTLP control.
