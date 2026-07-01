#!/bin/bash
# vLLM entrypoint — dual RTX 5070 Ti (2 × 16 GB)
#
# Model: Qwen3.5-27B GPTQ Int4
# Memory per GPU (TP=2):
#   Weights (Int4): ~6.75 GB
#   KV cache:       ~6.0 GB  (GPU 0 shares ~2 GB with desktop display)
#   Total:          ~12.75 GB / 15.47 GB ✓

set -euo pipefail

MODEL="${MODEL_NAME:-Qwen/Qwen2.5-32B-Instruct-GPTQ-Int4}"
# gptq_marlin: vLLM's fast Marlin kernel for GPTQ Int4, avoids the buggy plain gptq path
QUANT="${MODEL_QUANTIZATION:-gptq_marlin}"
DTYPE="${MODEL_DTYPE:-float16}"
TP="${TENSOR_PARALLEL_SIZE:-2}"
MAX_LEN="${MAX_MODEL_LEN:-32768}"
GPU_MEM="${GPU_MEMORY_UTILIZATION:-0.90}"
if [[ "${MODEL}" == *.gguf ]]; then
  DEFAULT_SERVED_NAME="$(basename "${MODEL}")"
else
  DEFAULT_SERVED_NAME="${MODEL}"
fi
SERVED_MODEL_NAME="${SERVED_MODEL_NAME:-${DEFAULT_SERVED_NAME}}"

echo "[openclaw-vllm] Starting vLLM"
echo "  model:       ${MODEL}"
echo "  quantize:    ${QUANT}"
echo "  dtype:       ${DTYPE}"
echo "  tp-size:     ${TP}"
echo "  max-seq-len: ${MAX_LEN}"
echo "  gpu-mem:     ${GPU_MEM}"
echo "  served-name: ${SERVED_MODEL_NAME}"

# Official vLLM images expose `python3`; `python` is absent.
if [[ "${MODEL}" == *.gguf ]]; then
  exec python3 -m vllm.entrypoints.openai.api_server \
      --model "${MODEL}" \
      --served-model-name "${SERVED_MODEL_NAME}" \
      --tensor-parallel-size "${TP}" \
      --max-model-len "${MAX_LEN}" \
      --gpu-memory-utilization "${GPU_MEM}" \
      --trust-remote-code \
      --enforce-eager \
      --max-num-seqs 1 \
      --max-num-batched-tokens 512 \
      --limit-mm-per-prompt '{"image": 0}' \
      --enable-auto-tool-choice \
      --tool-call-parser hermes \
      --host 0.0.0.0 \
      --port 8000
fi

exec python3 -m vllm.entrypoints.openai.api_server \
    --model "${MODEL}" \
    --served-model-name "${SERVED_MODEL_NAME}" \
    --quantization "${QUANT}" \
    --tensor-parallel-size "${TP}" \
    --max-model-len "${MAX_LEN}" \
    --gpu-memory-utilization "${GPU_MEM}" \
    --dtype "${DTYPE}" \
    --trust-remote-code \
    --enforce-eager \
    --max-num-seqs 1 \
    --max-num-batched-tokens 512 \
    --limit-mm-per-prompt '{"image": 0}' \
    --enable-auto-tool-choice \
    --tool-call-parser hermes \
    --host 0.0.0.0 \
    --port 8000
