# Judging Strategy And Required Proof

The judging criteria are product requirements. A polished explanation cannot
compensate for missing evidence.

## Technological Implementation - 40 Points

### What Must Be Visible

- A pinned, quality-engineered implementation rather than notebook glue.
- Real Arm64 execution on Graviton4.
- Verified KleidiAI kernel/dispatch evidence and explicit fallback reasons.
- Existing `llama.cpp` integration extended minimally and correctly.
- Hardware-aware quantization decisions followed by real candidate builds.
- Controlled speed, memory, size, quality, and server measurements.
- Tests for schemas, rules, policies, commands, and failure paths.
- Reproducible manifests and clean-room replay.

### High-Score Properties

- **Arm causality:** the system's recommendation changes with Arm ISA/kernel
  support and measured coverage.
- **Sound baselines:** it compares with standard presets and target-BPW, not a
  deliberately weak baseline.
- **Technical honesty:** unknown and inconclusive states remain visible.
- **Engineering quality:** tracing is bounded, contracts are versioned, and the
  upstream patch is reviewable.

### Failure Modes

- Merely building `llama.cpp` with KleidiAI.
- Generic parameter search with Arm branding.
- Reporting only average tokens/second without quality or uncertainty.
- Claiming kernel selection from startup logs alone.
- Treating a profiler visualization as the optimization itself.

## User/Developer Experience - 15 Points

### What Must Be Visible

- A small command sequence from model to evidence-backed candidate.
- Useful progress, errors, and typed unsupported states.
- A report whose first screen answers what changed and whether it won.
- Drill-down from model to operator, tensor, kernel, and source rule.
- Downloadable recipe, manifest, raw data, and reproduction command.
- Documentation for installation, first run, interpretation, extension, and CI.

### Reuse Test

A developer should be able to clone the repository, substitute their own GGUF
and workload, and obtain a defensible report without editing internal code.

## Potential Impact - 20 Points

### Reusable Contributions

- Structured KleidiAI dispatch trace schema.
- Minimal upstream tracing patch/integration.
- Versioned eligibility and fallback rules.
- Hardware-aware mixed-quant recipe format and generator.
- Candidate model plus reproducible recipe/checksum.
- Benchmark/evidence bundle schema.
- CI acceleration-coverage regression action or command.
- Arm optimization tutorial and worked example.

### Impact Narrative

KleidiScope shortens the path from "KleidiAI is enabled" to "this model is
measurably optimized and explainable on this Arm machine." It helps model
publishers, inference engineers, framework maintainers, and educators reuse the
same evidence instead of repeating source archaeology.

## WOW Factor - 25 Points

### The Visual Moment

The demo begins with a real model appearing as an execution X-ray:

- green paths reach named KleidiAI kernels;
- amber paths fall back with explicit reasons;
- width represents measured runtime significance;
- selecting a fallback reveals tensor type, shape, CPU requirement, source
  rule, and candidate remedy.

The user presses **Optimize**, sees only a bounded set of explainable candidates,
and then sees the winning model move onto a better size-quality-speed frontier.

### Why It Stands Out

- It makes invisible Arm optimization behavior inspectable.
- It connects low-level kernel dispatch to a deployable model artifact.
- It shows a causal before/after story, not disconnected benchmark bars.
- It is useful even when optimization fails because the fallback report and
  evidence bundle remain actionable.

## Optimization Checklist From The Challenge

| Challenge optimization | Required KleidiScope proof |
|---|---|
| Model size | Bytes, BPW, tensor-type distribution, RSS; matched quality comparison |
| Model quality | PPL/KLD or task metric versus F16/BF16 and size-matched baselines |
| Model speed | PP and TG tokens/sec, TTFT, repeated samples and uncertainty |
| Inference server speed | Fixed-concurrency throughput and p50/p95 latency |
| Developer experience | CLI, report, manifests, CI, docs, actionable failures |
| Arm-specific optimization | CPU features, kernel dispatch, fallbacks, KleidiAI-on/off and hardware-aware recipe |

KleidiScope need not win every metric simultaneously. It must demonstrate a
credible Pareto improvement while preserving quality, and explain why the
improvement is Arm-specific.

## Claims-To-Avoid

- "First hardware-aware quantizer" without a comprehensive novelty review.
- "Optimal" unless the search space and proof justify it.
- "Zero overhead" without measurement.
- "KleidiAI coverage" when only backend allocation is observed.
- "Production-ready" before clean-room reproduction and failure testing.
- "Faster than target-BPW" until measured at matched size and quality.

