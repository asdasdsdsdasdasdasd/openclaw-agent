# GitHub setup

This repo is published from a **separate export copy** so your local working tree (personal configs, paths) stays untouched.

## Publish workflow

```bash
# 1. Copy from your local openclaw project (exclude secrets/runtime data)
rsync -a --exclude '.git' --exclude '.env' ... /path/to/openclaw/ ./openclaw-agent-publish/

# 2. Sanitize paths/emails in the publish copy only, then:
cd openclaw-agent-publish
git add -A
git commit -m "Update public release"
git push origin main
```

## Never commit

- `.env`, API tokens, SMTP passwords
- `job-agent/config.json`, `candidate-profile.json`
- `scholarship-agent/config.json`, `downloads/`
- Application logs, sent-email manifests

## Repo

- **Name:** `openclaw-agent`
- **Visibility:** public
- **URL:** https://github.com/asdasdsdsdasdasdasd/openclaw-agent
