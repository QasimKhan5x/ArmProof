# Benchmark And Evidence Protocol

## Purpose

This protocol governs performance and quality claims. Unit tests may validate
code but cannot create headline benchmark evidence.

## Pre-Registration

Before a paid or headline run, freeze:

- hypothesis and causal scope;
- model, runtime, artifacts and hashes;
- instance, image, OS and CPU settings;
- workload IDs and traffic mixes;
- treatment commands and environment;
- warm-up and measurement windows;
- metrics, quality tolerance and thresholds;
- repetition count, exclusions and statistics;
- runtime, cost cap and cleanup.

Post-result threshold changes require a new experiment ID.

## Required Comparisons

### Whole Deployment Transformation

PyTorch BF16 versus ONNX Runtime GenAI INT4. This comparison may support size,
memory, quality and whole-stack deployment claims. It does not isolate
KleidiAI.

### Arm Acceleration

Identical ONNX Runtime GenAI INT4 service with KleidiAI disabled versus
enabled. Only the documented enable/disable control may differ. This comparison
supports KleidiAI-attributable performance claims.

### Cloud Consequence

For each INT4 treatment, measure the highest confirmed tested accepted throughput under
the same p95 SLO. Use short, long and mixed prompt traffic.

### Runtime Memory Follow-Up

Keep the accepted KleidiAI treatment active and test runtime-memory changes at
one fixed stress rate. First isolate transparent huge pages, allocator preload,
and any runtime thread overrides. Challenge a simpler candidate in at least five
sustained windows; release it only if every long window passes, otherwise retain
the fully sustained recipe. Preserve output digests and restore the host page
policy after collection. This comparison may
support a Graviton whole-runtime result; it must not be relabeled as a
KleidiAI-only or Arm-ISA-only effect.

## Measurement Rules

- Synchronize process readiness before warm-up.
- Use at least five independent post-warm-up repetitions for accepted serving
  claims.
- Preserve request-level samples and errors.
- Report p50, p95, p99, accepted RPS and error rate.
- Sample RSS/PSS throughout load and quality execution.
- Run profiler attribution separately from primary load measurements.
- For the reference release, capture matched Arm Performix profiles for both
  treatments with identical recipes, workload, duration and target. Only the
  documented KleidiAI control may differ.
- Record throttling, interruption, timeout and partial-run status.
- Record the allocator observed in `/proc/self/maps` and selected transparent
  huge-page policy before, during, and after runtime-memory treatments.
- Never drop a sample solely because it is unfavorable.

## Quality

- Freeze a public, licensed workload and IDs before the accepted run.
- Evaluate at least 500 labeled requests for the final reference claim, with
  1,000 preferred.
- Compare absolute task metrics and treatment non-inferiority.
- Count parse/schema failures explicitly.
- Required final tolerance: no more than one percentage point loss and at
  least 99% schema-valid output.
- Describe the result as workload-specific.

## Statistics

Report raw repetitions, median and a 95% confidence interval or bootstrap
interval. The fixed-SLO capacity result passes when:

- at least two of three traffic mixes show at least 1.5x throughput;
- the preferred headline target is 1.7x; and
- the lower confidence bound remains above 1.15x.

If noise prevents a decision, report `inconclusive` and rerun only under a new
recorded experiment attempt.

## Arm Attribution

Accepted enabled evidence must contain executed `kai_*` callchains and the
matched disabled control must contain none. The reference release requires two
independent profiler layers:

1. Linux `perf` preserves the already accepted cycle-share attribution.
2. Arm Performix Code Hotspots repeats the positive/negative callchain test,
   derives measured `kai_*` function-sample shares from native exports, and
   must independently agree with Linux `perf` within the preregistered five
   percentage-point tolerance.

CPU Microarchitecture and Instruction Mix are capability-gated because they
require at least three exposed PMU counters. On the measured `c8g.4xlarge`,
Performix reported two; those recipes are explicitly unavailable and their
readiness failures are preserved. They are not silently treated as passing or
made prerequisites for a claim they cannot measure. System Utilization is not
part of the accepted causal claim.

Performix runs must be exported in their native format with run IDs, recipe
versions, commands, target facts and SHA-256 hashes. If Performix is unavailable,
the reference Arm attribution remains `unknown`, not `pass`. If Performix and
Linux `perf` disagree, publication stops pending a new preregistered experiment.
Exact microkernel identity is reported only when directly observable;
family-level evidence must not be relabeled as an exact kernel.

## Overhead

Measure ArmProof's normal collection overhead against the same service without
collection. It must remain below 5%. Explicit profiler runs are excluded but
must be labeled as intrusive.

## Evidence Bundle

Every accepted run stores contract, environment, hashes, commands, logs, raw
request samples, memory samples, quality rows, Linux profiler output, native
Performix exports, normalized profiler evidence, claim ledger, spend record and
cleanup record.
