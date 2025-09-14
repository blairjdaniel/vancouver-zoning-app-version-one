#!/usr/bin/env bash
# Upload a file to Google Cloud Storage and print a public signed URL (optional).
# Usage: scripts/upload_to_gcs.sh /path/to/file gs://your-bucket-name [--public]

set -euo pipefail
FILE=${1:-}
BUCKET=${2:-}
PUBLIC_FLAG=${3:-}

if [ -z "$FILE" ] || [ -z "$BUCKET" ]; then
  echo "Usage: $0 /path/to/file gs://your-bucket-name [--public]"
  exit 1
fi

if ! command -v gsutil >/dev/null 2>&1; then
  echo "gsutil not found. Install Google Cloud SDK (gcloud) and initialize auth: https://cloud.google.com/sdk/docs/install"
  exit 1
fi

echo "Uploading $FILE to $BUCKET..."
gsutil cp "$FILE" "$BUCKET/"

FNAME=$(basename "$FILE")
DEST="$BUCKET/$FNAME"

if [ "$PUBLIC_FLAG" = "--public" ]; then
  echo "Making object public..."
  gsutil acl ch -u AllUsers:R "$DEST"
  echo "Public URL: https://storage.googleapis.com/${BUCKET#gs://}/$FNAME"
else
  echo "To generate a signed URL (valid 7 days):"
  echo "  gsutil signurl -d 7d /path/to/your-service-account.json $DEST"
fi
