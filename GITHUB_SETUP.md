# GitHub setup for openclaw

## Security first

**Never paste passwords into chat or commit them to git.** If you did, change your Linux password immediately:

```bash
passwd
```

---

## 1. Install GitHub CLI (run in your terminal)

```bash
sudo apt update
sudo apt install -y gh
gh --version
```

## 2. Log in to GitHub

```bash
gh auth login
```

Choose:

- **GitHub.com**
- **HTTPS** (simplest) or SSH if you use keys
- Authenticate via **browser** or **token**

Verify:

```bash
gh auth status
```

## 3. Create the remote repository

Replace `YOUR_USER` with your GitHub username.

**Private repo (recommended):**

```bash
cd /mnt/d/openclaw
gh repo create openclaw --private --source=. --remote=origin --description "OpenClaw + HKJC football scrape pipeline"
```

**Or public:**

```bash
gh repo create openclaw --public --source=. --remote=origin
```

If the repo already exists on GitHub:

```bash
git remote add origin https://github.com/YOUR_USER/openclaw.git
```

## 4. First commit and push

```bash
cd /mnt/d/openclaw
git add .
git status   # review: no .env, no models/, no pipeline.db
git commit -m "Initial commit: HKJC scrape pipeline and openclaw stack"
git push -u origin main
```

## What is excluded (.gitignore)

| Excluded | Why |
|----------|-----|
| `.env` | secrets |
| `models/`, `llama.cpp/` | very large (16GB+) |
| `hkjc-football-agent/output/` | scrape data (~14MB+) |
| `hkjc-football-agent/data/pipeline.db` | local checkpoint |
| `node_modules/` | reinstall with `npm install` |

## Push only the HKJC pipeline (optional)

If you want a **smaller repo** with just the football scraper, create a new repo and push a subtree:

```bash
# example: separate repo hkjc-football-agent only — ask if you want this layout
```

## Troubleshooting

**`gh: command not found`** — complete step 1.

**`Permission denied (publickey)`** — use HTTPS: `gh auth login` → HTTPS.

**Push rejected (large files)** — run `git status` and ensure `models/` is not staged; check `.gitignore`.

**Nested git in llama.cpp** — `llama.cpp/` is gitignored; it stays a local clone only.

## Current status

- Git initialized: `git init -b main` ✓
- Remote: add with step 3
- `gh` auth: complete step 2 in your terminal (requires sudo password locally — not in chat)
