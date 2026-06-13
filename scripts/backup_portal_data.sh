#!/usr/bin/env bash
# Copy SQLite DB, embeddings gallery, and portal-uploaded images to a timestamped backup folder.
set -euo pipefail
cd "$(dirname "$0")/.."
STAMP="$(date +%Y%m%d_%H%M%S)"
DEST="backups/${STAMP}"
mkdir -p "${DEST}"

if [[ -f data/attendance.db ]]; then
  cp -p data/attendance.db "${DEST}/"
fi
if [[ -d data/embeddings ]]; then
  mkdir -p "${DEST}/data"
  cp -R data/embeddings "${DEST}/data/"
fi
if [[ -d data/portal ]]; then
  mkdir -p "${DEST}/data"
  cp -R data/portal "${DEST}/data/"
fi

echo "Backup written to ${DEST}/"
ls -la "${DEST}"
