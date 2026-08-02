# ArmProof Quickstart

## Run SurgeDesk

The application demo is static, but its cases and measurements are generated
from accepted, checksummed experiment files:

```bash
python3.12 scripts/build_surgedesk_demo.py --verify
python3.12 scripts/serve_surgedesk.py --port 8765
```

Open `http://127.0.0.1:8765/surgedesk/#triage`. Choose **Guard intervention**
or **Human correction**, then continue through Arm result and Release proof.
The views are directly addressable as `#triage`, `#surge`, and `#proof`. See
[`SURGEDESK_DEMO.md`](SURGEDESK_DEMO.md) for provenance and narration.

## Evaluate The Reference

ArmProof's policy and report path has no runtime dependencies beyond Python
3.12:

```bash
python3.12 -m pip install .
armproof ci examples/armproof-reference/armproof.json
```

The command verifies and derives from 282 checksum-bound files, then writes a
machine-readable decision, a verification receipt and an offline `index.html`.
Exit `0` means all required claims passed, `2` means at least one required
claim failed or is unknown, and `1` means the inputs could not be evaluated.

Run the integrity challenge to see valid evidence pass and a temporary
one-digest mutation block before policy evaluation:

```bash
python3.12 scripts/demo_release_gate.py
```

Use the normalized negative fixtures to inspect policy fail-closed behavior:

```bash
armproof verify \
  --contract examples/fixture-fail/contract.json \
  --comparison examples/fixture-fail/comparison.json

armproof verify \
  --contract examples/fixture-unknown/contract.json \
  --comparison examples/fixture-unknown/comparison.json
```

## Add The GitHub Gate

Create an `armproof.json` matching
[`schemas/ci-config.schema.json`](../schemas/ci-config.schema.json), then add:

```yaml
- uses: QasimKhan5x/VerifyLane@v0.3.0
  with:
    config: armproof.json
    output: build/armproof-report

- if: always()
  uses: actions/upload-artifact@v4
  with:
    name: armproof-report
    path: build/armproof-report
```

Pin the released Action commit in production. Never run paid benchmarks or
cloud credentials in `pull_request_target` or on untrusted fork code. The
reference Action verifies raw evidence ledgers, re-derives the comparison and
binds it to the contract. Produce evidence on a trusted Arm runner; the ledger
detects later modification but does not independently attest who produced it.

Release workflow `.github/workflows/evidence-attestation.yml` packages the
accepted evidence and derived report and uses GitHub artifact attestations to
bind that published bundle to a repository, workflow and commit. This protects
publication provenance; it does not independently certify the original AWS
measurement process.

## Produce Evidence

The built-in collector only needs a bounded HTTP endpoint accepting `POST /infer` with a
request ID, prompt and token limit. ArmProof provides separate commands for
load and quality collection:

```bash
armproof capacity \
  --endpoint http://127.0.0.1:8000/infer \
  --workload workload.jsonl \
  --candidates-rps 0.1,0.2,0.4 \
  --measurement-seconds 30 \
  --p95-slo-ms 10000 \
  --output evidence/capacity

armproof quality \
  --endpoint http://127.0.0.1:8000/infer \
  --dataset quality.jsonl \
  --output evidence/quality
```

Run matched baseline and treatment configurations on the same Arm machine.
Record model, runtime, workload and environment hashes, and provide executed
Arm-path evidence for Arm-specific claims. A compiled or available library is
not execution evidence.

## Verify Raw Evidence

Guest-generated archives remain portable after relocation:

```bash
armproof evidence-verify \
  --checksums evidence/SHA256SUMS \
  --root evidence
```

An empty ledger, missing file, changed digest, duplicate entry or path outside
the declared guest prefix fails verification.

## Adapt Another Runtime

Use the built-in `http-slo-v1` raw-evidence adapter or publish an external
adapter through the `armproof.evidence_adapters` entry-point group. See
[`ADAPTERS.md`](ADAPTERS.md) for the public contract and an executable example.

Keep these boundaries intact:

1. Baseline and treatment expose the same HTTP contract.
2. Only the declared optimization control changes in an Arm-causal comparison.
3. Raw collection, verified derivation, policy decision and report remain
   separate artifacts; CI must derive rather than trust a supplied comparison.
4. Quality claims pass before dependent performance claims.
5. The deployment manifest points to the exact passing treatment.

Start from `examples/phi4-graviton/`, the JSON schemas and the pass/fail/unknown
fixtures. Runtime breadth is intentionally an extension point, not hidden
inside the reference report.
