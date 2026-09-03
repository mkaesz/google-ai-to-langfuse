"""Prototype converter: Cloud Logging → Pub/Sub → Langfuse.

Drains a Pub/Sub subscription fed by a Cloud Logging sink and forwards
GenAI conversation content to Langfuse Cloud. This is the fallback path
for agents whose runtime offers no OTLP export control (e.g. Gemini
Enterprise Agent Designer agents): span *structure* stays in Cloud
Trace, but prompt/response *content* routed to Cloud Logging can be
reconstructed as Langfuse traces.

Lossy by design: only what the log entries carry survives. Entries
sharing a GCP trace id are grouped into one Langfuse trace.
"""

import json
import os
import signal
import sys

from dotenv import load_dotenv
from google.cloud import pubsub_v1
from langfuse import Langfuse

load_dotenv()

PROJECT = os.environ["GOOGLE_CLOUD_PROJECT"]
SUBSCRIPTION = os.environ.get("PUBSUB_SUBSCRIPTION", "agent-designer-traces-sub")

langfuse = Langfuse()  # reads LANGFUSE_PUBLIC_KEY / SECRET_KEY / HOST from env


def _texts(messages) -> str:
    """Flattens gen_ai.*.messages (role/parts structure) to readable text."""
    if not isinstance(messages, list):
        return str(messages)
    out = []
    for m in messages:
        role = m.get("role", "?") if isinstance(m, dict) else "?"
        parts = m.get("parts", []) if isinstance(m, dict) else []
        for p in parts:
            if isinstance(p, dict) and "content" in p:
                out.append(f"{role}: {p['content']}")
    return "\n".join(out) or json.dumps(messages)


def extract(entry: dict) -> dict | None:
    """Pulls conversation content out of a LogEntry, defensively.

    Handles OTel GenAI semconv event payloads (gen_ai.* attributes) and
    falls back to generic input/output keys or textPayload.
    """
    payload = entry.get("jsonPayload") or {}
    attrs = payload.get("attributes") or payload
    inp = attrs.get("gen_ai.input.messages") or attrs.get("input")
    outp = attrs.get("gen_ai.output.messages") or attrs.get("output")
    if inp is None and outp is None:
        text = entry.get("textPayload")
        if not text:
            return None
        inp, outp = text, None

    gcp_trace = (entry.get("trace") or "").rsplit("/", 1)[-1]
    return {
        "trace_seed": gcp_trace or entry.get("insertId", "unknown"),
        "name": payload.get("event.name")
        or payload.get("event_name")
        or entry.get("logName", "log-entry").rsplit("/", 1)[-1],
        "input": _texts(inp) if inp is not None else None,
        "output": _texts(outp) if outp is not None else None,
        "model": attrs.get("gen_ai.request.model"),
        "usage": {
            "input": attrs.get("gen_ai.usage.input_tokens"),
            "output": attrs.get("gen_ai.usage.output_tokens"),
        },
        "session_id": attrs.get("gen_ai.conversation.id"),
        "user_id": attrs.get("user.id"),
        "metadata": {
            "gcp.log_name": entry.get("logName"),
            "gcp.trace": entry.get("trace"),
            "gcp.span_id": entry.get("spanId"),
            "gcp.timestamp": entry.get("timestamp"),
            "gcp.insert_id": entry.get("insertId"),
        },
    }


def handle(message: pubsub_v1.subscriber.message.Message) -> None:
    try:
        entry = json.loads(message.data.decode("utf-8"))
        item = extract(entry)
        if item is None:
            print(f"skipped (no content): {entry.get('insertId')}", flush=True)
            message.ack()
            return

        trace_id = langfuse.create_trace_id(seed=item["trace_seed"])
        metadata = dict(item["metadata"])
        if item["session_id"]:
            metadata["session.id"] = item["session_id"]
        if item["user_id"]:
            metadata["user.id"] = item["user_id"]
        obs = langfuse.start_observation(
            trace_context={"trace_id": trace_id},
            name=item["name"],
            as_type="generation",
            input=item["input"],
            output=item["output"],
            model=item["model"],
            metadata=metadata,
        )
        obs.set_trace_io(input=item["input"], output=item["output"])
        obs.end()
        langfuse.flush()
        print(f"forwarded: {item['name']} -> langfuse trace {trace_id}", flush=True)
        message.ack()
    except Exception as e:  # noqa: BLE001 - prototype: log and drop poison pills
        print(f"error, acking to avoid redelivery loop: {e}", file=sys.stderr)
        message.ack()


def main() -> None:
    subscriber = pubsub_v1.SubscriberClient()
    sub_path = subscriber.subscription_path(PROJECT, SUBSCRIPTION)
    future = subscriber.subscribe(sub_path, callback=handle)
    print(f"listening on {sub_path} -> {os.environ.get('LANGFUSE_HOST', 'langfuse cloud')}")

    signal.signal(signal.SIGTERM, lambda *_: future.cancel())
    try:
        future.result()
    except KeyboardInterrupt:
        future.cancel()
        future.result()
    finally:
        langfuse.shutdown()


if __name__ == "__main__":
    main()
