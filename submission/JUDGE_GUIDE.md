# Judge Guide

The project can be evaluated without AWS credentials, paid infrastructure or
model downloads. Accepted evidence, normalized decisions, a static report and
the product demo are checked into the public repository.

## 60-Second Path

1. Open https://qasimkhan5x.github.io/VerifyLane/surgedesk/#triage.
2. Choose **Guard intervention**, load the suggestion and inspect the direct
   LLM queue versus the guarded queue.
3. Open **Arm result**, inspect the accepted experiment identity and checksum
   status, then click **Load verified experiment**. The page derives same-load
   customer outcomes and the confirmed 3x tested capacity boundary from accepted
   events.
4. Open **Release proof**. Inspect the claim ledger, optimization path, exact
   deployment and reusable GitHub Action.

The public page is an evidence-backed application, not a live AWS dependency.
Recorded output is labeled. Edited text is rejected rather than presented as
model inference.

## Local Product

Prerequisite: Python 3.12.

```bash
git clone https://github.com/QasimKhan5x/VerifyLane.git
cd VerifyLane
python3.12 scripts/build_surgedesk_demo.py --verify
python3.12 scripts/serve_surgedesk.py --port 8765
```

Open http://127.0.0.1:8765/surgedesk/.

## Validate The Reusable Artifact

```bash
python3.12 -m pip install -e .
armproof ci examples/armproof-reference/armproof.json
```

Expected behavior:

- exit `0`;
- 282 files across the primary and fresh-instance confirmation bundles verify;
- seven required claims pass from a comparison derived by the adapter;
- an offline report and machine-readable decision are written; and
- the exact passing deployment remains linked to the decision.

To see a release blocked:

```bash
python3.12 scripts/demo_release_gate.py
```

The script alters only a temporary copy of one ledger digest. Expected output
is a valid eight-claim pass followed by a checksum block before policy runs.

## Full Test Suite

```bash
make check
npm ci
npx playwright install chromium
npm run test:logic
npm run test:ui
```

Public CI runs the core suite on native Arm64 and x86 and runs the product and
report browser workflows at desktop, tablet and mobile sizes.

## Rebuild The Graviton Reference

The full service is optional for judging because it requires the pinned model
and an Arm cloud machine. The reproducible recipe is documented in
[`examples/phi4-graviton/README.md`](../examples/phi4-graviton/README.md).
Runtime identities are pinned in `runtime-lock.json`; treatment overlays are
created by `scripts/prepare_phi4_variants.py`; `scripts/run_cap_001.py` runs
the frozen capacity protocol; and the passing deployment is captured in
`passing-deployment.json` plus `deploy/armproof-phi4.service`.

## Trust Boundary

ArmProof verifies declared claims for a pinned deployment. The authoritative
CI path is `ledgers + raw evidence -> derived comparison -> identity binding ->
policy`; a caller-authored normalized comparison cannot enter `armproof ci`.
It is not an Arm certification authority, and its repository checksums are not
independent attestation of the original evidence producer.
