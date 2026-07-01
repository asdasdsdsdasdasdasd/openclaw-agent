#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AGENT_DIR="${ROOT_DIR}/hkjc-football-agent"
PROMPT_FILE="${AGENT_DIR}/openclaw_autonomous_prompt.txt"
FULL_PROMPT_FILE="${AGENT_DIR}/openclaw_full_record_prompt.txt"
CONFIG_FILE="${AGENT_DIR}/config.json"
LOG_DIR="${AGENT_DIR}/logs"
OUT_DIR="${AGENT_DIR}/output"
MODE="${1:-june}"
AGENT_TIMEOUT="${OPENCLAW_AGENT_TIMEOUT:-900}"
MAX_MATCHES="${OPENCLAW_MAX_MATCHES:-0}"
SESSION_ID="${OPENCLAW_SESSION_ID:-hkjc-football-${MODE}-$(date +%Y%m%d-%H%M%S)}"
MODEL_ID="${OPENCLAW_MODEL_ID:-deepseek/deepseek-chat}"

DATE_START="${OPENCLAW_DATE_START:-01/06/2026}"
DATE_END="${OPENCLAW_DATE_END:-30/06/2026}"
DATE_RANGE="${DATE_START} - ${DATE_END}"

if [[ ! -f "${PROMPT_FILE}" ]]; then
  echo "Prompt file not found: ${PROMPT_FILE}" >&2
  exit 1
fi

mkdir -p "${LOG_DIR}" "${OUT_DIR}"
RUN_LOG="${LOG_DIR}/openclaw-hkjc-football-$(date +%F).log"

export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
if [[ -s "${NVM_DIR}/nvm.sh" ]]; then
  # shellcheck disable=SC1090
  . "${NVM_DIR}/nvm.sh"
fi

ensure_browser() {
  if ! curl -sf http://127.0.0.1:9222/json/version >/dev/null 2>&1; then
    echo "Starting Chromium CDP on port 9222..."
    export DISPLAY="${DISPLAY:-:0}"
    mkdir -p "${HOME}/snap/chromium/common/openclaw-cdp"
    nohup /snap/bin/chromium \
      --remote-debugging-port=9222 \
      --user-data-dir="${HOME}/snap/chromium/common/openclaw-cdp" \
      --no-first-run --no-default-browser-check \
      >/tmp/chromium-cdp.log 2>&1 &
    for _ in $(seq 1 15); do
      curl -sf http://127.0.0.1:9222/json/version >/dev/null 2>&1 && break
      sleep 1
    done
  fi
  openclaw browser status >/dev/null 2>&1 || true
}

BASE_MESSAGE="$(<"${PROMPT_FILE}")"

if [[ "${MODE}" == "june" ]]; then
  MODE_MESSAGE=$'\n\nRuntime mode: JUNE_SEARCH\nDate range override: '"${DATE_RANGE}"$'\nExecute Steps A-E only (skip Step F corners).\nDo NOT scroll. Use pagination-box clicks only.\nSave matches to '"${OUT_DIR}/matches.json"
elif [[ "${MODE}" == "custom" ]]; then
  DATE_START="${2:-${DATE_START}}"
  DATE_END="${3:-${DATE_END}}"
  DATE_RANGE="${DATE_START} - ${DATE_END}"
  MODE_MESSAGE=$'\n\nRuntime mode: CUSTOM_SEARCH\nDate range override: '"${DATE_RANGE}"$'\nExecute Steps A-E. Save to '"${OUT_DIR}/matches.json"
elif [[ "${MODE}" == "corners" ]]; then
  MODE_MESSAGE=$'\n\nRuntime mode: CORNERS_SAMPLE\nAfter Step E (or instead if matches.json exists), run Step F for first match.\nSave corners to '"${OUT_DIR}/corners-sample.json"
elif [[ "${MODE}" == "june-full" || "${MODE}" == "june-full-resume" ]]; then
  if [[ ! -f "${FULL_PROMPT_FILE}" ]]; then
    echo "Full record prompt not found: ${FULL_PROMPT_FILE}" >&2
    exit 1
  fi
  BASE_MESSAGE="$(<"${FULL_PROMPT_FILE}")"
  AGENT_TIMEOUT="${OPENCLAW_AGENT_TIMEOUT:-7200}"
  if [[ "${MODE}" == "june-full-resume" ]]; then
    RESUME_IDS="$(python3 - <<PY
import json
from pathlib import Path
all_ids = [m["match_id"] for m in json.loads((Path("${OUT_DIR}") / "matches.json").read_text())["matches"]]
done = set()
full = Path("${OUT_DIR}") / "june-full-records.json"
if full.exists():
    done = {m["match_id"] for m in json.loads(full.read_text()).get("matches", [])}
print(",".join(i for i in all_ids if i not in done))
PY
)"
    if [[ -z "${RESUME_IDS}" ]]; then
      echo "Nothing to resume — all matches already in june-full-records.json" >&2
      exit 0
    fi
    MODE_MESSAGE=$'\n\nRuntime mode: JUNE_FULL_RECORD_RESUME\nProcess ONLY these match_ids (in order): '"${RESUME_IDS}"$'\nSkip any match_id already present in '"${OUT_DIR}/june-full-records.json"$'.\nUse '"${OUT_DIR}/matches.json"' as the match index; re-search June range if rows not visible.\nRecord scores, corners, competition, closing odds (exclude 即場/同場過關).\nUpsert incrementally to '"${OUT_DIR}/june-full-records.json"
  elif [[ "${MAX_MATCHES}" != "0" ]]; then
    MODE_MESSAGE=$'\n\nRuntime mode: JUNE_FULL_RECORD\nMAX_MATCHES='"${MAX_MATCHES}"$'\nProcess only the first '"${MAX_MATCHES}"$' matches from June search.\nRecord scores, corners, competition, closing odds (exclude 即場/同場過關).\nSave incrementally to '"${OUT_DIR}/june-full-records.json"
  else
    MODE_MESSAGE=$'\n\nRuntime mode: JUNE_FULL_RECORD\nProcess ALL June matches from search.\nRecord scores, corners, competition, closing odds (exclude 即場/同場過關).\nSave incrementally to '"${OUT_DIR}/june-full-records.json"
  fi
else
  echo "Unsupported mode: ${MODE}. Use: june | june-full | june-full-resume | custom START END | corners" >&2
  exit 1
fi

MESSAGE="${BASE_MESSAGE}${MODE_MESSAGE}"

ensure_browser

{
  echo "[$(date -Is)] START hkjc-football-agent mode=${MODE} date_range=${DATE_RANGE} model=${MODEL_ID} session=${SESSION_ID}"
  openclaw agent \
    --session-id "${SESSION_ID}" \
    --model "${MODEL_ID}" \
    --thinking off \
    --timeout "${AGENT_TIMEOUT}" \
    --message "${MESSAGE}" \
    --json
  echo "[$(date -Is)] DONE hkjc-football-agent mode=${MODE}"
} >>"${RUN_LOG}" 2>&1

echo "Run complete. Log: ${RUN_LOG}"
for f in matches.json june-full-records.json; do
  if [[ -f "${OUT_DIR}/${f}" ]]; then
    echo "Output: ${OUT_DIR}/${f}"
    python3 - <<PY
import json
from pathlib import Path
p = Path("${OUT_DIR}") / "${f}"
d = json.loads(p.read_text())
mc = d.get("match_count", len(d.get("matches", [])))
extra = ""
if d.get("matches") and d["matches"] and isinstance(d["matches"][0], dict):
    m0 = d["matches"][0]
    if m0.get("competition"):
        extra = " competition=" + m0.get("competition", "")
    if m0.get("odds_closing"):
        extra += " odds_sections=" + str(len(m0.get("odds_closing", {})))
print("  matches:", mc, extra)
PY
  fi
done
