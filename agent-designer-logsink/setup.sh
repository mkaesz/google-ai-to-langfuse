#!/usr/bin/env bash
# One-time GCP setup: Pub/Sub topic + subscription, and a Cloud Logging
# sink that routes matching log entries into the topic.
set -euo pipefail
cd "$(dirname "$0")"
set -a; source .env; set +a

TOPIC="${PUBSUB_TOPIC:-agent-designer-traces}"
SUB="${PUBSUB_SUBSCRIPTION:-agent-designer-traces-sub}"
SINK="${LOG_SINK:-agent-designer-to-pubsub}"
LOG_NAME="${LOG_NAME:-agent-designer-demo}"
# Matches the synthetic demo log AND any OTel GenAI semconv events.
# For real Agent Designer agents, inspect Logs Explorer and adjust.
FILTER="${LOG_FILTER:-logName=\"projects/${GOOGLE_CLOUD_PROJECT}/logs/${LOG_NAME}\" OR jsonPayload.\"event.name\"=~\"^gen_ai\"}"

gcloud services enable pubsub.googleapis.com logging.googleapis.com --project "$GOOGLE_CLOUD_PROJECT"

gcloud pubsub topics create "$TOPIC" --project "$GOOGLE_CLOUD_PROJECT" 2>/dev/null \
  || echo "topic $TOPIC already exists"
gcloud pubsub subscriptions create "$SUB" --topic "$TOPIC" --ack-deadline 60 \
  --project "$GOOGLE_CLOUD_PROJECT" 2>/dev/null || echo "subscription $SUB already exists"

gcloud logging sinks create "$SINK" \
  "pubsub.googleapis.com/projects/${GOOGLE_CLOUD_PROJECT}/topics/${TOPIC}" \
  --log-filter="$FILTER" --project "$GOOGLE_CLOUD_PROJECT" 2>/dev/null \
  || echo "sink $SINK already exists"

# The sink writes with a Google-managed service account; grant it publish rights.
WRITER=$(gcloud logging sinks describe "$SINK" --project "$GOOGLE_CLOUD_PROJECT" --format='value(writerIdentity)')
gcloud pubsub topics add-iam-policy-binding "$TOPIC" --project "$GOOGLE_CLOUD_PROJECT" \
  --member="$WRITER" --role=roles/pubsub.publisher >/dev/null
echo "granted pubsub.publisher to $WRITER"
echo "setup complete."
