#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AGENT_DIR="${ROOT_DIR}/scholarship-agent"
PROMPT_FILE="${AGENT_DIR}/openclaw_autonomous_prompt.txt"
LOGIN_PROMPT_FILE="${AGENT_DIR}/openclaw_login_prompt.txt"
CONFIG_FILE="${AGENT_DIR}/config.json"
LOG_DIR="${AGENT_DIR}/logs"
DOWNLOAD_DIR="${AGENT_DIR}/downloads"
MODE="${1:-download}"
AGENT_TIMEOUT="${OPENCLAW_AGENT_TIMEOUT:-7200}"
LOGIN_TIMEOUT="${OPENCLAW_LOGIN_TIMEOUT:-300}"
MAX_EMAILS="${OPENCLAW_MAX_EMAILS:-200}"
SESSION_ID="${OPENCLAW_SESSION_ID:-scholarship-outlook-${MODE}-$(date +%Y%m%d-%H%M%S)}"
MODEL_ID="${OPENCLAW_MODEL_ID:-deepseek/deepseek-chat}"

if [[ ! -f "${CONFIG_FILE}" ]]; then
  echo "Config file not found: ${CONFIG_FILE}" >&2
  exit 1
fi

mkdir -p "${LOG_DIR}" "${DOWNLOAD_DIR}"
RUN_LOG="${LOG_DIR}/openclaw-scholarship-$(date +%F).log"

export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
if [[ -s "${NVM_DIR}/nvm.sh" ]]; then
  # shellcheck disable=SC1090
  . "${NVM_DIR}/nvm.sh"
fi

run_agent() {
  local timeout="$1"
  local message="$2"
  openclaw agent \
    --session-id "${SESSION_ID}" \
    --model "${MODEL_ID}" \
    --thinking off \
    --timeout "${timeout}" \
    --message "${message}" \
    --json
}

if [[ "${MODE}" == "login" ]]; then
  if [[ ! -f "${LOGIN_PROMPT_FILE}" ]]; then
    echo "Login prompt file not found: ${LOGIN_PROMPT_FILE}" >&2
    exit 1
  fi
  MESSAGE="$(<"${LOGIN_PROMPT_FILE}")"
  TIMEOUT="${LOGIN_TIMEOUT}"
  {
    echo "[$(date -Is)] START scholarship-outlook-agent mode=login model=${MODEL_ID} session=${SESSION_ID}"
    run_agent "${TIMEOUT}" "${MESSAGE}"
    echo "[$(date -Is)] DONE scholarship-outlook-agent mode=login"
  } >>"${RUN_LOG}" 2>&1
  echo "Outlook login page should be open in the browser."
  echo "Complete Microsoft sign-in and 2FA manually, then run:"
  echo "  ./scripts/run-openclaw-scholarship-email-agent.sh download"
  echo "Log: ${RUN_LOG}"
  exit 0
fi

if [[ ! -f "${PROMPT_FILE}" ]]; then
  echo "Prompt file not found: ${PROMPT_FILE}" >&2
  exit 1
fi

BASE_MESSAGE="$(<"${PROMPT_FILE}")"

if [[ "${MODE}" == "dry" ]]; then
  MODE_MESSAGE=$'\n\nRuntime mode: DRY_RUN\nAssume the user already logged into Outlook manually. Search and list matching scholarship messages only. Do NOT download files. Write a preview list to '"${AGENT_DIR}/dry-run-preview.json"' as a JSON array with subject/from/date/searchQuery for each match, then stop.'
elif [[ "${MODE}" == "download" ]]; then
  MODE_MESSAGE=$'\n\nRuntime mode: DOWNLOAD\nAssume the user already logged into Outlook manually. Download every NEW matching scholarship message up to '"${MAX_EMAILS}"$' messages this run. Update manifest files after each download.'
else
  echo "Unsupported mode: ${MODE}. Use: login | dry | download" >&2
  exit 1
fi

MESSAGE="${BASE_MESSAGE}${MODE_MESSAGE}"
TIMEOUT="${AGENT_TIMEOUT}"

{
  echo "[$(date -Is)] START scholarship-outlook-agent mode=${MODE} max_emails=${MAX_EMAILS} model=${MODEL_ID} session=${SESSION_ID}"
  run_agent "${TIMEOUT}" "${MESSAGE}"
  echo "[$(date -Is)] DONE scholarship-outlook-agent mode=${MODE}"
} >>"${RUN_LOG}" 2>&1

echo "Run complete. Log: ${RUN_LOG}"
