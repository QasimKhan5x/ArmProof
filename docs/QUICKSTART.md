# ArmProof Quickstart

## Run SurgeDesk

The application works from accepted, checksummed experiment files without
cloud access. Its local gateway re-derives the release evidence when requested,
and optional live endpoints add real Arm64 requests before and after activation:

```bash
python3.12 scripts/build_surgedesk.py --verify
python3.12 scripts/serve_surgedesk.py --port 8765
```

Open `http://127.0.0.1:8765/surgedesk/#triage`, route a request, then continue
through Release evidence and Traffic switch.
The views are directly addressable as `#triage`, `#evidence`, and `#release`.
See [`SURGEDESK.md`](SURGEDESK.md) for provenance and the connected reference
flow. The former `#surge` and `#proof` hashes remain compatibility aliases.

## Evaluate The Reference

ArmProof's policy and report path has no runtime dependencies beyond Python
3.12:

```bash
python3.12 -m pip install .
armproof ci examples/armproof-reference/armproof.json
```

The command verifies the confirmatory capacity, native Arm Performix, and
runtime-treatment experiment archives. It re-derives 2,100 capacity requests,
1,540 raw model outputs, the memory ablation, and the sustained final recipe,
then writes a machine-readable decision, a verification receipt and an offline
`index.html`.
Exit `0` means all required claims passed, `2` means at least one required
claim failed or is unknown, and `1` means the inputs could not be evaluated.

Print the same release decision consumed by SurgeDesk and CI:

```bash
python3.12 scripts/verify_reference_release.py
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
[`schemas/ci-config.schema.json`](../schemas/ci-config.schema.json). After the
contract is final, compute the protected digest that the Action must receive:

```bash
sha256sum contract.json
```

Then add these steps, replacing both placeholders with the released Action's
full commit SHA and the digest printed above:

```yaml
- uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7

- uses: actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97 # v7
  with:
    python-version: "3.12"

- uses: QasimKhan5x/ArmProof@7e1f33510af34f79a46b9011a26b899e80ff0dc4
  with:
    config: armproof.json
    output: build/armproof-report
    contract-sha256: REPLACE_WITH_CONTRACT_SHA256

- if: always()
  uses: actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a # v7
  with:
    name: armproof-report
    path: build/armproof-report
```

For a published release, download `armproof-evidence.tar.gz` and verify its
GitHub build provenance:

```bash
gh attestation verify armproof-evidence.tar.gz \
  -R QasimKhan5x/ArmProof
sha256sum -c armproof-evidence.tar.gz.sha256
```

The attestation binds the release bundle to this repository, workflow and
commit. It does not independently certify the AWS machine that produced the
raw measurements; ArmProof's checksummed evidence and matched controls cover
that declared trust boundary.

Pin the released Action commit in production. Never run paid benchmarks or
cloud credentials in `pull_request_target` or on untrusted fork code. The
Action verifies raw evidence ledgers, re-derives the comparison and
binds it to the contract. Produce evidence on a trusted Arm runner; the ledger
detects later modification but does not independently attest who produced it.

Release workflow `.github/workflows/evidence-attestation.yml` packages the
accepted evidence and derived report and uses GitHub artifact attestations to
bind that published bundle to a repository, workflow and commit. This protects
publication provenance; it does not independently certify the original AWS
measurement process.

## Produce Evidence

The built-in collector targets a bounded HTTP classification endpoint accepting
`POST /infer` with a request ID, prompt and token limit. ArmProof provides
separate commands for load and exact-label quality collection:

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

When collection is complete, seal every file under the configured evidence
root and then evaluate the contract:

```bash
armproof seal armproof.json
armproof ci armproof.json
```

`seal` only writes the deterministic ledger. It does not approve incomplete or
invalid measurements; the subsequent `ci` command remains the policy gate.

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

Use the built-in `http-slo-v1` classification evidence adapter or publish an
external adapter through the `armproof.evidence_adapters` entry-point group. See
[`ADAPTERS.md`](ADAPTERS.md) for the public contract and an executable example.

Keep these boundaries intact:

1. Baseline and treatment expose the same HTTP contract.
2. Only the declared optimization control changes in an Arm-causal comparison.
3. Raw collection, verified derivation, policy decision and report remain
   separate artifacts; CI must derive rather than trust a supplied comparison.
4. Quality claims pass before dependent performance claims.
5. The deployment manifest points to the exact passing treatment.

Start from `examples/http-slo/`, the JSON schemas and the pass/fail/unknown
fixtures. Other output types require an external adapter; runtime breadth is an
extension point, not hidden inside the reference report.
