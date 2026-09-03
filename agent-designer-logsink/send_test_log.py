"""Writes a synthetic 'Agent Designer-shaped' GenAI log entry to Cloud Logging.

Gemini Enterprise Agent Designer routes prompts/responses to Cloud
Logging (or GCS) as OTel GenAI semconv events rather than span
attributes. This script emits one such event so the whole pipeline
(logging sink → Pub/Sub → converter → Langfuse) can be tested without a
Gemini Enterprise subscription. The payload shape follows the OTel
GenAI semantic conventions; the real Agent Designer schema is
undocumented, so treat field mapping in converter.py as adjustable.
"""

import os
import uuid

from dotenv import load_dotenv
from google.cloud import logging as cloud_logging

load_dotenv()

PROJECT = os.environ["GOOGLE_CLOUD_PROJECT"]
LOG_NAME = os.environ.get("LOG_NAME", "agent-designer-demo")

client = cloud_logging.Client(project=PROJECT)
logger = client.logger(LOG_NAME)

trace_hex = uuid.uuid4().hex
payload = {
    "event.name": "gen_ai.client.inference.operation.details",
    "attributes": {
        "gen_ai.operation.name": "chat",
        "gen_ai.request.model": "gemini-2.5-flash",
        "gen_ai.input.messages": [
            {
                "role": "user",
                "parts": [
                    {"type": "text", "content": "What's the weather in Hamburg right now?"}
                ],
            }
        ],
        "gen_ai.output.messages": [
            {
                "role": "assistant",
                "parts": [
                    {"type": "text", "content": "Light rain and 16°C in Hamburg right now."}
                ],
            }
        ],
        "gen_ai.usage.input_tokens": 107,
        "gen_ai.usage.output_tokens": 178,
        "gen_ai.conversation.id": "demo-session-1",
        "user.id": "demo-user",
    },
}

logger.log_struct(
    payload,
    severity="INFO",
    trace=f"projects/{PROJECT}/traces/{trace_hex}",
    span_id=uuid.uuid4().hex[:16],
)
print(f"wrote log entry to '{LOG_NAME}' with trace id {trace_hex}")
