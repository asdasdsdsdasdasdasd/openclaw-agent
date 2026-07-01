#!/usr/bin/env bash
# Day-pool HKJC pipeline: N workers claim one calendar day at a time.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
AGENT_DIR="$ROOT/hkjc-football-agent"
DB="$AGENT_DIR/data/pipeline.db"
FROM=""
TO=""
WORKERS=1
DISCOVER_ONLY=0
SCRAPE_ONLY=0
MERGE_ONLY=0
HEADED=0

usage() {
  cat <<EOF
Usage: $(basename "$0") --from YYYY-MM --to YYYY-MM [options]

${WORKERS} workers pull one calendar day at a time from a shared queue.
Only pending / retryable matches are scraped.

Example: $(basename "$0") --from 2025-06 --to 2026-06 --workers 32

Options:
  --from YYYY-MM       First month (inclusive)
  --to YYYY-MM         Last month (inclusive)
  --workers N          Concurrent browsers (default: 1)
  --db PATH            SQLite checkpoint
  --discover-only      GraphQL discovery only
  --scrape-only        Skip discover; run day pool only
  --merge-only         Merge records-*.jsonl -> records.json
  --headed             Show browser windows
  -h, --help           Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --from) FROM="$2"; shift 2 ;;
    --to) TO="$2"; shift 2 ;;
    --workers) WORKERS="$2"; shift 2 ;;
    --db) DB="$2"; shift 2 ;;
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

echo "==> Stop any legacy month workers"
pkill -f "pipeline/scrape.py" 2>/dev/null || true
sleep 2

echo "==> Day pool: $WORKERS workers, $START_DATE .. $END_DATE"
POOL_ARGS=(python3 pipeline/pool_scrape.py --db "$DB" --start "$START_DATE" --end "$END_DATE" --workers "$WORKERS")
[[ "$HEADED" -eq 1 ]] && POOL_ARGS+=(--headed)
"${POOL_ARGS[@]}" 2>&1 | tee "logs/pool-scrape-${FROM}-${TO}.log"

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
conn.close()
PY

echo "Done."
