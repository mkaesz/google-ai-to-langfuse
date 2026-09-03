#!/usr/bin/env bash
# Removes the GCP resources created by setup.sh.
set -euo pipefail
cd "$(dirname "$0")"
set -a; source .env; set +a

gcloud logging sinks delete "${LOG_SINK:-agent-designer-to-pubsub}" --project "$GOOGLE_CLOUD_PROJECT" --quiet || true
gcloud pubsub subscriptions delete "${PUBSUB_SUBSCRIPTION:-agent-designer-traces-sub}" --project "$GOOGLE_CLOUD_PROJECT" --quiet || true
gcloud pubsub topics delete "${PUBSUB_TOPIC:-agent-designer-traces}" --project "$GOOGLE_CLOUD_PROJECT" --quiet || true
echo "cleanup complete."
