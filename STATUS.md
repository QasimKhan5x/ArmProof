# Current Status

Last updated: 2026-08-04

## Product

SurgeDesk is the judge-facing banking-support application. It routes recorded
BANKING77 requests through human confirmation, replays the accepted
same-instance Graviton surge, and hands off to ArmProof for causal release
proof. ArmProof remains the reusable fail-closed CI gate and evidence engine.

## Accepted Result

The decisive sustained audit ran on AWS Graviton4 `c8g.4xlarge`:

- Public fixed-SLO claim: at least 2.0x higher sustainable mixed traffic.
- Tested pass points: disabled 0.24 r/s and enabled 0.56 r/s, each passing all
  five 500-second confirmations; tested pass-point ratio 2.33x.
- Baseline 0.28 r/s failed all five windows, establishing the 2.0x lower bound.
- The original exact 2.5x bracket was rejected because enabled 0.60 r/s passed
  one of five windows. This rejected gate remains public.
- Quality delta: -0.390 percentage points accuracy and -0.673 points macro F1,
  both inside the preregistered one-point tolerance.
- Schema validity: 100% across the 770-item BANKING77 evaluation.
- Operational queue guard: 86.75% held-out five-destination accuracy (668/770), up
  12.34 percentage points from direct LLM intent-to-queue mapping.
- Arm attribution: 68.53% of sampled cycles reached the enabled KleidiAI I8MM
  callchain, versus 0% disabled, with zero lost samples.
- Whole deployment: 35.92% less disk, 55.34% lower peak PSS and 59.66% lower
  time-weighted PSS than the BF16 reference.
- Earlier short-window evidence reproduced on a fresh instance but is retained
  as supporting history, not the public sustained-capacity headline.

The public sustained result is derived from `EXP-2026-009`. That experiment is
marked rejected under its original exact-bracket gate; only its independently
supported conservative lower bound is released. All failed and inconclusive
attempts remain preserved and visible.

## Product State

Completed: guarded AWS lifecycle, reference service, fixed-SLO harness, policy
engine, pass/fail/unknown fixtures, single-config CLI, reusable GitHub Action,
responsive offline report, integrity verifier and pinned deployment artifact.

The reference release path verifies 282 files across the primary and
fresh-instance confirmation bundles, re-derives capacity and quality, binds model,
runtime, workload, environment and treatment identities to the contract, and
only then evaluates eight required claims. Caller-authored normalized
comparisons are rejected by `armproof ci`. The report emits a verification
receipt, and the safe tamper challenge proves one changed ledger digest blocks
before policy evaluation.

The SurgeDesk workflow now includes a held-out two-stage queue guard, human
confirm/correct state machine, equal-load customer-outcome replay, sustained
capacity lower bound, visible rejected overclaim, release-proof view,
executable adoption path and optional live Graviton gateway. A matched-request
demo races two prepared, core-isolated Graviton endpoints while explicitly
separating that live illustration from the sustained capacity evidence.
Recorded mode refuses to present edited text as inference; live mode remains
disabled unless a trusted endpoint is configured.

`armproof init` now scaffolds a runtime-neutral HTTP evidence project and
deliberately fails closed until real evidence is supplied. Its documented
clean-venv installation, generated files and missing-evidence failure were
executed end to end. A separate llama.cpp/Qwen2.5 0.5B Q4_0 bridge completed a
real local Arm64 inference smoke, proving protocol portability without
publishing an unmeasured performance claim.

Version `v0.5.1` is the intended release for the completed evidence, live-demo
and adoption paths.
Native Arm64, x86 and report-browser CI cover the Action, decision and offline
report. The complete
Devpost copy, judge guide, technical evidence map, media set, final checklist
and under-three-minute recording script are under `submission/`. Remaining
owner work is recording/uploading the video and pasting the prepared entry
into Devpost. The secondary measurement-overhead claim remains unpublished
until it has a matched baseline.

## Verified Commands

```bash
make check
armproof ci examples/armproof-reference/armproof.json
python3.12 scripts/demo_release_gate.py
armproof evidence-verify \
  --checksums ops/evidence/EXP-2026-004/accepted/evidence/SHA256SUMS \
  --root ops/evidence/EXP-2026-004/accepted/evidence
npm run test:ui
python3.12 scripts/demo_live_compare.py --help
.venv/bin/armproof init --endpoint http://127.0.0.1:8000/infer --output KIT
```

## Constraints

- Accepted performance claims are scoped to the pinned Phi-4 Mini workload,
  runtime and `c8g.4xlarge`; they are not universal model claims.
- Project source is MIT licensed; BANKING77 is attributed under CC-BY-4.0.
- Estimated cumulative AWS evidence cost is USD 10.7878 and inventory is empty.
- ArmProof means "verified against the declared contract," not Arm certified.
