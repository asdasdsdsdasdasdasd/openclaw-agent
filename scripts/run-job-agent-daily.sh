#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$ROOT_DIR/job-agent/logs"
LOCK_FILE="$ROOT_DIR/job-agent/.daily-run.lock"

mkdir -p "$LOG_DIR"

if ! command -v flock >/dev/null 2>&1; then
  echo "flock is required but not found." >&2
  exit 1
fi

exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  echo "Job agent daily task is already running, skip this run."
  exit 0
fi

LOG_FILE="$LOG_DIR/scheduler-$(date +%F).log"

{
  echo "[$(date -Is)] START daily job-agent run"
  echo "[$(date -Is)] Step 1/2: openclaw-agent dry-run"
  "$ROOT_DIR/scripts/run-openclaw-autonomous-job-agent.sh" dry
  echo "[$(date -Is)] Step 2/2: openclaw-agent send run"
  "$ROOT_DIR/scripts/run-openclaw-autonomous-job-agent.sh" send
  echo "[$(date -Is)] DONE daily job-agent run"
} >>"$LOG_FILE" 2>&1
