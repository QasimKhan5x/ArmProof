# Judge Guide

The project can be evaluated without AWS credentials, paid infrastructure or
model downloads. Accepted evidence, normalized decisions, a static report and
the product demo are checked into the public repository.

## 60-Second Path

1. Open https://qasimkhan5x.github.io/ArmProof/surgedesk/#triage.
2. Load a support request, inspect the model and guarded queues, and confirm the
   route.
3. Open **Capacity audit** and click **Verify measured experiment**. GitHub Pages
   opens the checked-in audit receipt; the local runbook performs a fresh
   archive derivation. The four-row trial matrix exposes every result and
   derives the at-least-2x lower bound from boundaries that agreed in all five
   500-second trials.
4. Open **Release gate**. Inspect the core Arm Performix causal experiment,
   claim ledger, optimization path, exact deployment and reusable GitHub
   Action. This view shows 0% versus 67.02% measured `kai_*` function samples
   while Linux perf separately shows 68.53% cycle attribution.

The public page is an evidence-backed application, not a live AWS dependency.
Recorded output is labeled. Edited text is rejected rather than presented as
model inference.

## Local Product

Prerequisite: Python 3.12.

```bash
git clone https://github.com/QasimKhan5x/ArmProof.git
cd ArmProof
python3.12 scripts/build_surgedesk_demo.py --verify
python3.12 scripts/serve_surgedesk.py --port 8765
```

Open http://127.0.0.1:8765/surgedesk/.

## Validate The Reusable Artifact

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/armproof ci examples/armproof-reference/armproof.json
```

Expected behavior:

- exit `0`;
- all 69 sustained and 35 native Performix checksummed evidence files verify;
- 4,200 raw request outcomes are re-derived and nine required claims pass;
- an offline report and machine-readable decision are written; and
- the reference passing deployment remains linked to that reference decision.

To see a release blocked:

```bash
python3.12 scripts/demo_release_gate.py
```

The script alters only a temporary archive copy. Expected output is a valid
nine-claim pass followed by a digest block before metric derivation.
The same one-byte check is available as a button in the local Release gate
view, so judges can inspect the block without leaving the application.

Scaffold a new HTTP classification endpoint without generating passing evidence:

```bash
armproof init \
  --endpoint http://127.0.0.1:8000/infer \
  --output /tmp/my-arm-service
armproof ci /tmp/my-arm-service/armproof.json
```

The first command creates seven adoption files. The second intentionally exits
`1` until real checksum-bound evidence is collected. The tested
`examples/llama-cpp-http-slo/` bridge demonstrates that the same endpoint
contract works with llama.cpp; it is a compatibility smoke, not a benchmark.

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
