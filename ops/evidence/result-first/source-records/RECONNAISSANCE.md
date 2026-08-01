# Source Reconnaissance

## Survivors

### ONNX Runtime GenAI and Phi-4 Mini INT4

- Arm's current learning path deploys `microsoft/Phi-4-mini-instruct-onnx`
  INT4 with ONNX Runtime GenAI on Arm servers.
- ONNX Runtime's build enables KleidiAI unless `--no_kleidiai` is supplied.
- Current Q4 selection accepts Arm Neon DotProd or I8MM, not only SME/SME2.
  Graviton4 exposes both DotProd and I8MM.
- `mlas.disable_kleidiai=1` is a session option. It permits a same-binary,
  same-model, same-machine negative control.
- Kernel logging can name the selected KleidiAI routines.

## Exclusions

- **vLLM INT4:** Arm specifies at least 32 vCPUs and 64 GB RAM. This exceeds the
  approved 16-vCPU experiment target and would make the bake-off unfair.
- **SME2-only LiteRT/XNNPACK paths:** Graviton4 does not expose SME2.
- **llama.cpp/KleidiAI:** already resolved by the comprehensive KleidiScope
  experiments. Quantization is useful, but the tested KleidiAI differential and
  derived product mechanisms did not provide the required application headline.
- **Whisper BF16/core sharding:** resolved by CivicCaption. BF16 improved
  single-worker inference 15-17% and reduced process memory about 39%, but the
  proposed four-way sharding reduced throughput to 0.746x baseline.
- **Performix agent workflow:** Arm now publishes this workflow directly, so it
  is not a novel project opportunity.

## Pinned Inputs

- ONNX Runtime: `4c4d4923b4630a2d0b3807cbbbc3b1813b1380a5`
- ONNX Runtime GenAI: `d2c81fdc8ef80836ceba1bae384be80262e24bb4`
- Phi-4 Mini ONNX INT4: `fc04c8f93df696602fd9f300a30d1bf2e3081347`
- Phi-4 Mini BF16: `cfbefacb99257ffa30c83adab238a50856ac3083`
- KleidiAI fetched by ONNX Runtime: release `v1.20.0`

## Primary Sources

- https://learn.arm.com/learning-paths/servers-and-cloud-computing/onnx/setup/
- https://learn.arm.com/learning-paths/servers-and-cloud-computing/vllm-acceleration/
- https://github.com/microsoft/onnxruntime
- https://github.com/microsoft/onnxruntime-genai
- https://github.com/ARM-software/kleidiai
- https://huggingface.co/microsoft/Phi-4-mini-instruct-onnx
- https://huggingface.co/microsoft/Phi-4-mini-instruct

