#!/usr/bin/env bash
# Cutover helper for zero-downtime migration toggles.
#
# Usage:
#   POSTGRES_DSN='postgresql://...' HIDB_DSN='postgresql://...' ./scripts/hidb-cutover.sh <phase> [percent]
#
# Phases:
#   dual-write       -> write on PostgreSQL + dual-write to HiDB, read on PostgreSQL
#   canary-read N    -> enable canary read with N percent traffic on HiDB
#   cutover-hidb     -> switch read/write to HiDB, keep PostgreSQL as rollback source
#   finalize-hidb    -> keep HiDB primary and disable dual-write
#   rollback-postgres-> switch read/write back to PostgreSQL quickly
#
# Optional:
#   ENV_FILE=.env (default)
set -euo pipefail

ENV_FILE="${ENV_FILE:-.env}"
PHASE="${1:-}"
CANARY_PERCENT="${2:-${DB_CUTOVER_PERCENT:-10}}"

require_var() {
  local name="$1"
  if [[ -z "${!name:-}" ]]; then
    echo "ERROR: ${name} is required for this phase." >&2
    exit 1
  fi
}

escape_sed_replacement() {
  printf '%s' "$1" | sed -e 's/[\\&|]/\\\\&/g'
}

set_env() {
  local key="$1"
  local value="$2"
  local escaped
  escaped="$(escape_sed_replacement "${value}")"

  if [[ ! -f "${ENV_FILE}" ]]; then
    touch "${ENV_FILE}"
  fi

  if grep -q "^${key}=" "${ENV_FILE}"; then
    sed -i.bak "s|^${key}=.*|${key}=${escaped}|" "${ENV_FILE}"
  else
    echo "${key}=${value}" >> "${ENV_FILE}"
  fi
}

validate_percent() {
  local p="$1"
  if ! [[ "${p}" =~ ^[0-9]+$ ]] || (( p < 0 || p > 100 )); then
    echo "ERROR: cutover percent must be an integer in [0,100]." >&2
    exit 1
  fi
}

print_state() {
  echo "Updated ${ENV_FILE}:"
  grep -E '^DB_(PROVIDER|DSN_WRITE|DSN_READ|LEGACY_DSN_WRITE|LEGACY_DSN_READ|DUAL_WRITE_ENABLED|READ_TARGET|CUTOVER_PERCENT)=' "${ENV_FILE}" || true
}

if [[ -z "${PHASE}" ]]; then
  echo "ERROR: missing phase." >&2
  exit 1
fi

case "${PHASE}" in
  dual-write)
    require_var POSTGRES_DSN
    require_var HIDB_DSN
    set_env DB_PROVIDER postgres
    set_env DB_DSN_WRITE "${POSTGRES_DSN}"
    set_env DB_DSN_READ "${POSTGRES_DSN}"
    set_env DB_LEGACY_DSN_WRITE "${HIDB_DSN}"
    set_env DB_LEGACY_DSN_READ "${HIDB_DSN}"
    set_env DB_DUAL_WRITE_ENABLED true
    set_env DB_READ_TARGET postgres
    set_env DB_CUTOVER_PERCENT 0
    ;;

  canary-read)
    validate_percent "${CANARY_PERCENT}"
    set_env DB_READ_TARGET canary
    set_env DB_CUTOVER_PERCENT "${CANARY_PERCENT}"
    ;;

  cutover-hidb)
    require_var POSTGRES_DSN
    require_var HIDB_DSN
    set_env DB_PROVIDER hidb_pg
    set_env DB_DSN_WRITE "${HIDB_DSN}"
    set_env DB_DSN_READ "${HIDB_DSN}"
    set_env DB_LEGACY_DSN_WRITE "${POSTGRES_DSN}"
    set_env DB_LEGACY_DSN_READ "${POSTGRES_DSN}"
    set_env DB_DUAL_WRITE_ENABLED true
    set_env DB_READ_TARGET hidb
    set_env DB_CUTOVER_PERCENT 100
    ;;

  finalize-hidb)
    set_env DB_PROVIDER hidb_pg
    set_env DB_READ_TARGET hidb
    set_env DB_CUTOVER_PERCENT 100
    set_env DB_DUAL_WRITE_ENABLED false
    ;;

  rollback-postgres)
    require_var POSTGRES_DSN
    require_var HIDB_DSN
    set_env DB_PROVIDER postgres
    set_env DB_DSN_WRITE "${POSTGRES_DSN}"
    set_env DB_DSN_READ "${POSTGRES_DSN}"
    set_env DB_LEGACY_DSN_WRITE "${HIDB_DSN}"
    set_env DB_LEGACY_DSN_READ "${HIDB_DSN}"
    set_env DB_DUAL_WRITE_ENABLED true
    set_env DB_READ_TARGET postgres
    set_env DB_CUTOVER_PERCENT 0
    ;;

  *)
    echo "ERROR: unsupported phase '${PHASE}'." >&2
    exit 1
    ;;
esac

print_state
