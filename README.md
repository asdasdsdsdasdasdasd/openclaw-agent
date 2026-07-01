# openclaw-agent

OpenClaw automation agents for **Hong Kong job applications** and **scholarship email archiving**, plus an optional local LLM stack (vLLM / llama.cpp) if you want to run models on your own GPUs.

## What’s in this repo

| Agent | Directory | Purpose |
|---|---|---|
| **Job agent** | [`job-agent/`](job-agent/) | Search JobsDB, filter leads, submit tailored applications via browser |
| **Scholarship agent** | [`scholarship-agent/`](scholarship-agent/) | Search Outlook Web for scholarship mail and download messages locally |

Both agents use the [OpenClaw](https://github.com/openclaw/openclaw) CLI with browser automation. Production runs typically use **DeepSeek API** (`deepseek/deepseek-chat`) — no local GPU required for the agents themselves.

---

## Prerequisites

1. **OpenClaw** installed and on your PATH (`openclaw health` succeeds).
2. **Browser tool** enabled (`openclaw browser status`).
3. **DeepSeek API** configured in OpenClaw (or switch runner scripts to a local model — see [Local LLM stack](#local-llm-stack-optional) below).

```bash
export NVM_DIR="$HOME/.nvm" && . "$NVM_DIR/nvm.sh"   # if you use nvm
openclaw health
openclaw browser status
```

---

## First-time setup

Copy example configs and fill in your paths locally (these files are gitignored):

```bash
cp job-agent/config.example.json job-agent/config.json
cp scholarship-agent/config.example.json scholarship-agent/config.json
```

**Job agent** — edit `job-agent/config.json`:

- `allowedRecipients` / `targetRecipient` — where test applications go
- `attachments.cvPath` — path to your CV PDF
- Create `job-agent/candidate-profile.json` from [`profile.schema.json`](job-agent/profile.schema.json)

**Scholarship agent** — edit `scholarship-agent/config.json`:

- `outputDir`, `manifestFile` — where downloads and indexes are stored
- Adjust `searchQueries` / `matchKeywords` if needed

Never commit `.env`, SMTP passwords, `config.json`, or downloaded emails.

---

## Job agent

Automates JobsDB search → evaluate constraints → internal apply flow.

**Constraints** (see [`openclaw_autonomous_prompt.txt`](job-agent/openclaw_autonomous_prompt.txt)):

- Salary ≥ HKD 25,000, experience ≤ 1 year, skill overlap with your profile
- Fixed keyword cycle: `machine learning` → `ai engineer` → `llm developer`
- Rejections logged to `job-agent/rejected-leads.log.jsonl`

### Run

```bash
# Full autonomous run (search + apply)
./scripts/run-openclaw-autonomous-job-agent.sh

# Split pipeline: search/validate first, send from queue later
./scripts/run-openclaw-split-job-agent.sh

# Cron-friendly daily wrapper
./scripts/run-job-agent-daily.sh
```

More detail: [`job-agent/README.md`](job-agent/README.md)

---

## Scholarship agent

Two-step Outlook Web flow — **you** log in manually; the agent only searches and downloads.

### 1) Open login page (you complete Microsoft sign-in + 2FA)

```bash
./scripts/run-openclaw-scholarship-email-agent.sh login
```

Complete login in the browser, then:

### 2) Download scholarship messages

```bash
./scripts/run-openclaw-scholarship-email-agent.sh download
```

Output: `scholarship-agent/downloads/` with `body.txt`, `metadata.json`, and attachments per message.

### 3) Optional — research catalog from web + downloaded mail

```bash
./scripts/run-openclaw-scholarship-research.sh
```

Writes `scholarship-agent/scholarship-catalog.md`.

More detail: [`scholarship-agent/README.md`](scholarship-agent/README.md)

---

## Helper scripts

| Script | Description |
|---|---|
| `scripts/run-openclaw-autonomous-job-agent.sh` | End-to-end JobsDB job agent |
| `scripts/run-openclaw-split-job-agent.sh` | Search/validate then send-from-queue |
| `scripts/run-job-agent-daily.sh` | Daily job-agent cron entry |
| `scripts/run-openclaw-scholarship-email-agent.sh` | Outlook login + download |
| `scripts/run-openclaw-scholarship-research.sh` | Scholarship catalog research |
| `scripts/run-whatsapp-job-bridge.sh` | WhatsApp → job-agent bridge (optional) |

---

## Local LLM stack (optional)

This section is **only** if you want to serve Qwen locally via Docker instead of (or alongside) cloud APIs.

Runs **Qwen3.5-35B-A3B** (MoE, **GPTQ Int4** checkpoint `Qwen/Qwen3.5-35B-A3B-GPTQ-Int4`) on dual RTX 5070 Ti via vLLM. The base BF16 repo does **not** work with `--quantization gptq`.

### Hardware budget

| | Per GPU |
|---|---|
| Weights (INT4, TP=2) | ~8.75 GB |
| KV cache | ~6.4–7.25 GB |
| Total | 16 GB ✓ |

Only 3B parameters activate per token → inference speed close to a 3B dense model.

### CUDA 13 (new GPUs)

Very new NVIDIA GPUs (e.g. **RTX 50-series / Blackwell**) need a **CUDA 13** user-space stack inside the container. This project pins **`vllm/vllm-openai:latest-cu130`** (set in `.env` as `VLLM_IMAGE`).

### Prerequisites (Ubuntu)

```bash
sudo apt update
sudo apt install -y docker.io docker-compose-v2
sudo usermod -aG docker "$USER"   # then log out and back in
docker compose version
```

### Quick start

```bash
echo 'HF_TOKEN=hf_...' >> .env
docker compose up -d
docker compose logs -f vllm
curl http://localhost:8080/v1/models
```

### GGUF via llama.cpp (dual GPU)

Separate from vLLM. Build [llama.cpp](https://github.com/ggml-org/llama.cpp) with CUDA, download a Q4_K_M GGUF, then:

```bash
MODEL_PATH="/absolute/path/to/model.gguf" \
CTX_SIZE=8192 PORT=8081 TENSOR_SPLIT=0.45,0.55 N_GPU_LAYERS=99 \
./scripts/run-llamacpp-q4km.sh
```

Verify GPUs: `./scripts/check-gpu-usage.sh`

### API

OpenAI-compatible endpoint on port `8080`:

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8080/v1", api_key="openclaw")
resp = client.chat.completions.create(
    model="Qwen/Qwen3.5-35B-A3B-GPTQ-Int4",
    messages=[{"role": "user", "content": "Hello!"}],
)
print(resp.choices[0].message.content)
```

### Tuning (`.env`)

| Variable | Default | Notes |
|---|---|---|
| `MODEL_NAME` | `Qwen/Qwen3.5-35B-A3B-GPTQ-Int4` | Use **-GPTQ-Int4** with `gptq` |
| `MODEL_QUANTIZATION` | `gptq_marlin` | Recommended for Qwen GPTQ-Int4 |
| `MODEL_DTYPE` | `float16` | GPTQ does not accept `bfloat16` here |
| `MAX_MODEL_LEN` | `16384` | Raise to `32768` if GPU 0 has headroom |
| `GPU_MEMORY_UTILIZATION` | `0.88` | Lower if OOM |

### Filesystem isolation

The `app` container mounts **only this project directory** (`/workspace`). Root filesystem is read-only.

### Troubleshooting

| Symptom | Fix |
|---|---|
| `docker: unknown command: docker compose` | `sudo apt install -y docker-compose-v2` |
| `permission denied` on Docker socket | `sudo usermod -aG docker "$USER"` and re-login |
| GPU not visible in container | Install [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html) |
| `Cannot find the config file for gptq` | Use `MODEL_NAME=Qwen/Qwen3.5-35B-A3B-GPTQ-Int4` |
| GPTQ + bfloat16 error | Set `MODEL_QUANTIZATION=gptq_marlin`, `MODEL_DTYPE=float16` |

**NVIDIA Container Toolkit (Ubuntu)** — if `apt` cannot find the package, add NVIDIA’s repo:

```bash
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
  | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
  | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
  | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker && sudo systemctl restart docker
docker run --rm --gpus all nvidia/cuda:13.0.0-base-ubuntu22.04 nvidia-smi
```
