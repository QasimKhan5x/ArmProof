# ArmProof Architecture

## System Boundary

ArmProof orchestrates existing inference runtimes and profiling tools. It does
not implement model kernels, inference scheduling or model conversion.

```text
contract + workload manifest + raw evidence + SHA-256 ledgers
     |
     v
integrity and schema verification
     |
     v
KleidiAI evidence adapter
     |-- re-derive fixed-SLO boundaries from request JSONL
     |-- re-derive quality from row-level evidence
     |-- validate positive/negative Arm callchains
     |-- cross-check Linux perf with matched Arm Performix attribution
     `-- verify runtime-treatment screen, sustained proof, and rejected candidate
     |
     v
contract identity binding
     |-- model artifact hash
     |-- runtime hash
     |-- workload hash
     |-- environment hash
     `-- exact treatment controls
     |
     v
fail-closed claim ledger
     |-- CLI decision
     |-- GitHub Check
     |-- static report
     `-- deployment manifest
```

## Modules

### Contracts

Parses versioned YAML/JSON inputs, rejects unknown required semantics, and
normalizes them into immutable domain records.

### Treatment Adapters

One adapter owns process command construction, environment, readiness and
shutdown for one treatment. Reference adapters are:

- `pytorch_bf16`;
- `ort_int4_kleidiai_disabled`;
- `ort_int4_kleidiai_enabled`.

Enabled and disabled INT4 adapters must share every field except the explicit
KleidiAI control.

### Workload Runner

Replays frozen requests against a common HTTP interface. It records request
identity, scheduling time, response, status and latency. Traffic policies are
closed-loop smoke, fixed-rate SLO and saturation discovery.

### Collectors

- Process collector: lifecycle, exit status and logs.
- Memory collector: timestamped RSS/PSS from `smaps_rollup`.
- Runtime-memory collector: allocator identity, transparent-huge-page policy,
  fixed-rate request rows, output digests, and restoration of the host policy.
- Performance collector: request latency, accepted throughput and errors.
- Arm collector: two-layer attribution. Linux `perf` supplies an independent
  cycle-callchain record; Arm Performix supplies matched native Code Hotspots,
  plus capability-gated CPU Microarchitecture and Instruction Mix readiness
  results. The normalizer binds
  recipe, command, target, treatment and raw-export hashes before deriving
  `kai_*` execution status.
- Environment collector: CPU, ISA, OS, runtime and artifact identity.

Profiler collection is separate from normal load measurement so profiling
overhead does not contaminate the primary performance result.

For the Phi-4 reference adapter, both profiler layers are required. Performix
is not a report importer or optional visualization: contradictory, missing or
unmatched runs make the Arm-specific release claim unknown and fail the gate.
The adapter verifies the outer archive digest and 40-entry guest checksum ledger, reads
the native Code Hotspots ZIPs, checks matched commands and CPU identity, and
recomputes the positive/negative `kai_*` sample attribution on every CI run.
Its runtime-lock digest, model revision, workload reference and matched
environment are also bound to the sustained release comparison.

The reference adapter then evaluates a separate whole-runtime layer. It keeps
the accepted KleidiAI path active and combines three evidence roles: a paired
sustained comparison, a four-way short treatment screen, and a sustained test
that rejected the tempting simplified recipe. Only the complete ONNX Runtime
thread-scheduling, mimalloc, and transparent-huge-page recipe passed all five
long windows. This layer is not presented as an ISA-only KleidiAI effect. Its
experiment IDs, archive digests, output identity, exact session options,
declared allocator treatment, observed huge-page policy, rate, SLO, and window
counts are verified independently. The archived Stage 3 evidence lacks process
maps, so it does not independently prove that the declared allocator was loaded.

### Quality Evaluator

Receives recorded outputs and a workload-specific metric plugin. It counts
malformed, missing and timed-out outputs as declared by the contract. The core
system does not encode support-routing semantics.

### Evidence Store

An append-only run directory contains raw samples, normalized records, hashes,
commands and logs. Normalized records reference raw evidence rather than copy
unverifiable prose.

### Claim Ledger

Pure policy code evaluates claims. A claim has a causal scope, comparison,
metric, threshold, evidence IDs and status: `pass`, `fail`, `unknown` or
`not_applicable`. Required `unknown` claims fail the contract.

### Authoritative CI Path

`armproof ci` does not accept a caller-authored normalized comparison. It
verifies both evidence ledgers, re-derives metrics with the selected adapter,
binds observed identities to the contract, and only then evaluates policy.
Its `verification.json` receipt records the adapter, derivation source and both
ledger results. Invalid checksums, swapped identities, inconsistent summaries,
and required identity mismatches stop before a release decision is emitted.

### Presenters

CLI, GitHub, the report and SurgeDesk consume the same verification, derivation
and policy path. SurgeDesk rebuilds its payload through that path; it does not
contain a hardcoded passing decision.

The live Phi-4 service reports its ONNX Runtime session tuning, allocator, and
selected transparent-huge-page policy alongside the model, runtime, instance,
CPU affinity, and KleidiAI control. The gateway checks the expected baseline and
optimized recipe identities before promotion and on every optimized response.

## Repository Structure

```text
src/armproof/
  cli.py
  contracts/
  domain/
  adapters/
  workload/
  collectors/
  quality/
  evidence/
  policy/
  report/
tests/
  fixtures/
  contract/
  integration/
report/
action.yml
examples/phi4-graviton/
schemas/
ops/evidence/
```

## Error Model

Errors use stable reason codes grouped as contract, execution, evidence,
attribution, quality and policy failures. Exceptions are not converted into
passing or partial decisions.

## Trust Boundaries

- Contract and workload content are untrusted input.
- Raw evidence is immutable after collection but not trusted until verified.
- Normalized evidence is derived and must retain provenance.
- The claim decision is trusted only after schema, hash and dependency checks.
- Report text is presentation, never authority.

## Deployment Output

The generated manifest pins the exact passing treatment identity, model,
runtime, environment variables, arguments and resource settings. It is not a
general deployment platform.
