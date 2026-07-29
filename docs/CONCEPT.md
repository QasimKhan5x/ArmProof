# Project Concept

## One Sentence

KleidiScope shows exactly how a GGUF model maps onto KleidiAI kernels on a
specific Arm CPU, explains costly fallbacks, and generates measured
hardware-aware mixed-quantization candidates under an explicit quality budget.

## The Developer Problem

An Arm developer can compile `llama.cpp` with KleidiAI and see that the backend
loaded. That does not answer whether the important parts of the selected model
use optimized kernels. When performance is disappointing, the developer must
piece together:

- runtime logs;
- model tensor names and quantization formats;
- GGML operator construction;
- KleidiAI dispatch conditions;
- CPU ISA features;
- profiler call stacks; and
- manual quantization experiments.

The result is slow, architecture-specific investigation with little reusable
evidence. Standard quantization presets optimize general size/quality
tradeoffs. Current upstream target-BPW optimization improves estimated quality
for a size target. Neither is designed to explain or optimize the measured
KleidiAI coverage and end-to-end performance of a particular model/workload on
a particular Arm server.

## Product Experience

A developer provides:

- an F16/BF16 source GGUF;
- a representative prompt/decode or server workload;
- a quality-loss budget;
- a size or performance objective; and
- an Arm64 target running a pinned `llama.cpp` build.

KleidiScope then:

1. inventories CPU features and runtime/build identity;
2. records structured operator, tensor, backend, and dispatch evidence;
3. ranks runtime-significant accelerated paths and fallbacks;
4. explains each fallback from pinned source rules rather than model guesses;
5. proposes a small bounded set of per-tensor type substitutions;
6. invokes upstream quantization mechanisms to create candidate GGUFs;
7. evaluates quality, size, RSS, prompt/decode speed, and server behavior;
8. compares candidates with all required baselines; and
9. exports the model, recipe, trace, raw measurements, manifest, and report.

## Distinctive Mechanism

The mechanism is **coverage-guided, hardware-constrained mixed
quantization**:

- Quality sensitivity determines which tensors cannot safely lose precision.
- KleidiAI eligibility determines which formats have optimized implementations
  on the detected ISA.
- Runtime weight determines which eligible changes are worth testing.
- A bounded candidate policy prevents an unreviewable parameter sweep.
- Measured evaluation, not static prediction, selects the final candidate.

KleidiScope does not need to invent a new quantization encoding. It uses
existing GGUF formats and upstream quantization primitives while contributing
the observability, Arm-specific decision policy, evidence model, automation,
and developer workflow.

## Primary User

An inference engineer, ML systems developer, framework contributor, or Arm
cloud adopter who needs to answer:

> Why is this model not obtaining the expected Arm acceleration, and what
> measured artifact should I deploy instead?

Secondary users include KleidiAI/llama.cpp contributors diagnosing coverage,
CI owners guarding against acceleration regressions, educators explaining
operator-to-kernel execution, and model publishers producing Arm-qualified
GGUF variants.

## What Ships

- A CLI and Python library with stable JSON contracts.
- A minimal, pinned, upstream-reviewable tracing integration.
- A source-grounded eligibility/fallback rule inventory.
- Hardware-aware recipe generation and upstream quantizer invocation.
- Benchmark and quality adapters with controlled repeated runs.
- An interactive X-ray report backed by downloadable raw evidence.
- CI coverage regression checks.
- At least one optimized GGUF, recipe, checksum, manifest, and walkthrough.

## Non-Goals

- Training or fine-tuning models.
- Creating a new quantization encoding.
- Generating new microkernels during the hackathon.
- GPU inference or GPU comparisons as the main result.
- A general-purpose inference scheduler.
- Hosted multi-tenant SaaS.
- Universal claims across all models and Arm processors.
- Requantizing low-bit models as primary evidence.

## Honest Claim Boundary

The acceptable claim form is:

> On model M, workload W, pinned runtime R, and Arm target H, KleidiScope
> generated candidate C. Against baselines B under protocol P, C changed metric
> X by Y while quality metric Q remained within budget Z.

The unacceptable claim form is:

> KleidiScope always finds the optimal Arm quantization or universally speeds
> up LLM inference.

