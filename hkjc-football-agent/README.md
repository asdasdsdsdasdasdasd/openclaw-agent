# HKJC Football Scrape Pipeline

Deterministic Python + Playwright pipeline to discover HKJC football match results, scrape **corner counts** (詳細賽果) and **closing odds** (最後賠率), with SQLite checkpoints and resumable parallel workers.

Target site: [HKJC football results](https://bet.hkjc.com/ch/football/results#search)

---

## What it collects

For each match (`FBxxxx`):

| Field | Source |
|-------|--------|
| `match_id`, date, competition, teams, scores | Discover (GraphQL) + results table |
| `corners` | 詳細賽果 — 半場/全場開出角球 |
| `odds_closing` | 最後賠率 — 8 sections (主客和, 讓球, 入球大細, 角球大細, …) |

Excludes live / same-match-combo markets (`即場`, `同場過關`).

---

## Architecture

```
discover.js (HKJC GraphQL via hkjc-api)
        │
        ▼
  pipeline.db (SQLite, WAL)     ← pending / done / error checkpoints
        │
        ▼
pool_scrape.py (N × Playwright)  ← one calendar day per worker at a time
        │
        ▼
output/records-YYYY-MM-DD.jsonl  ← per-day shards
        │
        ▼
merge_records.py → output/records.json
```

**Recommended runner:** day pool (`run-hkjc-pipeline-pool.sh`) — workers claim days with pending work from a shared queue. Only **pending** or retryable **error** rows are scraped.

> **Note:** Discover uses HKJC GraphQL; scrape uses the results **web page**. In rare cases API metadata (teams/competition) may not match the row shown on the website for the same `match_id`. Treat scraped `teams` on the page as ground truth when validating odds.

---

## Prerequisites

```bash
cd hkjc-football-agent
npm install                    # discover.js (better-sqlite3, hkjc-api)
pip install playwright         # or use system python with playwright
python3 -m playwright install chromium
```

---

## Quick start

From repo root (`/mnt/d/openclaw`):

```bash
# Full run: discover → scrape (1 worker) → merge
./scripts/run-hkjc-pipeline-pool.sh --from 2025-06 --to 2026-06

# Resume scrape only (after IP block / crash)
./scripts/run-hkjc-pipeline-pool.sh --from 2025-06 --to 2026-06 --workers 1 --scrape-only

# Merge JSONL shards only
./scripts/run-hkjc-pipeline-pool.sh --from 2025-06 --to 2026-06 --merge-only
```

### Reset failed matches and retry

```bash
sqlite3 hkjc-football-agent/data/pipeline.db \
  "UPDATE matches SET status='pending', retries=0, last_error=NULL WHERE status='error';"

./scripts/run-hkjc-pipeline-pool.sh --from 2025-06 --to 2026-06 --workers 1 --scrape-only
```

### Reset bulk false errors from date-search timeouts

```bash
sqlite3 hkjc-football-agent/data/pipeline.db \
  "UPDATE matches SET status='pending', retries=0, last_error=NULL
   WHERE status='error' AND last_error LIKE 'Date search failed%';"
```

---

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/run-hkjc-pipeline-pool.sh` | **Primary** — day-pool workers (default **1** worker) |
| `scripts/run-hkjc-pipeline-multi.sh` | Legacy — one worker per calendar month |
| `scripts/run-hkjc-pipeline.sh` | Single-worker discover → scrape |

### Pool options

```bash
./scripts/run-hkjc-pipeline-pool.sh --from YYYY-MM --to YYYY-MM \
  [--workers N]          # default 1; use 12+ only if HKJC is not rate-limiting you
  [--discover-only]
  [--scrape-only]
  [--merge-only]
  [--headed]             # show browser (debug)
  [--db PATH]
```

---

## Pipeline modules

| File | Role |
|------|------|
| `pipeline/discover.js` | Loop days, paginate GraphQL `matchResult`, upsert into SQLite |
| `pipeline/scrape.py` | Playwright scraper; React date search; per-match corners + odds |
| `pipeline/pool_scrape.py` | Day queue + multiprocessing worker pool |
| `pipeline/db.py` | Schema, `fetch_pending`, day locks, checkpoints |
| `pipeline/parsers.py` | Corner + 8 closing-odds section parsers |
| `pipeline/storage.py` | JSONL append + merge into `records.json` |
| `pipeline/merge_records.py` | Merge `records-*.jsonl` shards |
| `pipeline/config.py` | Timeouts, delays, worker defaults |

---

## Outputs

| Path | Description |
|------|-------------|
| `data/pipeline.db` | Checkpoint DB (gitignored) |
| `output/records-YYYY-MM-DD.jsonl` | Per-day scrape shards |
| `output/records.json` | Merged final dataset |
| `logs/pool-worker-NN.log` | Per-worker scrape log |
| `logs/pool-scrape-*.log` | Orchestrator log |

### Check progress

```bash
sqlite3 data/pipeline.db "SELECT status, COUNT(*) FROM matches GROUP BY status;"

tail -f logs/pool-worker-01.log
```

### Record shape (excerpt)

```json
{
  "date": "28/06/2026",
  "match_id": "FB0119",
  "competition": "世盃",
  "teams": "巴拿馬 對 英格蘭",
  "scores": { "half_time": "0 : 0", "full_time": "1 : 5" },
  "corners": { "half_time": { "total": 3, "home": 1, "away": 2 } },
  "odds_closing": {
    "主客和": [{ "selection": "巴拿馬 (主隊勝)", "odds": 15.0 }],
    "讓球": [{ "line": "[+2.5/+3]", "odds": 1.59 }]
  }
}
```

---

## How date search works (headless)

HKJC’s datepicker is React-controlled; UI clicks fail headless. The scraper:

1. Opens the results page and selects the **搜尋** tab
2. Waits for React to hydrate (`SEARCH_REACT_READY_MS`)
3. Walks the React fiber tree to call `onChangeSearchParams` + search button (component `Jf`)
4. Waits up to **90s** for result rows or 「共找到」
5. For each match: click 詳細賽果 → parse corners → back → click `%` → parse 最後賠率

Tune waits in `pipeline/config.py`:

| Constant | Default | Meaning |
|----------|---------|---------|
| `DEFAULT_POOL_WORKERS` | `1` | Concurrent browsers |
| `MATCH_DELAY_SEC` | `3.0` | Pause between matches |
| `SEARCH_RESULTS_TIMEOUT_MS` | `90000` | Step 4: wait for table |
| `SEARCH_REACT_READY_MS` | `4000` | Step 3: pre-search hydrate |
| `SEARCH_DAY_ATTEMPTS` | `6` | Retries per day search |

If a day search fails after all retries, matches **stay pending** (not bulk-marked error). The worker skips the day and tries another.

---

## Concurrency and rate limits

HKJC may throttle or block IPs under heavy automated load.

| Workers | Guidance |
|---------|----------|
| **1** | Safest after a block; slow but stable |
| **12** | Worked for bulk runs when not blocked |
| **32** | Often caused mass `Date search failed` timeouts |

Signs of blocking: date search timeouts, empty pages, HTTP errors. **Wait several hours** (or change network) before retrying; keep `--workers 1` and increase `MATCH_DELAY_SEC` if needed.

---

## Manual / debug commands

```bash
cd hkjc-football-agent

# Discover one range
node pipeline/discover.js --start 2026-06-01 --end 2026-06-30 --db data/pipeline.db

# Scrape one day
python3 pipeline/scrape.py --date 2026-06-28 --headed

# Scrape one match
python3 pipeline/scrape.py --match-id FB0119 --headed

# Pool scrape directly
python3 pipeline/pool_scrape.py --start 2025-06-01 --end 2026-06-30 --workers 1
```

---

## Legacy: OpenClaw agent

The older OpenClaw + DeepSeek browser agent is still available for experiments:

```bash
./scripts/run-openclaw-hkjc-football-agent.sh june
```

Production bulk scraping should use **this pipeline** (`run-hkjc-pipeline-pool.sh`), not OpenClaw.

---

## Known limitations

1. **Closing odds coverage** — many matches have scores but empty `odds_closing` (HKJC did not offer 最後賠率 for that market).
2. **Discover vs page mismatch** — GraphQL `teams`/`competition` can differ from the results table for the same `match_id`; validate before trusting World Cup / qualifier odds.
3. **Log line `odds_sections=8`** counts parser keys, not non-empty odds lines.
4. **Discover pagination** — `discover.js` dedupes by `match_id` and caps pages per day to avoid API duplicate loops.

---

## License / data

Scraped data is from HKJC public results pages. Use responsibly; respect site terms and rate limits.
