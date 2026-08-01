# Experiment 2: Runtime Memory Validation

## Status

Predeclared before execution. This experiment does not alter Experiment 1,
which remains a measured 9/10 NO-GO under its frozen loaded-RSS gate.

## Question

Does Phi-4 Mini INT4 with KleidiAI reduce physical memory during real inference,
when memory is sampled continuously rather than once before lazy BF16 pages are
touched?

## Controls

- Same `c8g.4xlarge`, pinned models, wheels, prompts, shapes, thread count,
  warm-ups, deterministic decoding, and KleidiAI on/off control as Experiment 1.
- Restore the checksummed ARM64 ONNX Runtime and GenAI artifacts produced by
  Experiment 1. No native rebuild is permitted in the expected path.
- Sample `/proc/self/smaps_rollup` every 50 ms from before model construction
  until all performance and quality inference completes.

## Measurements

- Peak RSS and PSS.
- Time-weighted RSS and PSS.
- BF16 peak-PSS-to-model-bytes residency sanity ratio.
- Existing batch-1 and batch-4 throughput, quality, repetitions, and perf
  attribution checks.

## Frozen Gates

All gates must pass:

1. INT4 peak PSS is at least 35% lower than BF16.
2. INT4 time-weighted PSS is at least 35% lower than BF16.
3. BF16 peak PSS is at least 75% of its model directory bytes, demonstrating
   that the comparison touched a credible fraction of its weights.
4. INT4 remains at least 2x faster than BF16 on at least one frozen shape.
5. INT4 loses at most one of 24 answers and is at least 95% parseable.
6. Enabled perf output contains `kai_*`; disabled output does not.
7. Every mode retains at least three post-warm-up repetitions.

Failure is `NO_GO`. Results from Experiment 1 remain unchanged regardless of
this outcome.

## Cost Boundary

- One `c8g.4xlarge` in `us-east-1`.
- Maximum 50 minutes and `$0.5317` instance compute at `$0.63808/hour`.
- Encrypted 60 GiB gp3 volume deleted with the instance.
- Temporary private S3 assets and evidence deleted by the lifecycle runner.
