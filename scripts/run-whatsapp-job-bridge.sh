#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$ROOT_DIR/job-agent/logs"
mkdir -p "$LOG_DIR"

# Required/Recommended env vars:
# - WHATSAPP_ALLOWED_FROM="whatsapp:+852XXXXXXXX"
# - WHATSAPP_BRIDGE_SECRET="your-secret"
# - WHATSAPP_BRIDGE_HOST="0.0.0.0"
# - WHATSAPP_BRIDGE_PORT="8787"

exec python3 "$ROOT_DIR/scripts/whatsapp_job_bridge.py" >>"$LOG_DIR/whatsapp-bridge-server.log" 2>&1
