# Validation Guide

The checked-in evidence can be evaluated without AWS credentials, paid
infrastructure or model downloads.

SurgeDesk is the banking-support reference application. ArmProof is its
reusable Arm optimization release gate.

## Product Walkthrough

1. Open <https://qasimkhan5x.github.io/ArmProof/surgedesk/#triage>.
2. Inspect one clearly labeled stored BANKING77 model response, choose the final
   support queue and route the ticket.
3. Open **Release evidence** and click **Open checked-in evidence**. The page shows
   the two rates chosen before the final test, five outcomes per service and
   the `0.56 / 0.28 = at least 2.0x` lower bound. The optimized rate is 2,016
   offered messages per hour on the same server.
4. Open **Traffic switch** to inspect the sustainable-capacity result, Arm Performix
   profile and identity-bound live traffic control. Expand technical details
   for the exploratory fixed-shape result, quality limits and GitHub Action.

The public page uses checked-in evidence. A connected deployment can execute
requests on matched Graviton services, recalculate the release decision from
the checked-in measurements, and promote the optimized route only after its
runtime identity matches the accepted evidence. The full ten-window benchmark
remains a separate documented recollection workflow.

## Recompute The Release

Prerequisite: Python 3.12.

```bash
git clone https://github.com/QasimKhan5x/ArmProof.git
cd ArmProof
python3.12 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/armproof ci examples/armproof-reference/armproof.json
```

Expected behavior:

- exit `0`;
- all capacity, raw quality and Arm Performix checksum entries verify;
- 2,100 traffic outcomes and 1,540 raw model outputs used for the separate
  quality comparison are re-evaluated;
- the two measured treatment identities bind to the confirmed contract;
- all ten required claims pass; and
- the command writes a machine-readable decision and offline report.

## Run SurgeDesk Locally

```bash
python3.12 scripts/build_surgedesk.py --verify
python3.12 scripts/serve_surgedesk.py --port 8765
```

Open <http://127.0.0.1:8765/surgedesk/>.

`build_surgedesk.py --verify` independently derives the JSON used by the
page and compares it byte for byte with the checked-in payload. The local
**Recompute release decision** action runs the same analysis again and displays
the newly recalculated result.

## Inspect The Arm Work

The shortest artifact path is:

```text
ops/experiments/EXP-2026-014.json       final capacity preregistration
examples/armproof-reference/preregistration-publication.json plan bytes and recorded chronology
ops/evidence/EXP-2026-014/              ten identity-bound 500-second windows
ops/experiments/EXP-2026-013.json       final Performix preregistration
ops/evidence/EXP-2026-013/              native Code Hotspots exports
examples/armproof-reference/            confirmed contract and release config
src/armproof/evidence/confirmed_audit.py raw capacity derivation
src/armproof/evidence/raw_quality.py     raw output quality derivation
src/armproof/evidence/performix.py       native Performix parser
src/armproof/evidence/adapters.py        reusable release adapter
```

The capacity comparison changes one declared runtime control,
`mlas.disable_kleidiai`. Model files, ONNX Runtime build, workload, 16 threads,
instance type and SLO remain fixed. Performix must observe zero `kai_*` samples
in the control and at least 50% in the treatment, with at least 100,000 function
samples per profile. `kai_*` names are functions supplied by KleidiAI. The
service-level objective (SLO) requires 95% of responses within ten seconds,
zero errors and at least 95% completion of scheduled traffic.

## Reuse The Gate

```bash
.venv/bin/armproof init \
  --endpoint http://127.0.0.1:8000/infer \
  --output /tmp/my-arm-service
.venv/bin/armproof ci /tmp/my-arm-service/armproof.json
```

The generated project contains no invented measurements and lists the raw
request, quality, profiler and identity evidence that must be collected. The
initial `ci` call demonstrates that the empty starter is blocked. After
collection, run `armproof seal /tmp/my-arm-service/armproof.json`; sealing
creates a ledger, while `ci` still rejects incomplete evidence.
External adapters are
discovered through Python entry points and listed with `armproof adapters`.

## Full Validation

```bash
make check
npm ci
npx playwright install chromium
npm run test:logic
npm run test:ui
```

The browser suite covers desktop, tablet and 320-pixel mobile layouts. The
backend suite includes a real localhost HTTP flow through control routing,
saved-evidence validation, deployment-identity comparison, promotion and
optimized routing.
The visible action is a route cutover between two already-running services.
The service verifies the pinned runtime-wheel ledger at startup, reads its
instance type from AWS IMDSv2, and checks every optimized response against the
release that authorized it.

## Evidence Boundary

ArmProof evaluates this repository's versioned contract. SHA-256 ledgers detect
changes after evidence collection, while the AWS environment capture and
profiler exports document the measured host. Arm certification remains outside
the tool's scope.
