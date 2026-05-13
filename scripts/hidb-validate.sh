#!/usr/bin/env bash
# Validate migrated data between PostgreSQL source and HiDB target.
#
# Usage:
#   SOURCE_DSN='postgresql://...' TARGET_DSN='postgresql://...' ./scripts/hidb-validate.sh
#
# Optional:
#   TABLES='table_a,table_b'
#   SAMPLE_ROWS=1000
set -euo pipefail

if [[ -z "${SOURCE_DSN:-}" ]]; then
  echo "ERROR: SOURCE_DSN is required" >&2
  exit 1
fi

if [[ -z "${TARGET_DSN:-}" ]]; then
  echo "ERROR: TARGET_DSN is required" >&2
  exit 1
fi

SAMPLE_ROWS="${SAMPLE_ROWS:-1000}"

run_sql() {
  local dsn="$1"
  local sql="$2"
  psql "$dsn" -X -v ON_ERROR_STOP=1 -At -c "$sql"
}

if [[ -n "${TABLES:-}" ]]; then
  IFS=',' read -r -a TABLE_LIST <<<"${TABLES}"
else
  mapfile -t TABLE_LIST < <(
    run_sql "${SOURCE_DSN}" "
      SELECT tablename
      FROM pg_tables
      WHERE schemaname = 'public'
        AND tablename NOT LIKE 'pg_%'
      ORDER BY 1;
    "
  )
fi

if [[ ${#TABLE_LIST[@]} -eq 0 ]]; then
  echo "No tables found to validate."
  exit 0
fi

failures=0

printf "%-32s %-10s %-10s %-8s %-8s %-8s\n" "table" "src_rows" "dst_rows" "rows" "pk" "hash"
printf "%.0s-" {1..84}
printf "\n"

for raw_table in "${TABLE_LIST[@]}"; do
  table="$(echo "${raw_table}" | xargs)"
  [[ -z "${table}" ]] && continue

  if ! src_rows=$(run_sql "${SOURCE_DSN}" "SELECT COUNT(*) FROM \"${table}\";"); then
    echo "WARN: skip ${table} (source query failed)" >&2
    failures=$((failures + 1))
    continue
  fi

  if ! dst_rows=$(run_sql "${TARGET_DSN}" "SELECT COUNT(*) FROM \"${table}\";"); then
    echo "WARN: skip ${table} (target query failed)" >&2
    failures=$((failures + 1))
    continue
  fi

  rows_status="OK"
  if [[ "${src_rows}" != "${dst_rows}" ]]; then
    rows_status="DIFF"
    failures=$((failures + 1))
  fi

  pk_status="N/A"
  order_expr="row_to_json(t)::text"

  pk_cols="$(run_sql "${SOURCE_DSN}" "
    SELECT string_agg(format('%I', kcu.column_name), ', ' ORDER BY kcu.ordinal_position)
    FROM information_schema.table_constraints tc
    JOIN information_schema.key_column_usage kcu
      ON tc.constraint_name = kcu.constraint_name
     AND tc.table_schema = kcu.table_schema
     AND tc.table_name = kcu.table_name
    WHERE tc.constraint_type = 'PRIMARY KEY'
      AND tc.table_schema = 'public'
      AND tc.table_name = '${table}';
  ")"

  if [[ -n "${pk_cols}" ]]; then
    order_expr="${pk_cols}"
    if src_pk=$(run_sql "${SOURCE_DSN}" "SELECT COUNT(DISTINCT (${pk_cols})) FROM \"${table}\";") \
      && dst_pk=$(run_sql "${TARGET_DSN}" "SELECT COUNT(DISTINCT (${pk_cols})) FROM \"${table}\";"); then
      if [[ "${src_pk}" == "${dst_pk}" ]]; then
        pk_status="OK"
      else
        pk_status="DIFF"
        failures=$((failures + 1))
      fi
    else
      pk_status="ERR"
      failures=$((failures + 1))
    fi
  fi

  hash_sql="
    WITH sampled AS (
      SELECT row_to_json(t)::text AS row_txt
      FROM \"${table}\" t
      ORDER BY ${order_expr}
      LIMIT ${SAMPLE_ROWS}
    )
    SELECT COALESCE(md5(string_agg(md5(row_txt), '' ORDER BY row_txt)), '')
    FROM sampled;
  "

  hash_status="OK"
  if src_hash=$(run_sql "${SOURCE_DSN}" "${hash_sql}") \
    && dst_hash=$(run_sql "${TARGET_DSN}" "${hash_sql}"); then
    if [[ "${src_hash}" != "${dst_hash}" ]]; then
      hash_status="DIFF"
      failures=$((failures + 1))
    fi
  else
    hash_status="ERR"
    failures=$((failures + 1))
  fi

  printf "%-32s %-10s %-10s %-8s %-8s %-8s\n" \
    "${table}" "${src_rows}" "${dst_rows}" "${rows_status}" "${pk_status}" "${hash_status}"
done

if [[ ${failures} -gt 0 ]]; then
  echo "Validation finished with ${failures} mismatch/error(s)." >&2
  exit 2
fi

echo "Validation passed."
