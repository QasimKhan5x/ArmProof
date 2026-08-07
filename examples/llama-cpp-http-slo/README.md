# llama.cpp HTTP Adoption Example

This compact example demonstrates that ArmProof's bounded HTTP contract can
connect to a second runtime. It bridges llama.cpp's documented
OpenAI-compatible `/v1/chat/completions` endpoint to ArmProof's `/infer`
request shape.

It is a compatibility example, **not an optimization benchmark**. No latency,
throughput, quality or Arm-acceleration claim from this smoke may be compared
with the Graviton4 reference result.

## Run The Compatibility Smoke Test

Install `llama-server`, then start the official Apache-2.0 Qwen2.5 0.5B GGUF:

```bash
llama-server \
  -hf Qwen/Qwen2.5-0.5B-Instruct-GGUF:Q4_0 \
  --host 127.0.0.1 --port 8080 \
  --alias qwen-smoke -c 1024 -np 1 -t 4
```

Start the dependency-free bridge:

```bash
python3.12 examples/llama-cpp-http-slo/bridge.py \
  --llama-url http://127.0.0.1:8080/v1/chat/completions \
  --model qwen-smoke \
  --backend-label llama.cpp-qwen2.5-0.5b-q4_0 \
  --port 8000
```

Send one ArmProof-compatible request:

```bash
curl --fail --silent --show-error \
  -H 'Content-Type: application/json' \
  -d '{"request_id":"llama-smoke-1","prompt":"Reply briefly: ArmProof bridge works","max_new_tokens":16}' \
  http://127.0.0.1:8000/infer
```

Then scaffold the generic evidence workflow around that endpoint:

```bash
armproof init \
  --endpoint http://127.0.0.1:8000/infer \
  --output my-llama-armproof
```

The generated CI remains blocked until a developer supplies real baseline and
treatment evidence. See `smoke-receipt.json` for the checked compatibility run.

Sources: [llama.cpp server API](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md),
[official Qwen GGUF](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF).
