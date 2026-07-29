# Benchmark And Evidence Protocol

This protocol prevents benchmark tuning after results are known.

## Pre-Registration

Before a paid run, commit an experiment record containing:

- hypothesis and predicted direction;
- primary metric and quality budget;
- required baselines;
- fixed model/data/workload revisions;
- candidate policy and maximum candidate count;
- warmup and repeat counts;
- thread/affinity/context/batch/concurrency settings;
- acceptance, rejection, and inconclusive thresholds;
- maximum runtime and AWS cost.

Changes after observing results require a new experiment ID, not an edit to the
original hypothesis.

## Required Baselines

- F16/BF16 reference for quality.
- Standard Q4_K_M.
- Q4_0 or the most relevant uniform/standard KleidiAI-supported format.
- Upstream target-BPW candidate matched by actual BPW or bytes.
- KleidiAI disabled for causal implementation evidence where supported.
- KleidiScope candidate.

Add Q8_0 when useful for quality/speed shape. Do not add baselines solely to
make the candidate look favorable.

## Environment Controls

- One instance type and region per comparison table.
- Record CPU model/features, core topology, kernel, compiler, runtime revision,
  build flags, model hash, and data hashes.
- No unrelated workloads.
- Fixed thread count and affinity.
- Fixed context, prompt length, generation length, batch settings, and
  concurrency.
- Record CPU frequency/power controls where exposed.
- Download/build before timed trials.
- Do not mix Spot and On-Demand samples in one claim.

## Measurement Order

Use a deterministic randomized or counterbalanced order so thermal, cache, and
time trends do not always favor one candidate. Record the order. Separate:

- cold model load;
- warm prompt processing;
- warm token generation;
- server TTFT/latency/throughput; and
- trace-enabled profiling runs.

Tracing runs explain execution. Tracing-disabled runs determine headline
performance unless overhead is proven negligible.

## Repetition

Initial default, subject to pilot noise:

- at least 2 untimed warmups;
- at least 7 measured repetitions per microbenchmark condition;
- at least 3 server load-test windows per condition;
- report median, p25/p75 or MAD, and individual samples;
- p95 latency requires enough requests to make the percentile meaningful.

Do not discard outliers without a predeclared mechanical rule and retained raw
sample.

## Metrics

### Model

- exact bytes and GiB;
- bits per weight;
- tensor count/bytes by quantization type;
- loaded and peak RSS;
- quality delta versus reference.

### Runtime

- prompt-processing tokens/second;
- generation tokens/second;
- time to first token;
- end-to-end p50/p95 latency;
- requests/second at fixed concurrency;
- load time where relevant.

### Arm Coverage

- event-count accelerated coverage;
- tensor-byte-weighted coverage;
- observed-runtime-weighted coverage;
- unknown/unattributed share;
- fallback counts and weight by stable reason code;
- trace overhead.

### Economics

- instance-hour cost;
- experiment wall time;
- cost per completed evidence bundle;
- optional cost per million generated tokens based on measured sustained load,
  clearly labeled as an estimate.

## Quality Protocol

- Select the metric before candidate evaluation.
- Use the same tokenizer, context, dataset order, and sample count.
- Keep calibration/imatrix data separate from held-out acceptance data.
- Prefer perplexity/KLD for fast sensitivity screening and a small relevant
  task suite for final sanity.
- Report absolute and relative change.
- A candidate outside budget is rejected regardless of speed.

## Acceptance Logic

The primary feasibility threshold is defined in `FEASIBILITY_PLAN.md`.
Additionally:

- A result is **inconclusive** when uncertainty overlaps the acceptance margin
  or required evidence is missing.
- A candidate cannot pass by comparing different prompt lengths, thread counts,
  contexts, or precision references.
- A Pareto win must identify the controlled axes: equal quality, equal size,
  equal hardware, or equal service objective.
- Multiple-comparison fishing is prevented by the bounded candidate count.

## Evidence Bundle Minimum

- preregistration;
- environment manifest;
- exact commands and exit statuses;
- stdout/stderr logs;
- raw samples;
- trace and coverage files;
- model/recipe/data/tool checksums;
- quality outputs;
- decision output;
- AWS runtime/cost record;
- generated report data.

Screenshots and Markdown summaries are not raw evidence.

## Reproduction Standard

A clean instance must reproduce:

- successful build;
- model/candidate identity;
- qualitative dispatch mapping;
- acceptance decision; and
- headline metric direction within declared tolerance.

If exact absolute speed differs, report both runs and investigate rather than
replacing the less favorable run.

