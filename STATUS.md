# Current Status

Last updated: 2026-08-04
## Product
SurgeDesk is the judge-facing banking-support application. It routes recorded
BANKING77 requests through human confirmation, can send a matched six-request
identity check to two verified Arm endpoints, and streams a fresh derivation
of the canonical sustained experiment. ArmProof remains the reusable
fail-closed CI gate and evidence engine.
## Accepted Result

The decisive sustained audit ran on AWS Graviton4 `c8g.4xlarge`:

- Public fixed-SLO claim: at least 2.0x higher sustainable mixed traffic.
- Stable passing points: disabled 0.24 r/s and enabled 0.56 r/s, each passing
  all five 500-second confirmations.
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
- Arm Performix 1.20 independently measured 67.02% `kai_*` function samples
  enabled versus 0% disabled. The 1.51 pp difference from Linux perf is inside
  the frozen 5 pp agreement limit.
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

The reference release path verifies 69 checksummed sustained-evidence files
and 35 native Arm Performix files. It re-derives 4,200 request outcomes,
quality, and matched Code Hotspots attribution; binds model, runtime, workload,
environment, and treatment identities to the contract; and then evaluates
nine required claims. Caller-authored normalized comparisons are rejected by
`armproof ci`. The report emits a verification receipt, and the safe tamper
challenge proves one changed ledger digest blocks before policy evaluation.

SurgeDesk includes a held-out queue guard, human confirmation, optional live
matched endpoints, a streamed sustained audit, the visible lower-bound
equation, causal profiler evidence, and a reusable starter-kit preview.
Recorded mode rejects edited text rather than presenting it as inference. The
gateway compares content-derived model identity, runtime, Arm architecture,
treatment control and CPU affinity before enabling the matched run, then
rechecks both health records and the response fingerprint on every request.
Identical endpoints and overlapping or unequal core groups are rejected.

`armproof init` scaffolds a runtime-neutral HTTP classification evidence
project and fails closed until real load rows, quality rows, identity sources, positive/negative
Arm profiles, and their checksum ledger are supplied. The `http-slo-v1`
adapter derives identities from source files, parses profiler samples, and
requires quality to pass before capacity. A llama.cpp/Qwen2.5 0.5B Q4_0 bridge
completed a local Arm64 compatibility smoke without a performance claim.

The c8g.4xlarge virtual PMU exposed two counters. Performix CPU
Microarchitecture and Instruction Mix each require at least three, so those
readiness failures remain public and unavailable rather than passing.

Version `v0.7.0` is the redesigned sustained-audit release.
Native Arm64, x86 and report-browser CI cover the Action, decision and offline
report. Submission copy and the under-three-minute script are under
`submission/`. Remaining owner work is recording/uploading the video and
pasting the prepared entry into Devpost. Capacity collection and profiler runs
remain separate; the project makes no measurement-overhead claim.

## Verified Commands

```bash
make check
armproof ci examples/armproof-reference/armproof.json
python3.12 scripts/demo_release_gate.py
shasum -a 256 ops/evidence/EXP-2026-009/evidence.tar.gz
shasum -a 256 ops/evidence/EXP-2026-010/evidence.tar.gz
npm run test:ui
python3.12 scripts/demo_live_compare.py --help
.venv/bin/armproof init --endpoint http://127.0.0.1:8000/infer --output KIT
```

## Constraints

- Accepted performance claims are scoped to the pinned Phi-4 Mini workload,
  runtime and `c8g.4xlarge`; they are not universal model claims.
- Project source is MIT licensed; BANKING77 is attributed under CC-BY-4.0.
- Estimated cumulative AWS evidence cost is USD 10.9399 and inventory is empty.
- ArmProof means "verified against the declared contract," not Arm certified.
