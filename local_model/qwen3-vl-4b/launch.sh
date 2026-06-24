#!/bin/bash
# Qwen3-VL-4B-Instruct — llama-server launch
# Repo: Qwen/Qwen3-VL-4B-Instruct-GGUF
#
# Download first:
#   hf download Qwen/Qwen3-VL-4B-Instruct-GGUF \
#     Qwen3VL-4B-Instruct-Q4_K_M.gguf \
#     mmproj-Qwen3VL-4B-Instruct-Q8_0.gguf \
#     --local-dir .
#
# LLM quant options:
#   Qwen3VL-4B-Instruct-Q4_K_M.gguf  ~2.5 GB  ← recommended (M1 Pro)
#   Qwen3VL-4B-Instruct-Q8_0.gguf    ~4.2 GB
#   Qwen3VL-4B-Instruct-f16.gguf     ~8.0 GB
#
# mmproj options:
#   mmproj-Qwen3VL-4B-Instruct-Q8_0.gguf  smaller
#   mmproj-Qwen3VL-4B-Instruct-f16.gguf   higher vision quality

llama-server \
  -m  Qwen3VL-4B-Instruct-Q4_K_M.gguf \
  --mmproj mmproj-Qwen3VL-4B-Instruct-Q8_0.gguf \
  -c 8192 \
  -ngl 99 \
  --port 8080 \
  --host 127.0.0.1
