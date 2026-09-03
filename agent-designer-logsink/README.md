# Agent Designer → Cloud Logging → Pub/Sub → Langfuse (prototype)

Fallback pipeline for agents whose runtime offers **no OTLP export
control** - e.g. agents authored in Gemini Enterprise **Agent Designer**.
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

## Why a custom converter - and not an OTel Collector?

It's tempting to replace `converter.py` with a collector, and half of it
would even work: the `googlecloudpubsub` receiver plus the
`googlecloudlogentryencoding` extension can pull from the subscription
and decode Cloud Logging `LogEntry` messages natively - pure config, no
code. But the pipeline dead-ends right after:

1. Decoded log entries enter the collector as OTel **logs**, and the
   collector has no logs→traces conversion. Its connectors go
   traces→metrics and similar; nothing promotes log records to spans.
2. Langfuse's OTLP endpoint accepts **traces only** - OTLP log export
   404s (confirmed as expected behavior by Langfuse).

So something must read a GenAI log event and *construct* a Langfuse
trace/generation from it. That semantic lift is exactly what
`converter.py` does, and it is structurally unavoidable on this path -
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

## Connecting a real Agent Designer agent

Nothing on the agent side ever targets Pub/Sub - the agent only needs to
get its content into Cloud Logging; the log-router sink created by
`setup.sh` does the Pub/Sub delivery. To wire up a real Gemini
Enterprise agent:

1. **Enable the observability toggles** ([admin guide](https://docs.cloud.google.com/gemini/enterprise/docs/manage-observability-settings)).
   Where they live depends on agent type - Core Assistant: app-level
   toggle; Agent Designer employee-made agents and Deep Research agents:
   agent-level toggle (Agent Platform → Agent Registry → agent →
   Configuration tab). Both switches are needed:
   - *Enable instrumentation of OpenTelemetry traces and logs* - spans,
     span logs, metrics (structure → Cloud Trace).
   - *Enable logging of prompt inputs and response outputs* - full
     prompt/response content into Cloud Logging (requires the first
     toggle). ⚠️ Google's own caution applies: this logs potentially
     sensitive data/PII - clear it with your data-protection process
     first.

2. **Enable the APIs** in the GCP project backing the Gemini Enterprise
   app (that's where the logs land, so the sink must live there too):
   Cloud Trace API, Cloud Logging API, Telemetry API.

3. **Discover the real log shape** - the step the synthetic test stands
   in for. Run one conversation, find the content-carrying entries in
   Logs Explorer, note their `logName` and payload structure, then point
   the sink at them:

   ```sh
   gcloud logging sinks update agent-designer-to-pubsub \
     --log-filter='logName="projects/YOUR_PROJECT/logs/THE_REAL_LOG_NAME"'
   ```

   If the payload differs from the OTel GenAI semconv shape assumed
   here, adjust `converter.py:extract()` - it is written defensively for
   exactly this.

4. **Done** - matching entries flow log router → Pub/Sub → converter →
   Langfuse automatically.

Known unknown until step 3 runs against a real tenant: whether your
org's configuration routes prompt/response content to Cloud Logging or
to Cloud Storage (recommended by Google for large/multimodal payloads).
If it's GCS, this pipeline needs a GCS-notification trigger instead of a
log sink.

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
