# Decisive Experiment

## Question

Does the official Phi-4 Mini INT4 stack produce a large, causally attributable
Arm optimization that is strong enough to design a practical community project
around it?

## Controlled Matrix

1. Phi-4 Mini BF16 with PyTorch/oneDNN on all 16 cores.
2. Phi-4 Mini ONNX INT4 with ONNX Runtime GenAI and KleidiAI enabled.
3. The identical ONNX model, runtime binary and settings with
   `mlas.disable_kleidiai=1`.

Every mode uses the same Graviton4 host, task prompts, deterministic decoding,
thread count, warm-up policy and batch shapes.

## Measurements

- Batch 1 and batch 4, prompt lengths 128 and 512, generation length 64.
- TTFT, end-to-end latency, output tokens/second and RSS.
- Model bytes on disk.
- Accuracy and output-format validity on the frozen 24-question probe.
- Sampled `perf` callchains containing named KleidiAI routines and a
  no-KleidiAI negative control.
- CPU model, ISA flags, revisions, commands and checksums.

## Hard Gates

All gates must pass:

1. KleidiAI improves INT4 decode or end-to-end throughput by at least 20% on at
   least three of four workload shapes, with no shape regressing more than 5%.
2. INT4 is at least 2x faster than BF16 at batch 1 or batch 4.
3. INT4 reduces both model bytes and resident memory by at least 35%.
4. INT4 loses no more than one correct answer out of 24 versus BF16 and emits a
   parseable answer for at least 95% of tasks.
5. Enabled callchains name executed KleidiAI Q4 routines; disabled callchains
   contain none.
6. Results include at least three measured repetitions after warm-up and all
   active AWS resources are deleted.

Failure is a typed `NO_GO`. The project may not be rescued by weakening these
gates after observing results.

## Cost Boundary

- Region: `us-east-1`
- Instance: one `c8g.4xlarge`
- Maximum runtime: 80 minutes
- Frozen rate: $0.63808/hour
- Maximum instance compute: $0.8508 before tax
- Storage: encrypted 60 GiB gp3, deleted with the instance
- Temporary private S3 staging, deleted by the lifecycle runner

The build and downloads are performed once. KleidiAI on/off uses one runtime
binary, avoiding a second ONNX Runtime build.
