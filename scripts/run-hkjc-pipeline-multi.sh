#!/usr/bin/env bash
# Multi-worker HKJC pipeline: one browser worker per calendar month.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
AGENT_DIR="$ROOT/hkjc-football-agent"
DB="$AGENT_DIR/data/pipeline.db"
FROM=""
TO=""
MAX_PARALLEL=0
DISCOVER_ONLY=0
SCRAPE_ONLY=0
MERGE_ONLY=0
HEADED=0

usage() {
  cat <<EOF
Usage: $(basename "$0") --from YYYY-MM --to YYYY-MM [options]

Launch one scrape worker per month in parallel (separate Chromium each).
Example: $(basename "$0") --from 2025-06 --to 2026-06

Options:
  --from YYYY-MM     First month (inclusive)
  --to YYYY-MM       Last month (inclusive)
  --db PATH          SQLite checkpoint (default: data/pipeline.db)
  --max-parallel N   Cap concurrent workers (0 = all months at once)
  --discover-only    Run GraphQL discovery for full range only
  --scrape-only      Skip discover; launch month workers only
  --merge-only       Merge records-YYYY-MM.jsonl shards into records.json
  --headed           Show browser windows
  -h, --help         Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --from) FROM="$2"; shift 2 ;;
    --to) TO="$2"; shift 2 ;;
    --db) DB="$2"; shift 2 ;;
    --max-parallel) MAX_PARALLEL="$2"; shift 2 ;;
    --discover-only) DISCOVER_ONLY=1; shift ;;
    --scrape-only) SCRAPE_ONLY=1; shift ;;
    --merge-only) MERGE_ONLY=1; shift ;;
    --headed) HEADED=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage; exit 1 ;;
  esac
done

if [[ -z "$FROM" || -z "$TO" ]]; then
  echo "Required: --from YYYY-MM --to YYYY-MM" >&2
  usage
  exit 1
fi

cd "$AGENT_DIR"
mkdir -p logs output

to_dmy() { echo "$1" | awk -F- '{print $3"/"$2"/"$1}'; }

START_DATE="${FROM}-01"
END_Y="${TO%-*}"
END_M="${TO#*-}"
END_DAY="$(python3 - <<PY
import calendar
y, m = int("$END_Y"), int("$END_M")
print(calendar.monthrange(y, m)[1])
PY
)"
END_DATE="${END_Y}-${END_M}-${END_DAY}"
DATE_RANGE_LABEL="$(to_dmy "$START_DATE") - $(to_dmy "$END_DATE")"

mapfile -t MONTHS < <(python3 - <<PY
import calendar
from datetime import date

def parse_ym(s):
    y, m = s.split("-")
    return int(y), int(m)

sy, sm = parse_ym("$FROM")
ey, em = parse_ym("$TO")
y, m = sy, sm
while (y, m) <= (ey, em):
    last = calendar.monthrange(y, m)[1]
    print(f"{y:04d}-{m:02d}-01 {y:04d}-{m:02d}-{last:02d} {y:04d}-{m:02d}")
    m += 1
    if m > 12:
        m, y = 1, y + 1
PY
)

if [[ "$MERGE_ONLY" -eq 1 ]]; then
  echo "==> Merge JSONL shards"
  python3 pipeline/merge_records.py --date-range "$DATE_RANGE_LABEL"
  exit 0
fi

if [[ "$SCRAPE_ONLY" -eq 0 ]]; then
  echo "==> Discover $START_DATE .. $END_DATE"
  node pipeline/discover.js --start "$START_DATE" --end "$END_DATE" --db "$DB"
fi

if [[ "$DISCOVER_ONLY" -eq 1 ]]; then
  echo "Discover complete."
  exit 0
fi

echo "==> Launch ${#MONTHS[@]} month workers (${FROM} .. ${TO})"
PIDS=()
WORKER_LABELS=()

run_worker() {
  local start="$1" end="$2" label="$3"
  local log="logs/worker-${label}.log"
  local jsonl="output/records-${label}.jsonl"
  local range_label
  range_label="$(to_dmy "$start") - $(to_dmy "$end")"
  local args=(python3 pipeline/scrape.py --db "$DB" --start "$start" --end "$end"
    --output-jsonl "$jsonl" --json-only --date-range "$range_label")
  [[ "$HEADED" -eq 1 ]] && args+=(--headed)
  echo "  worker $label: $start .. $end -> $jsonl"
  "${args[@]}" >"$log" 2>&1 &
  PIDS+=($!)
  WORKER_LABELS+=("$label")
  sleep 0.3
}

if [[ "$MAX_PARALLEL" -gt 0 ]]; then
  running=0
  for entry in "${MONTHS[@]}"; do
    read -r ms me ml <<<"$entry"
    run_worker "$ms" "$me" "$ml"
    running=$((running + 1))
    if [[ "$running" -ge "$MAX_PARALLEL" ]]; then
      wait -n || true
      running=$((running - 1))
    fi
  done
  wait || true
else
  for entry in "${MONTHS[@]}"; do
    read -r ms me ml <<<"$entry"
    run_worker "$ms" "$me" "$ml"
  done
  echo "==> Waiting for workers: ${WORKER_LABELS[*]}"
  fail=0
  for i in "${!PIDS[@]}"; do
    if ! wait "${PIDS[$i]}"; then
      echo "  worker ${WORKER_LABELS[$i]} FAILED (see logs/worker-${WORKER_LABELS[$i]}.log)"
      fail=1
    fi
  done
  [[ "$fail" -eq 0 ]] || echo "Some workers failed; re-run with --scrape-only to resume."
fi

echo "==> Merge JSONL shards"
python3 pipeline/merge_records.py --date-range "$DATE_RANGE_LABEL"

echo "==> Status"
python3 - <<PY
import sqlite3
from pathlib import Path
db = Path("$DB")
conn = sqlite3.connect(db)
conn.row_factory = sqlite3.Row
for row in conn.execute(
    "SELECT status, COUNT(*) AS n FROM matches WHERE match_date >= ? AND match_date <= ? GROUP BY status ORDER BY status",
    ("$START_DATE", "$END_DATE"),
):
    print(f"  {row['status']}: {row['n']}")
total = conn.execute(
    "SELECT COUNT(*) AS n FROM matches WHERE match_date >= ? AND match_date <= ?",
    ("$START_DATE", "$END_DATE"),
).fetchone()[0]
print(f"  total in range: {total}")
conn.close()
PY

echo "Done."
