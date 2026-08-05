# Arm Performix Confirmation

Arm Performix is a required input to the SurgeDesk release. It answers one
question: when the KleidiAI setting changes, did the optimized process actually
execute KleidiAI functions on Graviton4?

## Frozen Experiment

[`EXP-2026-013`](../ops/experiments/EXP-2026-013.json) is bound to a Git commit
whose time precedes the AWS launch time recorded in the experiment metadata.
This is inspectable chronology, not independent AWS attestation. The plan fixes:

- AWS Graviton4 `c8g.4xlarge`, 16 Neoverse V2 cores;
- Arm Performix 1.20 Code Hotspots at normal sampling;
- the pinned Phi-4 Mini INT4 and ONNX Runtime GenAI Arm64 build;
- the BANKING77 mixed workload repeated three times;
- `mlas.disable_kleidiai=1` for the control and `0` for the treatment;
- zero `kai_*` function samples in the control;
- at least 50% `kai_*` function-sample share in the treatment; and
- at least 100,000 total function samples in each profile.

The native exports, run-ID map, captured treatment configs, runtime lock,
machine identity and environment are stored under
[`ops/evidence/EXP-2026-013`](../ops/evidence/EXP-2026-013/).

## Release Verification

```bash
armproof ci examples/armproof-reference/armproof.json
```

The verifier requires the experiment copied into the archive to equal the
committed plan. It then:

1. checks the outer digest and every guest ledger entry;
2. binds each export to the captured disabled/enabled run-ID map;
3. checks the captured model configs differ only in the KleidiAI setting;
4. matches the executed commands with the preregistered commands;
5. requires the same CPU and Performix engine version;
6. reads function samples and symbols directly from each native export; and
7. evaluates the frozen control, treatment-share and sample-volume thresholds.

The release config contains archive locations and run IDs. The acceptance
thresholds are read from EXP-2026-013, so they cannot be lowered while packaging
the result.

## Linux Perf

The capacity archive also contains a separate Linux perf callchain profile.
Performix reports function samples; Linux perf reports sampled cycles. ArmProof
shows both measurements in their native units and does not compare their
percentages numerically.

## Cloud PMU Scope

Earlier exploratory work found that this Graviton VM exposed two virtual PMU
counters. Performix CPU Microarchitecture and Instruction Mix recipes required
at least three, so those recipes remain unavailable. EXP-2026-013 intentionally
preregistered only Code Hotspots, the supported recipe needed for the execution
claim. The earlier EXP-2026-010/011 records remain in the repository history.
