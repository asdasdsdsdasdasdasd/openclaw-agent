# HK Job Agent

Current production flow uses OpenClaw + DeepSeek API to run JobsDB internal applications end-to-end.

## Current workflow (2026-06)

- Model: `deepseek/deepseek-chat` (API), no local model required for this path.
- Channel: JobsDB internal apply flow only (`.../apply`), no external SMTP send.
- Candidate facts source of truth: `job-agent/candidate-profile.json`.
- Rejection logs:
  - `job-agent/rejected-leads.log.jsonl` (JSONL append)
  - `job-agent/rejected-leads.json` (snapshot array)

## Required behavior

- Deterministic query cycle:
  1. `machine learning`
  2. `ai engineer`
  3. `llm developer`
  4. Repeat by page order
- Cover letter rules:
  - Tailored to each JD
  - Formal and external-facing
  - No fabricated facts
  - Must end with:
    `Note: This email is automatically generated and sent by openclaw.`

## Run commands

### 1) Health checks

```bash
export NVM_DIR="$HOME/.nvm" && . "$NVM_DIR/nvm.sh"
openclaw health
openclaw browser status
```

### 2) DeepSeek smoke test

```bash
openclaw agent \
  --session-id deepseek-api-smoke \
  --model deepseek/deepseek-chat \
  --thinking off \
  --timeout 120 \
  --message "Reply with exactly OK" \
  --json
```

### 3) One real JobsDB application

```bash
openclaw agent \
  --session-id jobsdb-apply-one \
  --model deepseek/deepseek-chat \
  --thinking off \
  --timeout 3600 \
  --message "Run one real JobsDB application now (exactly one successful submission)..." \
  --json
```

### 4) Batch run with AI-title bypass

```bash
openclaw agent \
  --session-id jobsdb-apply-batch50 \
  --model deepseek/deepseek-chat \
  --thinking off \
  --timeout 43200 \
  --message "Submit 50 applications. Bypass rule: if job title contains 'ai' (case-insensitive), submit directly unless blocked or cannot complete truthfully." \
  --json
```

## Performance quick fix

If web actions become slow and `openclaw health` shows high event loop delay/utilization:

1. Restart gateway:
   ```bash
   openclaw gateway restart
   ```
2. Relaunch Chromium CDP profile (attach mode):
   ```bash
   mkdir -p "$HOME/snap/chromium/common/openclaw-cdp"
   /snap/bin/chromium --remote-debugging-port=9222 \
     --user-data-dir="$HOME/snap/chromium/common/openclaw-cdp" \
     --no-first-run --no-default-browser-check
   ```
3. Re-check:
   ```bash
   openclaw browser status
   openclaw health
   ```
