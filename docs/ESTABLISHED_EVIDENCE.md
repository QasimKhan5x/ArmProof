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
| Sustained fixed-SLO capacity | KleidiAI enabled versus disabled, mixed traffic | at least 2.0x; 2.33x tested pass-point ratio |
| Large-set quality | enabled versus disabled on 770 BANKING77 cases | -0.390 pp accuracy, -0.673 pp macro F1 |
| Schema validity | both normalized treatments | 100% |
| Clean reproduction | fresh `c8g.4xlarge` versus accepted result | 0% ratio difference in all mixes |
| Operational queue quality | dependency-free guard on disjoint 770-case holdout | 86.75% (668/770) |
| Direct LLM queue mapping | recorded enabled outputs mapped to five destinations plus fallback | 74.42% (573/770) |

The four accepted KleidiAI speedups cover batch/prompt shapes `(1,128)`,
`(1,512)`, `(4,128)` and `(4,512)`.

The queue guard is product-layer evidence, not an Arm speedup. It uses word
unigrams/bigrams and multinomial Naive Bayes, trains on the remaining 30 test
examples per upstream class (2,310 total) and evaluates on the frozen first 10
per class used by ArmProof (770 total). The sets have no shared text.

## Historical Qualification

The first experiment failed its frozen loaded-RSS gate because pre-inference
BF16 RSS did not represent resident model pages. That experiment remains a
no-go under its original rules. A separately preregistered follow-up sampled
`/proc/self/smaps_rollup` throughout inference and passed all nine gates. The
follow-up does not rewrite the original result.

Short capacity studies `EXP-2026-004` and `EXP-2026-005` reported 2.5x-3.0x
tested grid ratios. The later 500-second audit `EXP-2026-009` supersedes those
numbers for public sustained-capacity claims. Its exact 2.5x bracket gate was
rejected, while five-of-five passes at 0.24 and 0.56 r/s plus five-of-five
baseline failures at 0.28 r/s establish the conservative at-least-2.0x result.

## Current Evidence Location

The imported size, memory and direct-speed evidence is under
`ops/evidence/result-first/`. The accepted service-capacity bundle is under
`ops/evidence/EXP-2026-004/accepted/`. Its guest ledger contains 141 entries;
`armproof evidence-verify` checks all of them after relocation. The independent
reproduction is under `ops/evidence/EXP-2026-005/accepted/` with its comparison
at `ops/evidence/EXP-2026-005/reproduction-comparison.json`.
The decisive sustained archive, failed original gate and conservative derived
claim are under `ops/evidence/EXP-2026-009/`.

## Not Yet Established

- ArmProof measurement overhead.

No document or report may present those as completed.
