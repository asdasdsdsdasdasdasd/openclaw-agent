# openclaw-agent

Runs **Qwen3.5-35B-A3B** (MoE, **GPTQ Int4** checkpoint `Qwen/Qwen3.5-35B-A3B-GPTQ-Int4`) on dual RTX 5070 Ti via vLLM. The base BF16 repo does **not** work with `--quantization gptq`.

## Hardware budget

| | Per GPU |
|---|---|
| Weights (INT4, TP=2) | ~8.75 GB |
| KV cache | ~6.4–7.25 GB |
| Total | 16 GB ✓ |

Only 3B parameters activate per token → inference speed close to a 3B dense model.

## CUDA 13 (new GPUs)

Very new NVIDIA GPUs (e.g. **RTX 50-series / Blackwell**) need a **CUDA 13** user-space stack inside the container. The default `vllm/vllm-openai:latest` image may ship an older CUDA and fail at runtime.

This project pins **`vllm/vllm-openai:latest-cu130`** (set in `.env` as `VLLM_IMAGE`). Your host driver should report **CUDA 13.x** in `nvidia-smi` (e.g. 13.1); the container toolkit then mounts compatible user-space libs.

To override the image tag:

```bash
# .env
VLLM_IMAGE=vllm/vllm-openai:latest-cu130
```

## Prerequisites (Ubuntu)

`docker.io` alone does **not** include the Compose plugin. Install it:

```bash
sudo apt update
sudo apt install -y docker.io docker-compose-v2
sudo usermod -aG docker "$USER"   # then log out and back in (or newgrp docker)
docker compose version            # must print v2.x, not "unknown command"
```

If you also installed Docker via **snap**, pick **one** stack (apt **or** snap). Two installs can confuse which `docker` runs. For this project, **apt + docker-compose-v2** is enough.

## Quick start

```bash
# 1. Set your HuggingFace token (only needed once, for model download)
echo 'HF_TOKEN=hf_...' >> .env

# 2. Pull images and start everything
docker compose up -d

# 3. Watch vLLM load the model (~2-3 min first run)
docker compose logs -f vllm

# 4. Hit the API (OpenAI-compatible)
curl http://localhost:8080/v1/models
```

## GGUF (Q4_K_M) via llama.cpp (Dual GPU)

This path is separate from the `vLLM + GPTQ` setup above. Use it when you want to run a GGUF model such as `Q4_K_M`.

### 1) Build/install llama.cpp

```bash
git clone https://github.com/ggml-org/llama.cpp.git
cd llama.cpp
cmake -B build -DGGML_CUDA=ON
cmake --build build -j
```

Then point `LLAMA_SERVER_BIN` to the built binary:

```bash
export LLAMA_SERVER_BIN="$PWD/build/bin/llama-server"
```

### 2) Download a Q4_K_M model

Example model file (about 16.5-16.7 GB):

- `Qwen3.5-27B-Q4_K_M.gguf` from [unsloth/Qwen3.5-27B-GGUF](https://huggingface.co/unsloth/Qwen3.5-27B-GGUF)

### 3) Run dual-GPU server

From this project directory:

```bash
MODEL_PATH="/absolute/path/to/Qwen3.5-27B-Q4_K_M.gguf" \
CTX_SIZE=8192 \
PORT=8081 \
TENSOR_SPLIT=0.45,0.55 \
N_GPU_LAYERS=99 \
LLAMA_SERVER_BIN="${LLAMA_SERVER_BIN:-llama-server}" \
./scripts/run-llamacpp-q4km.sh
```

Notes:
- `TENSOR_SPLIT=0.45,0.55` gives GPU1 more model load to offset desktop VRAM usage on GPU0.
- Keep this server on `8081` so it does not collide with the existing app (`8080`).

### 4) Verify both GPUs are in use

In another terminal:

```bash
./scripts/check-gpu-usage.sh
curl http://127.0.0.1:8081/health
```

If your `llama-server` build does not expose `/health`, use:

```bash
curl http://127.0.0.1:8081/
```

### 5) OOM tuning

If GPU0 still OOMs:

1. Reduce GPU0 share (example: `TENSOR_SPLIT=0.40,0.60`).
2. Lower context size (`CTX_SIZE=4096`).
3. Close desktop/browser workloads using GPU0.
4. If still failing, lower `N_GPU_LAYERS` from `99` and allow more CPU offload.

## API

The openclaw app exposes an **OpenAI-compatible API** on port `8080`.
Point any OpenAI client at `http://localhost:8080/v1` with any API key.

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8080/v1", api_key="openclaw")
resp = client.chat.completions.create(
    model="Qwen/Qwen3.5-35B-A3B-GPTQ-Int4",
    messages=[{"role": "user", "content": "Hello!"}],
)
print(resp.choices[0].message.content)
```

## Tuning

Edit `.env` to adjust:

| Variable | Default | Notes |
|---|---|---|
| `MODEL_NAME` | `Qwen/Qwen3.5-35B-A3B-GPTQ-Int4` | Use the **-GPTQ-Int4** repo with `gptq`; not the base BF16 model |
| `MODEL_QUANTIZATION` | `gptq_marlin` | Use `gptq_marlin` for Qwen GPTQ-Int4 in vLLM |
| `MODEL_DTYPE` | `float16` | GPTQ in vLLM does not accept `bfloat16` here |
| `MAX_MODEL_LEN` | `16384` | Raise to `32768` if GPU 0 has no desktop |
| `GPU_MEMORY_UTILIZATION` | `0.88` | Lower if OOM |

## Filesystem isolation

The `app` container mounts **only this directory** (`/workspace`).
Root filesystem is `read_only: true`. No access to `/home`, `/etc`, or any other host path.

## Troubleshooting

| Symptom | Cause | Fix |
|--------|--------|-----|
| `docker: unknown command: docker compose` | Compose plugin not installed | `sudo apt install -y docker-compose-v2` |
| `unknown shorthand flag: 'd' in -d` | Same — `compose` is not a subcommand, CLI misparses `-d` | Install `docker-compose-v2`, then retry |
| `permission denied` on Docker socket | User not in `docker` group | `sudo usermod -aG docker "$USER"` and re-login |
| GPU not visible in container | NVIDIA Container Toolkit missing | Install [nvidia-container-toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html) and restart Docker |
| `nvidia-container-cli: ... libnvidia-ml.so.1: cannot open shared object file` | Toolkit not installed or Docker not wired to NVIDIA runtime | See **NVIDIA Container Toolkit (Ubuntu)** below |
| `Cannot find the config file for gptq` | Base `Qwen/Qwen3.5-35B-A3B` is BF16; vLLM needs a **GPTQ** model ID | Set `MODEL_NAME=Qwen/Qwen3.5-35B-A3B-GPTQ-Int4` (default in `.env`) |
| `torch.bfloat16 is not supported for quantization method gptq` | GPTQ path needs **float16**; vLLM recommends **gptq_marlin** for Int4 | Defaults: `MODEL_QUANTIZATION=gptq_marlin`, `MODEL_DTYPE=float16` |

### NVIDIA Container Toolkit (Ubuntu)

Ubuntu’s default repos **do not** ship `nvidia-container-toolkit`. If `apt` says **找不到套件** / “Unable to locate package”, add NVIDIA’s repo first:

```bash
# One-time: add NVIDIA Container Toolkit repository (Noble / 24.04)
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
  | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
  | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
  | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

Then verify the GPU is visible inside a container (CUDA **13** image matches new GPUs + driver 590+):

```bash
docker run --rm --gpus all nvidia/cuda:13.0.0-base-ubuntu22.04 nvidia-smi
```

If the image tag is not found on Docker Hub, pick any current `nvidia/cuda:*13*` `base` or `runtime` tag for your Ubuntu version.

If that prints GPU info, run `docker compose up -d` again in this project.

Official reference: [NVIDIA Container Toolkit install guide](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html).

## Automation agents

This repo bundles OpenClaw-driven automation alongside the LLM stack:

| Agent | Directory | Run scripts |
|---|---|---|
| **HK job search & applications** | [`job-agent/`](job-agent/) | `scripts/run-openclaw-autonomous-job-agent.sh`, `scripts/run-openclaw-split-job-agent.sh`, `scripts/run-job-agent-daily.sh` |
| **Scholarship email harvest** | [`scholarship-agent/`](scholarship-agent/) | `scripts/run-openclaw-scholarship-email-agent.sh`, `scripts/run-openclaw-scholarship-research.sh` |
| **HKJC football scrape pipeline** | [`hkjc-football-agent/`](hkjc-football-agent/) | `scripts/run-hkjc-pipeline-pool.sh` |

Each agent has its own README. Copy `config.example.json` → `config.json` and set paths/credentials locally (configs are gitignored).

**Secrets:** never commit `.env`, SMTP passwords, or downloaded emails. Runtime outputs (logs, manifests, scrape DB) stay local.
