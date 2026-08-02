# Evidence Adapters

ArmProof adapters turn raw, checksum-bound experiment files into one normalized
comparison. Policy evaluation and report generation operate on that comparison;
an adapter cannot bypass the contract.

## Built-In Adapters

### `kleidiai-capacity-v1`

The complete Phi-4 Mini reference workflow. It validates matched KleidiAI
controls, BANKING77 quality, three traffic shapes, Arm callchains and a second
Graviton run.

### `http-slo-v1`

A runtime-neutral fixed-SLO adapter for bounded HTTP inference services. Its
protocol identifies baseline and optimized treatments, at least three raw JSONL
files for every passing and failing boundary, measurement requirements, and
baseline/optimized profiler files. Every referenced file must remain inside the
evidence root and appear in its verified SHA-256 ledger.

The protocol also points to a checksummed identity manifest. ArmProof derives
the observed artifact, runtime, workload, environment and control identities
from that manifest and then matches them against the contract. An adapter cannot
make evidence pass by copying the contract's expected identities.

It emits a tested pass-point ratio and an identifiable capacity interval:

```text
lower bound = optimized passing rate / baseline failing rate
upper bound = optimized failing rate / baseline passing rate
```

The tested ratio is never relabeled as an exact maximum-capacity estimate.

```json
{
  "adapter": "http-slo-v1",
  "root": "evidence",
  "checksums": "evidence/SHA256SUMS",
  "protocol": "evidence/protocol.json"
}
```

[`examples/http-slo/`](../examples/http-slo/) is a complete executable adoption
kit. It generates raw rows, observed identities, profiler inputs, the checksum
ledger, contract, config, report and a GitHub Action template in one command.

## External Adapters

An adapter package implements the public `EvidenceAdapter` protocol and
registers an entry point:

```toml
[project.entry-points."armproof.evidence_adapters"]
my-runtime-v1 = "my_package.adapter:MyRuntimeAdapter"
```

```python
class MyRuntimeAdapter:
    adapter_id = "my-runtime-v1"

    def verify(self, contract, config, base):
        # Verify integrity, derive metrics from raw files, bind identities,
        # and return armproof.evidence.VerifiedEvidence.
        ...
```

Adapters should fail closed on unknown fields, missing raw samples, unmatched
treatment identities, insufficient observations and absent Arm attribution.
They should not accept a caller-supplied normalized comparison as evidence.

List built-in and installed plugin adapters with `armproof adapters`.
