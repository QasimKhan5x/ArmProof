# Arm Performix Core Experiment

ArmProof uses Arm Performix as a required causal check for its reference
Graviton release. It is not a screenshot, optional report import or future
integration.

## Question

When the only changed control is `mlas.disable_kleidiai`, does native profiling
observe KleidiAI work in the optimized process and none in the control?

## Matched Runs

- Machine: AWS Graviton4 `c8g.4xlarge`, 16 vCPUs, Neoverse V2.
- Profiler: Arm Performix CLI 1.20.0, Code Hotspots recipe.
- Runtime: the same pinned ONNX Runtime GenAI INT4 build.
- Workload: the same frozen BANKING77 mixed workload, repeated three times.
- Control: `mlas.disable_kleidiai=1`.
- Treatment: `mlas.disable_kleidiai=0`.

The commands, profiler version, CPU identity, run IDs and native exports are
inside [`EXP-2026-010`](../ops/evidence/EXP-2026-010/). The archive SHA-256 is:

```text
28d411e40de38f3ad4a455bbfa09524dee8b44d6e44eb4d3b599e01635789148
```

## Result

| Treatment | Measured function samples | `kai_*` samples | Share |
|---|---:|---:|---:|
| KleidiAI disabled | 947,888 | 0 | 0% |
| KleidiAI enabled | 368,119 | 246,698 | 67.02% |

The enabled export directly names the Neoverse I8MM matrix kernel family,
including
`kai_kernel_matmul_clamp_f32_qai8dxp4x8_qsi4c32p4x8_16x4x32_opt32_neon_i8mm`.

Linux perf separately attributed 68.53% of sampled cycles to the enabled
KleidiAI callchain. Performix function-sample share and Linux perf cycle share
have different denominators, so ArmProof does not call them the same metric.
Their absolute difference is 1.51 percentage points, inside the
preregistered five-point consistency limit.

## Fail-Closed Validation

The reference command performs these checks every time:

```bash
armproof ci examples/armproof-reference/armproof.json
```

It verifies the outer archive digest and all 35 guest checksums, opens the two
declared native ZIP exports, checks recipe success, CPU identity and matched
commands, then derives the sample totals. The release is invalid if:

- the archive or any bound file changes;
- either native export is missing;
- the run IDs, CPUs, profiler versions or commands do not match;
- the disabled run contains a measured `kai_*` sample;
- the enabled run contains no measured `kai_*` sample; or
- Performix disagrees with Linux perf beyond the frozen tolerance.

The normalized JSON is convenient for inspection but is not trusted by CI.

## Cloud PMU Limitation

Performix reported that this VM exposes two PMU counters. CPU
Microarchitecture and Instruction Mix each require at least three, so their
readiness checks are preserved as unavailable. This does not weaken the Code
Hotspots result: that recipe completed successfully in two matched sessions
and supplies the execution attribution required by the release contract.

No additional AWS run is needed to validate the checked-in evidence. The two
Performix sessions cost an estimated USD 0.1521 combined, and both final AWS
inventories were empty.
`EXP-2026-010` originally required a broader set of Performix recipes and was
rejected when the VM exposed too few PMU counters for all of them. ArmProof does
not relabel that experiment as accepted. The release gate consumes only the
completed, matched Code Hotspots control/treatment pair for the narrower claim
that the optimized service executed the KleidiAI path.
