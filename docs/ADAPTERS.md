# Evidence Adapters

ArmProof adapters turn raw, checksum-bound experiment files into one normalized
comparison. Policy evaluation and report generation operate on that comparison;
an adapter cannot bypass the contract.

## Built-In Adapters

### `kleidiai-capacity-v1`

The complete Phi-4 Mini reference workflow. It validates matched KleidiAI
controls, BANKING77 quality, three traffic shapes, Arm callchains and a second
Graviton run. Its Performix evidence must carry runtime, model, workload and
environment bindings that match the normalized comparison.

### `kleidiai-sustained-v1`

The historical EXP-2026-009 adapter. It verifies the
immutable sustained-capacity and Performix archives, re-derives every capacity
and quality metric from 4,200 request outcomes, and binds the observed Neoverse
kernel path to the same model, runtime, workload, machine and thread count.

### `kleidiai-confirmed-v2`

The current reference release adapter. It requires byte-for-byte copies of the
committed EXP-2026-014 capacity and EXP-2026-013 Performix preregistrations. It
re-derives ten fixed-rate windows, verifies 1,540 original model outputs,
checks the frozen workload and treatment identities, and reads native Performix
Code Hotspots exports. Capacity rates and profiler thresholds come from the
committed plans; the release config cannot replace them after collection.
The adapter also verifies three independent runtime-treatment archives: the
paired KleidiAI-only versus full-recipe sustained test, the short
mechanism-isolation screen, and the sustained rejection of a simplified
candidate. It releases only the complete thread-scheduling, allocator, and THP
recipe that passed every long window, with unchanged outputs and restored host
page policy. These conditions are a separate whole-runtime layer and do not
alter the causal scope of the KleidiAI-only comparison.

### `http-slo-v1`

A runtime-neutral fixed-SLO adapter for bounded HTTP classification services.
Its protocol identifies baseline and optimized treatments, at least three
independent raw JSONL files for every passing and failing boundary,
measurement requirements, and baseline/optimized profiler files. Every
referenced file must remain inside the evidence root and appear in its verified
SHA-256 ledger. Reused paths, duplicate file contents, unordered timestamps,
and request schedules that disagree with the declared measurement duration are
rejected.

The identity manifest names source files for the artifact, runtime, workload,
and environment. ArmProof hashes those files itself, then compares the derived
digests and observed treatment controls with the contract. The workload
manifest must also contain the hashes ArmProof derives from the consumed
capacity and quality workloads.

Both profiler inputs are parser-ready Linux `perf report --stdio` exports with
the event, sample count, lost-sample count, and symbol table used for
attribution. A separate profile manifest binds each consumed report digest to
the treatment command, artifact, runtime, workload, environment and control.
The baseline must show no accelerated Arm symbols while the treatment must show
the declared path. The adapter rejects a missing profile, lost samples,
unparseable events, a positive baseline, or a negative treatment.

The built-in quality profile binds an exact-label classification workload to
raw baseline and treatment HTTP response samples. ArmProof parses the model
outputs and re-derives accuracy, macro F1, schema validity, and output
agreement. Three required quality claims must be
present, and the capacity claim must depend on them. Other output types use an
external evidence adapter rather than pretending classification metrics apply.
The generic contract must require a capacity gain above 1.0x, at least 95%
schema-valid output, and no more than five percentage points of accuracy or
macro-F1 regression.

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
kit. It generates raw capacity and quality-response rows, identity sources,
parser-ready profiler exports, the checksum ledger, contract, config, report, and a GitHub Action
template in one command.

The adapter verifies integrity and internal consistency after collection. It
consumes the checksum-bound text export rather than claiming to validate an
unused binary `perf.data` file. It does not remotely attest that an evidence
producer ran the command honestly; use a trusted Arm evidence runner and
publication attestation for that boundary.

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
