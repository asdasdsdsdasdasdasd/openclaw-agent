# Scholarship Outlook Agent

Uses OpenClaw + DeepSeek API to search **Outlook Web** for scholarship-related messages and download them locally.

Login is **manual** (Microsoft sign-in + two-step verification). The agent never enters credentials.

## Current workflow (2026-06)

- Model: `deepseek/deepseek-chat` (API), no local model required.
- Channel: Outlook Web via browser tool (`outlook.office.com`), read-only (no send/delete).
- Two-step flow:
  1. **`login`** — agent opens Outlook login page; you sign in and complete 2FA yourself.
  2. **`download`** — after you are logged in, agent searches and downloads scholarship mail.
- Config: `scholarship-agent/config.json`
- Download output: `scholarship-agent/downloads/`
- Manifest:
  - `scholarship-agent/downloaded-emails.log.jsonl` (JSONL append)
  - `scholarship-agent/downloaded-emails.json` (snapshot array)

## Required behavior

- Deterministic search query cycle:
  1. `scholarship`
  2. `scholarships`
  3. `bursary`
  4. `fellowship`
  5. `grant application`
  6. `financial aid`
  7. `tuition waiver`
  8. `獎學金`
  9. `助學金`
  10. `獎助學金`
  11. Paginate each query until exhausted, then move to next query
- Match rule: subject, sender, or body contains any scholarship keyword (see `config.json`).
- Skip messages already recorded in the manifest.
- Per message, save under `downloads/YYYY-MM-DD_<subject>_<id>/`:
  - `body.txt`
  - `metadata.json`
  - `attachments/` (if any)
  - `message.eml` (when export is available)

## Run commands

### 1) Health checks + browser

```bash
export NVM_DIR="$HOME/.nvm" && . "$NVM_DIR/nvm.sh"
openclaw health
openclaw browser status
```

If browser is not attached, start Chromium CDP:

```bash
mkdir -p "$HOME/snap/chromium/common/openclaw-cdp"
/snap/bin/chromium --remote-debugging-port=9222 \
  --user-data-dir="$HOME/snap/chromium/common/openclaw-cdp" \
  --no-first-run --no-default-browser-check
```

### 2) Step A — open Outlook for manual login

```bash
./scripts/run-openclaw-scholarship-email-agent.sh login
```

The agent opens `https://outlook.office.com/mail/` in the browser and stops.

**You do:** sign in with your Microsoft account and complete two-step verification in that browser window.

Do **not** close the browser after login — the same session is reused for the download step.

### 3) Step B — download scholarship mail (after login)

```bash
./scripts/run-openclaw-scholarship-email-agent.sh download
```

If the session expired, run `login` again first.

### 4) Dry run (list matches, no download)

Run only after you are logged in:

```bash
./scripts/run-openclaw-scholarship-email-agent.sh dry
```

Preview output: `scholarship-agent/dry-run-preview.json`

### 5) Limit batch size

```bash
OPENCLAW_MAX_EMAILS=50 ./scripts/run-openclaw-scholarship-email-agent.sh download
```

### 6) DeepSeek smoke test

```bash
openclaw agent \
  --session-id deepseek-api-smoke \
  --model deepseek/deepseek-chat \
  --thinking off \
  --timeout 120 \
  --message "Reply with exactly OK" \
  --json
```

## Performance quick fix

If web actions become slow and `openclaw health` shows high event loop delay/utilization:

1. Restart gateway:
   ```bash
   openclaw gateway restart
   ```
2. Relaunch Chromium CDP (see command above).
3. Run `login` again if the Outlook session was lost.
4. Re-check:
   ```bash
   openclaw browser status
   openclaw health
   ```
