#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROMPT_FILE="${ROOT_DIR}/job-agent/openclaw_autonomous_prompt.txt"
LOG_DIR="${ROOT_DIR}/job-agent/logs"
MODE="${1:-send}"
AGENT_TIMEOUT="${OPENCLAW_AGENT_TIMEOUT:-1200}"
SEND_COUNT="${OPENCLAW_SEND_COUNT:-5}"
RECIPIENT_MODE="${OPENCLAW_RECIPIENT_MODE:-test}"
SESSION_ID="${OPENCLAW_SESSION_ID:-jobsdb-autonomous-${MODE}-$(date +%Y%m%d-%H%M%S)}"
MODEL_ID="${OPENCLAW_MODEL_ID:-t@models/Qwen3.5-27B-Q4_K_M.gguf}"
if [[ "${MODEL_ID}" == "t@models/Qwen3.5-27B-Q4_K_M.gguf" ]]; then
  # OpenClaw 2026.5.22 model id parser rejects '@' and '/' alias syntax.
  # Map user-facing requested id to the configured provider model id.
  MODEL_ID="vllm/Qwen3.5-27B-Q4_K_M.gguf"
fi

if [[ ! -f "${PROMPT_FILE}" ]]; then
  echo "Prompt file not found: ${PROMPT_FILE}" >&2
  exit 1
fi

mkdir -p "${LOG_DIR}"
RUN_LOG="${LOG_DIR}/openclaw-autonomous-$(date +%F).log"

BASE_MESSAGE="$(<"${PROMPT_FILE}")"

if [[ "${MODE}" == "dry" ]]; then
  MODE_MESSAGE=$'\n\nRuntime mode: DRY_RUN\nDo NOT send any email. Write one tailored draft only and stop.'
elif [[ "${MODE}" == "send" ]]; then
  if [[ "${RECIPIENT_MODE}" == "real" ]]; then
    RECIPIENT_OVERRIDE=$'\nOverride recipient rule for this run: send to real company application contact found in each selected JD/company page. Do NOT send to the test inbox.'
  else
    RECIPIENT_OVERRIDE=""
  fi
  MODE_MESSAGE=$'\n\nRuntime mode: SEND\nOverride any earlier numeric target in this prompt: you must send exactly '"${SEND_COUNT}"$' emails via send-email skill and then stop.'"${RECIPIENT_OVERRIDE}"$'\nExecution policy for this run: do not output long progress narratives; execute tools directly and only stop after sending the required count or a hard error.'
else
  echo "Unsupported mode: ${MODE}. Use: dry | send" >&2
  exit 1
fi

MESSAGE="${BASE_MESSAGE}${MODE_MESSAGE}"

{
  echo "[$(date -Is)] START openclaw autonomous job-agent mode=${MODE} send_count=${SEND_COUNT} recipient_mode=${RECIPIENT_MODE}"
  openclaw agent \
    --session-id "${SESSION_ID}" \
    --model "${MODEL_ID}" \
    --thinking off \
    --timeout "${AGENT_TIMEOUT}" \
    --message "${MESSAGE}"
  echo "[$(date -Is)] DONE openclaw autonomous job-agent mode=${MODE}"
} >>"${RUN_LOG}" 2>&1
