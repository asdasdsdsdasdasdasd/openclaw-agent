#!/usr/bin/env bash
# HKJC deterministic discover → scrape pipeline
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
AGENT_DIR="$ROOT/hkjc-football-agent"
DB="$AGENT_DIR/data/pipeline.db"
START=""
END=""
DISCOVER_ONLY=0
SCRAPE_ONLY=0
MATCH_ID=""
DATE=""
HEADED=0

usage() {
  cat <<EOF
Usage: $(basename "$0") --start YYYY-MM-DD --end YYYY-MM-DD [options]

Options:
  --start DATE       First day (inclusive)
  --end DATE         Last day (inclusive)
  --db PATH          SQLite checkpoint (default: hkjc-football-agent/data/pipeline.db)
  --discover-only    Run GraphQL discovery only
  --scrape-only      Run browser scrape only (skip discover)
  --match-id ID      Scrape single match (passes through to scrape.py)
  --date DATE        Scrape single ISO date (passes through to scrape.py)
  --headed           Show browser window during scrape
  -h, --help         Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --start) START="$2"; shift 2 ;;
    --end) END="$2"; shift 2 ;;
    --db) DB="$2"; shift 2 ;;
    --discover-only) DISCOVER_ONLY=1; shift ;;
    --scrape-only) SCRAPE_ONLY=1; shift ;;
    --match-id) MATCH_ID="$2"; shift 2 ;;
    --date) DATE="$2"; shift 2 ;;
    --headed) HEADED=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage; exit 1 ;;
  esac
done

if [[ -z "$START" || -z "$END" ]]; then
  if [[ -z "$MATCH_ID" && -z "$DATE" ]]; then
    echo "Required: --start and --end (unless --match-id or --date with --scrape-only)" >&2
    usage
    exit 1
  fi
fi

DATE_RANGE=""
if [[ -n "$START" && -n "$END" ]]; then
  # metadata label DD/MM/YYYY - DD/MM/YYYY
  to_dmy() { echo "$1" | awk -F- '{print $3"/"$2"/"$1}'; }
  DATE_RANGE="$(to_dmy "$START") - $(to_dmy "$END")"
fi

cd "$AGENT_DIR"

if [[ "$SCRAPE_ONLY" -eq 0 && -n "$START" && -n "$END" ]]; then
  echo "==> Discover $START .. $END"
  node pipeline/discover.js --start "$START" --end "$END" --db "$DB"
fi

if [[ "$DISCOVER_ONLY" -eq 1 ]]; then
  echo "Discover complete (--discover-only)."
  exit 0
fi

SCRAPE_ARGS=(python3 pipeline/scrape.py --db "$DB")
[[ -n "$DATE_RANGE" ]] && SCRAPE_ARGS+=(--date-range "$DATE_RANGE")
[[ -n "$MATCH_ID" ]] && SCRAPE_ARGS+=(--match-id "$MATCH_ID")
[[ -n "$DATE" ]] && SCRAPE_ARGS+=(--date "$DATE")
[[ "$HEADED" -eq 1 ]] && SCRAPE_ARGS+=(--headed)

echo "==> Scrape"
"${SCRAPE_ARGS[@]}"

echo "==> Status"
python3 - <<PY
import sqlite3
from pathlib import Path
db = Path("$DB")
conn = sqlite3.connect(db)
conn.row_factory = sqlite3.Row
for row in conn.execute("SELECT status, COUNT(*) AS n FROM matches GROUP BY status ORDER BY status"):
    print(f"  {row['status']}: {row['n']}")
total = conn.execute("SELECT COUNT(*) AS n FROM matches").fetchone()[0]
print(f"  total: {total}")
errors = conn.execute(
    "SELECT match_id, last_error FROM matches WHERE status='error' ORDER BY match_id LIMIT 20"
).fetchall()
if errors:
    print("  recent errors:")
    for e in errors:
        print(f"    {e['match_id']}: {e['last_error'][:120]}")
conn.close()
PY

echo "Done."
