# Evidence Bundles

Normalized run bundles live under `ops/evidence/<experiment-id>/<run-id>/`.
Large raw traces and model files may use external artifact storage, but their
manifests, hashes, licenses and immutable URLs belong here.

An accepted bundle contains the identities, commands, environment probe, raw
samples, profiler output, quality output, statistical summary and claim ledger
defined by [`docs/ARCHITECTURE.md`](../../docs/ARCHITECTURE.md) and
[`docs/BENCHMARK_PROTOCOL.md`](../../docs/BENCHMARK_PROTOCOL.md).

Do not publish a metric from a prose-only summary. Do not delete failed runs.
Redact credentials and machine identifiers before making a bundle public.
