#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AGENT_DIR="${ROOT_DIR}/scholarship-agent"
PROMPT_FILE="${AGENT_DIR}/openclaw_scholarship_research_prompt.txt"
OUTPUT_FILE="${AGENT_DIR}/scholarship-catalog.md"
LOG_DIR="${AGENT_DIR}/logs"
AGENT_TIMEOUT="${OPENCLAW_AGENT_TIMEOUT:-7200}"
SESSION_ID="${OPENCLAW_SESSION_ID:-scholarship-research-$(date +%Y%m%d-%H%M%S)}"
MODEL_ID="${OPENCLAW_MODEL_ID:-deepseek/deepseek-chat}"

if [[ ! -f "${PROMPT_FILE}" ]]; then
  echo "Prompt file not found: ${PROMPT_FILE}" >&2
  exit 1
fi

mkdir -p "${LOG_DIR}"
RUN_LOG="${LOG_DIR}/openclaw-scholarship-research-$(date +%F).log"
MESSAGE="$(<"${PROMPT_FILE}")"

export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
if [[ -s "${NVM_DIR}/nvm.sh" ]]; then
  # shellcheck disable=SC1090
  . "${NVM_DIR}/nvm.sh"
fi

{
  echo "[$(date -Is)] START scholarship-research model=${MODEL_ID} session=${SESSION_ID}"
  openclaw agent \
    --session-id "${SESSION_ID}" \
    --model "${MODEL_ID}" \
    --thinking off \
    --timeout "${AGENT_TIMEOUT}" \
    --message "${MESSAGE}" \
    --json
  echo "[$(date -Is)] DONE scholarship-research"
} >>"${RUN_LOG}" 2>&1

if [[ -f "${OUTPUT_FILE}" ]]; then
  echo "Catalog written: ${OUTPUT_FILE}"
  wc -l "${OUTPUT_FILE}"
else
  echo "Warning: ${OUTPUT_FILE} not found. Check log: ${RUN_LOG}" >&2
  exit 1
fi

echo "Log: ${RUN_LOG}"
