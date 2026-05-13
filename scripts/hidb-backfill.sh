#!/usr/bin/env bash
# Full backfill from PostgreSQL to HiDB (PostgreSQL-compatible protocol).
#
# Usage:
#   SOURCE_DSN='postgresql://...' TARGET_DSN='postgresql://...' ./scripts/hidb-backfill.sh
#
# Optional:
#   WORK_DIR=/tmp/hidb-migration
#   RESTORE_JOBS=4
set -euo pipefail

if [[ -z "${SOURCE_DSN:-}" ]]; then
  echo "ERROR: SOURCE_DSN is required" >&2
  exit 1
fi

if [[ -z "${TARGET_DSN:-}" ]]; then
  echo "ERROR: TARGET_DSN is required" >&2
  exit 1
fi

WORK_DIR="${WORK_DIR:-/tmp/hidb-migration}"
DUMP_FILE="${WORK_DIR}/full.dump"
mkdir -p "${WORK_DIR}"

echo "[1/4] Exporting snapshot from source..."
pg_dump "${SOURCE_DSN}" \
  --format=custom \
  --no-owner \
  --no-privileges \
  --file "${DUMP_FILE}"

echo "[2/4] Restoring snapshot to HiDB..."
pg_restore "${DUMP_FILE}" \
  --dbname "${TARGET_DSN}" \
  --clean \
  --if-exists \
  --no-owner \
  --no-privileges \
  --jobs "${RESTORE_JOBS:-4}"

echo "[3/4] Running ANALYZE on HiDB..."
psql "${TARGET_DSN}" -v ON_ERROR_STOP=1 -c "ANALYZE;"

echo "[4/4] Backfill completed."
echo "Snapshot file: ${DUMP_FILE}"