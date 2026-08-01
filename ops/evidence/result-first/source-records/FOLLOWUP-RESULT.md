# Experiment 2 Result: Runtime Memory Validation

Status: **GO - all 9 frozen gates passed**

Experiment 2 completed successfully on a Graviton4 `c8g.4xlarge`. It restored
the checksummed ARM64 runtime artifacts from Experiment 1 and performed no
native rebuild. Memory was sampled from `/proc/self/smaps_rollup` throughout
model loading, repeated inference, and quality evaluation.

## Memory

- INT4/KleidiAI peak PSS: `4,846,790,656` bytes.
- BF16 peak PSS: `10,851,862,528` bytes.
- Peak PSS reduction: `55.34%`.
- INT4/KleidiAI time-weighted PSS: `4,074,753,789` bytes.
- BF16 time-weighted PSS: `10,101,106,656` bytes.
- Time-weighted PSS reduction: `59.66%`.
- BF16 peak-PSS-to-model-bytes ratio: `1.41`, clearing the frozen `0.75`
  residency sanity threshold.

## Arm Optimization

Against the identical INT4 model and ONNX Runtime binary with
`mlas.disable_kleidiai=1`, KleidiAI produced these end-to-end speedups:

- Batch 1, prompt 128: `1.72x`.
- Batch 1, prompt 512: `2.13x`.
- Batch 4, prompt 128: `2.41x`.
- Batch 4, prompt 512: `2.59x`.

Enabled perf callchains contained executed `kai_*` routines. Disabled
callchains did not, preserving the causal Arm attribution.

## Size And Quality

- INT4 model directory was `35.92%` smaller than BF16.
- INT4 quality: `20/24`; BF16 quality: `19/24`.
- Both modes produced parseable answers for `24/24` tasks.
- Every shape retained at least three post-warm-up repetitions.

## Interpretation

Experiment 1 remains a 9/10 NO-GO under its original pre-inference loaded-RSS
gate. Experiment 2 does not rewrite that result. It independently demonstrates
that the earlier loaded-RSS reading was not representative of physical memory
during inference and validates the mechanism under predeclared runtime-memory
gates.

The optimization mechanism is now a product-level **GO**. Product design may
proceed around the reproducible Arm result, while avoiding the extreme
INT4-versus-PyTorch batch-1 speedup as a headline until a server-level baseline
is completed.
