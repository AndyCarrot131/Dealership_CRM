FROM ghcr.io/ggml-org/llama.cpp:server

EXPOSE 8080

# Model weights are mounted at /models (see docker-compose.llm.yml).
# Keep WORKDIR /app (base image default) so shared libraries resolve.
# Download first:
#   hf download Qwen/Qwen3-VL-4B-Instruct-GGUF \
#     Qwen3VL-4B-Instruct-Q4_K_M.gguf \
#     mmproj-Qwen3VL-4B-Instruct-Q8_0.gguf \
#     --local-dir local_model/qwen3-vl-4b

ENTRYPOINT ["/app/llama-server"]
CMD ["-m", "/models/Qwen3VL-4B-Instruct-Q4_K_M.gguf", \
     "--mmproj", "/models/mmproj-Qwen3VL-4B-Instruct-Q8_0.gguf", \
     "-c", "8192", \
     "--threads", "8", \
     "--port", "8080", \
     "--host", "0.0.0.0"]
