# Evidence Bundles

## Storage policy

Each experiment has one canonical representation in this repository. Early
experiments `EXP-2026-003` through `EXP-2026-005` keep their checksum-bound
expanded evidence because the quality and reproduction tests read individual
files. Later release experiments keep immutable archives because ArmProof
audits those archives directly. We do not keep both forms when one is unused.

Model files referenced by the early capacity runs are identified by hashes in
the evidence. They are not vendored or represented by machine-local symlinks.
The accepted measurements, raw profiler data, logs, checksums, and failed runs
remain in the repository.

Normalized run bundles live under `ops/evidence/<experiment-id>/<run-id>/`.
Large raw traces and model files may use external artifact storage, but their
manifests, hashes, licenses and immutable URLs belong here.

An accepted bundle contains the identities, commands, environment probe, raw
samples, profiler output, quality output, statistical summary and claim ledger
defined by [`docs/ARCHITECTURE.md`](../../docs/ARCHITECTURE.md) and
[`docs/BENCHMARK_PROTOCOL.md`](../../docs/BENCHMARK_PROTOCOL.md).

Do not publish a metric from a prose-only summary. Do not delete failed runs.
Redact credentials and machine identifiers before making a bundle public.
