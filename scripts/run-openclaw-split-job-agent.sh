#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROMPT_FILE="${ROOT_DIR}/job-agent/openclaw_autonomous_prompt.txt"
QUEUE_FILE="${ROOT_DIR}/job-agent/send-queue.json"
LOG_DIR="${ROOT_DIR}/job-agent/logs"
SEND_COUNT="${OPENCLAW_SEND_COUNT:-2}"
RECIPIENT_MODE="${OPENCLAW_RECIPIENT_MODE:-real}" # real | test
MODEL_ID="${OPENCLAW_MODEL_ID:-vllm/Qwen3.5-27B-Q4_K_M.gguf}"
SEARCH_TIMEOUT="${OPENCLAW_SEARCH_TIMEOUT:-2400}"
SEND_TIMEOUT="${OPENCLAW_SEND_TIMEOUT:-1800}"
MIN_QUERY_COUNT="${OPENCLAW_MIN_QUERY_COUNT:-200}"
MAX_SEARCH_ATTEMPTS="${OPENCLAW_MAX_SEARCH_ATTEMPTS:-8}"
REJECT_LOG_FILE="${ROOT_DIR}/job-agent/rejected-leads.log.jsonl"
RUN_ID="$(date +%Y%m%d-%H%M%S)"
SEARCH_SESSION_ID="jobsdb-search-validate-${RUN_ID}"
SEND_SESSION_ID="jobsdb-send-from-queue-${RUN_ID}"

if [[ ! -f "${PROMPT_FILE}" ]]; then
  echo "Prompt file not found: ${PROMPT_FILE}" >&2
  exit 1
fi

mkdir -p "${LOG_DIR}"
RUN_LOG="${LOG_DIR}/openclaw-split-${RUN_ID}.log"
BASE_MESSAGE="$(<"${PROMPT_FILE}")"

if [[ "${RECIPIENT_MODE}" == "real" ]]; then
  RECIPIENT_RULE="Use real company application contact for each selected job."
else
  RECIPIENT_RULE="Override all recipients to ${OPENCLAW_TEST_RECIPIENT:-you@example.edu.hk}."
fi

SEARCH_MESSAGE="${BASE_MESSAGE}

Split pipeline stage: SEARCH_VALIDATE.
- DO NOT send any email in this stage.
- Find exactly ${SEND_COUNT} jobs that pass constraints.
- ${RECIPIENT_RULE}
- Hard minimum workload: evaluate and log at least ${MIN_QUERY_COUNT} jobs in rejected-leads.log.jsonl before finishing this stage.
- Do NOT stop early with a summary. If no suitable jobs, keep querying until the minimum workload is reached.
- Write ${QUEUE_FILE} as a JSON array with exactly ${SEND_COUNT} entries (or [] if none):
  [{\"recipient\":\"...\",\"company\":\"...\",\"role\":\"...\",\"url\":\"...\",\"subject\":\"...\",\"body\":\"...\",\"matched_constraints\":{\"salary\":\"...\",\"experience\":\"...\",\"skills\":\"...\"}}]
- Email body must be formal external-facing content only.
- Do NOT include internal sections such as Job Details, Matched Constraints table, reasoning logs, or markdown separators in body.
- Include note line at bottom of each body:
  Note: This email is automatically generated and sent by openclaw
- Keep rejected leads logging to rejected-leads.log.jsonl and rejected-leads.json."

SEND_MESSAGE="Split pipeline stage: SEND_FROM_QUEUE.
- Read queue file: ${QUEUE_FILE}
- Send exactly ${SEND_COUNT} emails using send-email skill from queue entries.
- ${RECIPIENT_RULE}
- If queue has fewer than ${SEND_COUNT}, send what exists and report shortage.
- After sending, print final sent_count and sent_jobs with role/company/url/recipient."

line_count() {
  local file="$1"
  if [[ -f "${file}" ]]; then
    wc -l < "${file}"
  else
    echo 0
  fi
}

queue_count() {
  python3 - <<'PY' "${QUEUE_FILE}"
import json, pathlib, sys
p = pathlib.Path(sys.argv[1])
if not p.exists():
    print(0)
    raise SystemExit
try:
    data = json.loads(p.read_text(encoding='utf-8'))
except Exception:
    print(0)
    raise SystemExit
print(len(data) if isinstance(data, list) else 0)
PY
}

{
  echo "[$(date -Is)] START split-pipeline send_count=${SEND_COUNT} recipient_mode=${RECIPIENT_MODE}"
  before_lines="$(line_count "${REJECT_LOG_FILE}")"
  REJECT_BACKUP="${LOG_DIR}/rejected-leads-backup-${RUN_ID}.log.jsonl"
  if [[ -f "${REJECT_LOG_FILE}" ]]; then
    cp "${REJECT_LOG_FILE}" "${REJECT_BACKUP}"
  else
    : > "${REJECT_BACKUP}"
  fi
  echo "[$(date -Is)] Stage 1/2 SEARCH_VALIDATE session=${SEARCH_SESSION_ID} min_query=${MIN_QUERY_COUNT} before_lines=${before_lines}"

  attempt=1
  while (( attempt <= MAX_SEARCH_ATTEMPTS )); do
    current_lines="$(line_count "${REJECT_LOG_FILE}")"
    delta_lines=$(( current_lines - before_lines ))
    remaining=$(( MIN_QUERY_COUNT - delta_lines ))
    if (( remaining <= 0 )); then
      break
    fi

    if (( attempt == 1 )); then
      search_prompt="${SEARCH_MESSAGE}"
    else
      search_prompt="Continue SEARCH_VALIDATE in the same session.
- Remaining minimum workload: log at least ${remaining} more rejected jobs.
- Do not summarize progress.
- Continue deterministic querying and append one JSON object per rejected job line."
    fi

    echo "[$(date -Is)] SEARCH attempt=${attempt} delta_lines=${delta_lines} remaining=${remaining}"
    openclaw agent \
      --session-id "${SEARCH_SESSION_ID}" \
      --model "${MODEL_ID}" \
      --thinking off \
      --timeout "${SEARCH_TIMEOUT}" \
      --message "${search_prompt}"

    after_lines="$(line_count "${REJECT_LOG_FILE}")"
    if (( after_lines < before_lines )); then
      echo "[$(date -Is)] DETECTED LOG CORRUPTION: line count shrank from baseline ${before_lines} to ${after_lines}. Restoring backup and aborting."
      cp "${REJECT_BACKUP}" "${REJECT_LOG_FILE}"
      exit 1
    fi
    new_delta=$(( after_lines - before_lines ))
    if (( new_delta <= delta_lines )); then
      echo "[$(date -Is)] SEARCH progress stalled at ${new_delta} lines; stopping retries."
      break
    fi
    attempt=$(( attempt + 1 ))
  done

  final_lines="$(line_count "${REJECT_LOG_FILE}")"
  final_delta=$(( final_lines - before_lines ))
  if (( final_delta < MIN_QUERY_COUNT )); then
    echo "[$(date -Is)] SEARCH_VALIDATE FAILED min workload not met: got=${final_delta} required=${MIN_QUERY_COUNT}"
    exit 1
  fi

  qcount="$(queue_count)"
  echo "[$(date -Is)] SEARCH_VALIDATE PASSED query_logs_added=${final_delta} queue_count=${qcount}"

  echo "[$(date -Is)] Stage 2/2 SEND_FROM_QUEUE session=${SEND_SESSION_ID}"
  openclaw agent \
    --session-id "${SEND_SESSION_ID}" \
    --model "${MODEL_ID}" \
    --thinking off \
    --timeout "${SEND_TIMEOUT}" \
    --message "${SEND_MESSAGE}"
  echo "[$(date -Is)] DONE split-pipeline"
} >>"${RUN_LOG}" 2>&1

