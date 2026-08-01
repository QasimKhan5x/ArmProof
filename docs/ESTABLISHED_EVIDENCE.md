# Established Evidence

This document records accepted findings that predate the ArmProof product
implementation. It is a routing summary, not a substitute for raw evidence.

## Environment

- AWS Graviton4 `c8g.4xlarge`, CPU-only.
- Phi-4 Mini.
- PyTorch BF16 reference.
- ONNX Runtime GenAI INT4 treatment.
- Identical INT4 model/runtime with `mlas.disable_kleidiai=1` as the Arm
  acceleration control.

## Accepted Results

| Claim | Comparison | Result |
|---|---|---:|
| Artifact size | INT4 versus BF16 | 35.92% smaller |
| Peak PSS | INT4 versus BF16 | 55.34% lower |
| Time-weighted PSS | INT4 versus BF16 | 59.66% lower |
| KleidiAI end-to-end speed | enabled versus disabled, same INT4 runtime | 1.72x to 2.59x |
| Quality | INT4 versus BF16 | 20/24 versus 19/24 |
| Parseability | both | 24/24 |
| Arm attribution | enabled/disabled perf callchains | `kai_*` only when enabled |
| Fixed-SLO capacity | KleidiAI enabled versus disabled | 3.0x short, 2.5x long, 3.0x mixed |
| Large-set quality | enabled versus disabled on 770 BANKING77 cases | -0.390 pp accuracy, -0.673 pp macro F1 |
| Schema validity | both normalized treatments | 100% |
| Clean reproduction | fresh `c8g.4xlarge` versus accepted result | 0% ratio difference in all mixes |

The four accepted KleidiAI speedups cover batch/prompt shapes `(1,128)`,
`(1,512)`, `(4,128)` and `(4,512)`.

## Historical Qualification

The first experiment failed its frozen loaded-RSS gate because pre-inference
BF16 RSS did not represent resident model pages. That experiment remains a
no-go under its original rules. A separately preregistered follow-up sampled
`/proc/self/smaps_rollup` throughout inference and passed all nine gates. The
follow-up does not rewrite the original result.

## Current Evidence Location

The imported size, memory and direct-speed evidence is under
`ops/evidence/result-first/`. The accepted service-capacity bundle is under
`ops/evidence/EXP-2026-004/accepted/`. Its guest ledger contains 141 entries;
`armproof evidence-verify` checks all of them after relocation. The independent
reproduction is under `ops/evidence/EXP-2026-005/accepted/` with its comparison
at `ops/evidence/EXP-2026-005/reproduction-comparison.json`.

## Not Yet Established

- ArmProof measurement overhead.

No document or report may present those as completed.
