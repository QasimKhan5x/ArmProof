# Result-First Bake-Off Result

Status: **EXPERIMENT 1 NO-GO; MECHANISM SUBSEQUENTLY VALIDATED BY EXPERIMENT 2**

The checkpointed Graviton4 run completed successfully on a `c8g.4xlarge`.
Inference, quality evaluation, repeated performance shapes, and sampled perf
callchains all completed. The experiment does not pass its frozen acceptance
suite because the loaded-RSS reduction gate failed.

## Strong measured results

- KleidiAI versus the same INT4 runtime with `mlas.disable_kleidiai=1`:
  `1.76x`, `2.18x`, `2.45x`, and `2.61x` end-to-end speedup across the four
  batch/prompt shapes.
- Decode speedup from KleidiAI: `1.25x` to `1.88x`.
- INT4 versus PyTorch BF16 end-to-end speedup: `3.16x` to `47.62x`, depending
  on shape. The extreme batch-1 numbers should not become a headline without
  an additional server-level baseline.
- Model directory size reduction: `35.92%`.
- Quality: INT4 scored `20/24`; BF16 scored `19/24`; both produced parseable
  answers for all 24 tasks.
- Attribution: enabled perf callchains contained KleidiAI `kai_*` routines;
  disabled callchains did not.
- Five repetitions were collected for each INT4 shape and three for BF16.

## Failed gate

The frozen gate required at least 35% lower loaded RSS for INT4. Instead:

- INT4/KleidiAI total RSS after model construction: `2,920,054,784` bytes.
- BF16 total RSS after model construction: `1,099,300,864` bytes.
- Reported reduction: `-165.63%`.

The BF16 value is not credible as full physical residency for approximately
7.7 GB of model weights. The harness samples RSS immediately after model
construction, before inference, so lazy or file-backed pages can make the two
runtimes incomparable. That explains why the metric is suspect; it does not
permit changing the frozen result to a pass.

## Reusable artifacts

The evidence contains checksummed ARM64 wheels for pinned ONNX Runtime 1.29
with KleidiAI and ONNX Runtime GenAI 0.15.0.dev0, plus the ORT SDK archive,
raw benchmark JSON, quality rows, perf data, and profiler reports.

## Decision

Do not claim that the full frozen experiment passed. The Arm speed mechanism is
strongly validated, but the product decision remains NO-GO under the original
rules. A separate, predeclared follow-up may test peak/runtime-weighted memory
and a server-level workload; it must be reported as a new experiment rather
than rewriting this result.

That predeclared follow-up has now completed and passed all 9 of its frozen
gates. See `FOLLOWUP-RESULT.md`. Experiment 1 remains unchanged, while the
overall optimization mechanism is now a product-level GO.

## Estimated AWS cost

Total observed c8g.4xlarge lifetime across setup and both completed experiments
is about 135 minutes, approximately `$1.43` of compute at `$0.63808/hour`, plus small
short-lived EBS charges. This is an estimate, not an AWS invoice.
