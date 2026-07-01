#!/usr/bin/env bash
set -euo pipefail

# Dual-GPU runner for GGUF Q4_K_M via llama.cpp.
# This path is separate from vLLM/GPTQ.

MODEL_PATH="${MODEL_PATH:-}"
CTX_SIZE="${CTX_SIZE:-32768}"
PORT="${PORT:-8081}"
TENSOR_SPLIT="${TENSOR_SPLIT:-0.45,0.55}"
N_GPU_LAYERS="${N_GPU_LAYERS:-99}"
LLAMA_SERVER_BIN="${LLAMA_SERVER_BIN:-llama-server}"

if [[ -z "${MODEL_PATH}" ]]; then
  echo "ERROR: MODEL_PATH is required."
  echo "Example:"
  echo "  MODEL_PATH=/path/to/Qwen3.5-27B-Q4_K_M.gguf $0"
  exit 1
fi

if [[ ! -f "${MODEL_PATH}" ]]; then
  echo "ERROR: MODEL_PATH does not exist: ${MODEL_PATH}"
  exit 1
fi

if ! command -v "${LLAMA_SERVER_BIN}" >/dev/null 2>&1; then
  echo "ERROR: llama-server not found."
  echo "Set LLAMA_SERVER_BIN to a valid binary path or add it to PATH."
  exit 1
fi

echo "[llama.cpp] starting dual-GPU server"
echo "  model:        ${MODEL_PATH}"
echo "  ctx_size:     ${CTX_SIZE}"
echo "  port:         ${PORT}"
echo "  tensor_split: ${TENSOR_SPLIT}"
echo "  n_gpu_layers: ${N_GPU_LAYERS}"
echo "  binary:       ${LLAMA_SERVER_BIN}"

exec "${LLAMA_SERVER_BIN}" \
  -m "${MODEL_PATH}" \
  -c "${CTX_SIZE}" \
  -ngl "${N_GPU_LAYERS}" \
  --tensor-split "${TENSOR_SPLIT}" \
  --host 127.0.0.1 \
  --port "${PORT}"
