# Technical Evidence Map

This page maps each public result to the raw artifact and code that verifies it.
The README and screenshots are summaries; the release command derives
its decision again from the files below.

## Measured Environment

- AWS `c8g.4xlarge`: 16 Graviton4 Neoverse V2 cores, CPU only
- Phi-4 Mini INT4 served with the pinned ONNX Runtime GenAI Arm64 build
- 16 inference threads
- BANKING77 mixed request stream and 770-message quality set
- Response-time rule: p95 at or below 10 seconds, zero errors, at least 95%
  delivery of the offered request rate
- Control: `mlas.disable_kleidiai=1`
- Treatment: `mlas.disable_kleidiai=0`

The model files, runtime, workload, machine shape, thread count and response-time
rule are fixed across the control and treatment.

## Confirmatory Release Evidence

| Result | Frozen comparison | Required result | Authoritative artifacts |
|---|---|---:|---|
| Sustainable capacity | Five 500-second control windows at 0.28 requests/s; five treatment windows at 0.56 requests/s | Every control fails, every treatment passes; at least 2.0x lower bound | [`EXP-2026-014 plan`](../ops/experiments/EXP-2026-014.json), [`analysis lock`](../ops/experiments/EXP-2026-014-analysis.json), [`protocol`](../ops/aws/sustained-006/protocol.json), [`evidence`](../ops/evidence/EXP-2026-014/) |
| Capacity request volume | Ten frozen windows | 2,100 raw HTTP outcomes | EXP-2026-014 confirmation JSONL files and [`confirmed_audit.py`](../src/armproof/evidence/confirmed_audit.py) |
| Output quality | 770 original outputs from each treatment | Accuracy and macro-F1 loss no greater than one percentage point; at least 99% schema-valid | [`EXP-2026-003 raw quality evidence`](../ops/evidence/EXP-2026-003/attempt-002/evidence/capacity/quality-batch), its locked ledger, and [`raw_quality.py`](../src/armproof/evidence/raw_quality.py) |
| Arm execution | Matched Performix Code Hotspots profiles | No `kai_*` samples in control; at least 50% in treatment; at least 100,000 function samples per profile | [`EXP-2026-013 plan`](../ops/experiments/EXP-2026-013.json), [`evidence`](../ops/evidence/EXP-2026-013/), and [`performix.py`](../src/armproof/evidence/performix.py) |
| Release decision | Ten required claims | All ten pass | [`confirmed contract`](../examples/armproof-reference/confirmed-contract.json), [`release config`](../examples/armproof-reference/armproof.json), and [`confirmed adapter`](../src/armproof/evidence/adapters.py) |

The capacity and Performix plans match Git objects whose recorded times precede
the recorded AWS launch times. The adapter requires byte-for-byte copies of
those plans from the evidence archives. Capacity rates and profiler thresholds
are read from the plans, so the release config cannot lower them.
The capacity analysis starts latency at each scheduled send rather than at
worker dispatch and rejects completions after the 500-second window plus the
ten-second SLO drain. EXP-2026-014's plan and analysis lock match the Git object
and both returned archives. This is integrity and recorded chronology evidence,
not independent proof of when the commit became public or when AWS launched the
instance.

EXP-2026-012 matched the same frozen capacity outcomes but omitted the
`source_artifact_sha256` field later required by the hardened release analyzer.
That archive is rejected. EXP-2026-014 froze the exact response schema before
provisioning and changes no rate, workload, SLO, model
or runtime parameter; it repeats the confirmation with complete response-level
identity binding.

## Supporting Optimization Measurements

These measurements were established earlier and remain separate comparisons:

| Result | Comparison | Measured improvement | Artifact |
|---|---|---:|---|
| Direct inference | KleidiAI enabled versus disabled, same INT4 runtime | 1.72x to 2.59x across four batch/prompt shapes | [`EXP-2026-002 raw measurements`](../ops/evidence/result-first/EXP-2026-002/) and [`supporting evidence lock`](../examples/armproof-reference/supporting-evidence-lock.json) |
| Model files | Public INT4 deployment versus BF16 reference | 35.92% smaller | Same summary |
| Peak proportional set size | INT4 versus BF16 | 55.34% lower | Same summary |
| Time-weighted proportional set size | INT4 versus BF16 | 59.66% lower | Same summary |
| Operational routing | Queue guard versus direct LLM-to-queue mapping on a disjoint 770-message holdout | 86.75% accuracy, +12.34 percentage points | [`queue_guard.py`](../src/armproof/demo/queue_guard.py) and generated [`data.json`](../surgedesk/data.json) |

The INT4 footprint results describe the model migration. The two-times capacity
claim isolates the KleidiAI setting inside the already-quantized deployment.
The routing guard is a SurgeDesk product feature and is not attributed to Arm.
SurgeDesk recalculates the median from five raw repetitions for each fixed
shape. It calculates the size and PSS reductions from locked aggregate fields
in the BF16 and INT4 measurement files. The fixed-shape speed range is labeled
exploratory supporting evidence.

## What The Verifier Recomputes

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/armproof ci examples/armproof-reference/armproof.json
```

The command:

1. checks the locked outer archive digests and every internal ledger entry;
2. requires the archived EXP-2026-014 and EXP-2026-013 plans to equal the committed files;
3. verifies that all raw capacity rows use the two preregistered rates;
4. recalculates scheduled-to-finished latency and bounded completion for every capacity window;
5. reparses 1,540 original model outputs and recalculates quality;
6. checks the model, runtime, workload, Arm machine and treatment identity carried by every successful capacity response;
7. reads function samples and symbols from the native Performix exports;
8. keeps Performix function samples and Linux perf cycle samples in separate units;
9. recalculates model-size and memory percentages from locked aggregate fields,
   and fixed-shape medians from raw repetitions in four hash-locked files;
10. evaluates all ten required claims; and
11. writes `verification.json`, `comparison.json`, `decision.json`, `summary.json`
    and an offline HTML report.

Exit `0` approves the measured treatment. Exit `2` means at least one required
claim failed or remained unknown. Exit `1` means the evidence or configuration
was invalid.

## Evidence Scope

The SHA-256 ledgers detect changes after collection. They do not independently
attest who controlled the original AWS host. The evidence bundle therefore also
records the Arm machine, runtime lock, source-model fingerprint, workload,
treatment configs, response backend labels, native profiler exports and
preregistered plans. A publication record binds the exact EXP-2026-014 plan
bytes in the prelaunch project bundle and measurement archive to a Git object
in this checkout. The Git object time predates the recorded AWS launch time;
that launch time remains experiment metadata rather than independent cloud
attestation. The live service verifies the pinned runtime-wheel ledger and reads
the instance type from AWS IMDSv2. The gateway rechecks the model fingerprint,
source artifact, runtime lock, wheel ledger, runtime version, instance, Arm64
CPU placement, threads and treatment controls before switching its route and
again on every optimized response. Drift invalidates the release and restores
the control route.

Performix reports function-sample share. Linux perf reports sampled-cycle
attribution. ArmProof presents both but never compares the percentages as if
they used the same denominator.

Historical discovery and rejected experiments remain under [`ops/evidence`](../ops/evidence/)
and [`ops/experiments`](../ops/experiments/). They explain how the final rates
were selected; they cannot approve the current release.
