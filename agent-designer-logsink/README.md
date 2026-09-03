# Agent Designer → Cloud Logging → Pub/Sub → Langfuse (prototype)

Fallback pipeline for agents whose runtime offers **no OTLP export
control** — e.g. agents authored in Gemini Enterprise **Agent Designer**.
Those agents emit span *structure* to Cloud Trace (which has no export
sink) and route prompt/response *content* to Cloud Logging or GCS. This
prototype captures the Cloud Logging path and reconstructs
content-level traces in Langfuse:

```
Agent Designer agent (unmodifiable, Google-managed runtime)
   │ prompts/responses as GenAI log events
   ▼
Cloud Logging ──(log router sink)──► Pub/Sub topic
                                        │ pull subscription
                                        ▼
                                  converter.py ──► Langfuse Cloud
```

**Honest limitations** (this is why the ADK env-var variant in
`../adk-otel-direct` is preferred wherever possible):

- **Lossy**: only what log entries carry survives. No span tree — one
  Langfuse generation per log event, grouped by GCP trace id.
- **Unverified against real Agent Designer output**: their exact log
  schema is undocumented. `send_test_log.py` emits OTel GenAI semconv
  shaped events as a stand-in; with a real Gemini Enterprise setup,
  inspect Logs Explorer and adjust the sink `LOG_FILTER` and
  `converter.py:extract()`.
- **Code required**: unlike the env-var variant, this pipeline is a
  running service you operate.

## Why a custom converter — and not an OTel Collector?

It's tempting to replace `converter.py` with a collector, and half of it
would even work: the `googlecloudpubsub` receiver plus the
`googlecloudlogentryencoding` extension can pull from the subscription
and decode Cloud Logging `LogEntry` messages natively — pure config, no
code. But the pipeline dead-ends right after:

1. Decoded log entries enter the collector as OTel **logs**, and the
   collector has no logs→traces conversion. Its connectors go
   traces→metrics and similar; nothing promotes log records to spans.
2. Langfuse's OTLP endpoint accepts **traces only** — OTLP log export
   404s (confirmed as expected behavior by Langfuse).

So something must read a GenAI log event and *construct* a Langfuse
trace/generation from it. That semantic lift is exactly what
`converter.py` does, and it is structurally unavoidable on this path —
not an implementation choice.

This is also the core contrast between the two variants in this repo:
in [`../adk-otel-direct`](../adk-otel-direct/) the data is *born as
traces*, so everything downstream is standard plumbing (env vars,
optionally a collector, zero custom code). Here, the managed runtime
demoted the content to *log events*, and no standard tooling can promote
it back.

## Setup

```sh
cp .env.example .env       # fill in Langfuse keys + GCP project
./setup.sh                 # creates topic, subscription, logging sink
```

## Test end-to-end (no Gemini Enterprise needed)

```sh
uv run python converter.py        # terminal 1: start the forwarder
uv run python send_test_log.py    # terminal 2: emit a synthetic agent log
```

Within ~10–30s the converter prints `forwarded: ...` and the trace
appears in Langfuse (with input/output, session, user, model and the
GCP log metadata).

## Teardown

```sh
./cleanup.sh
```
