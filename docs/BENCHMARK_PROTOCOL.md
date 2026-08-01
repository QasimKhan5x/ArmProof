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

For each INT4 treatment, measure maximum sustainable accepted throughput under
the same p95 SLO. Use short, long and mixed prompt traffic.

## Measurement Rules

- Synchronize process readiness before warm-up.
- Use at least five independent post-warm-up repetitions for accepted serving
  claims.
- Preserve request-level samples and errors.
- Report p50, p95, p99, accepted RPS and error rate.
- Sample RSS/PSS throughout load and quality execution.
- Run profiler attribution separately from primary load measurements.
- Record throttling, interruption, timeout and partial-run status.
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

Accepted enabled evidence must contain executed `kai_*` callchains. The matched
disabled control must contain none. Exact microkernel identity is reported only
when directly observable; family-level evidence must not be relabeled as an
exact kernel.

## Overhead

Measure ArmProof's normal collection overhead against the same service without
collection. It must remain below 5%. Explicit profiler runs are excluded but
must be labeled as intrusive.

## Evidence Bundle

Every accepted run stores contract, environment, hashes, commands, logs, raw
request samples, memory samples, quality rows, profiler output, normalized
evidence, claim ledger, spend record and cleanup record.

