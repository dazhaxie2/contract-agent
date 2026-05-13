#!/usr/bin/env bash
# HiDB (PostgreSQL-compatible) bootstrap script.
# Keep bootstrap DDL dialect-neutral and avoid PostgreSQL-only extensions.
set -euo pipefail

psql -v ON_ERROR_STOP=1 --username "${POSTGRES_USER}" --dbname "${POSTGRES_DB}" <<'EOSQL'
CREATE TABLE IF NOT EXISTS db_bootstrap_marker (
    id BIGINT PRIMARY KEY,
    db_provider VARCHAR(32) NOT NULL,
    initialized_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_db_bootstrap_marker_provider
  ON db_bootstrap_marker (db_provider);

INSERT INTO db_bootstrap_marker (id, db_provider)
VALUES (1, 'hidb_pg')
ON CONFLICT (id) DO UPDATE
SET db_provider = EXCLUDED.db_provider,
    updated_at = CURRENT_TIMESTAMP;

SELECT 'HiDB bootstrap initialized successfully' AS status;
EOSQL
