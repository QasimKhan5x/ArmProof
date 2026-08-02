# Development

## Prerequisites

- Python 3.12
- GNU Make
- Linux Arm64 only for `/proc` PSS collection and accepted Arm evidence

The core has no runtime package dependency. Run it directly from `src`:

```bash
make check
PYTHONPATH=src python3.12 -m armproof.cli ci \
  examples/armproof-reference/armproof.json
```

`make check` validates durable context, imported evidence, unit/contract tests,
and Python compilation. CI executes it on x86 and Arm64 runners.

The reusable Action consumes that same config. Pass, measured-fail and
missing-attribution fixtures are under `examples/fixture-*`.

## Evidence Integrity

```bash
PYTHONPATH=src python3.12 -m armproof.cli evidence-verify \
  --checksums ops/evidence/EXP-2026-004/accepted/evidence/SHA256SUMS \
  --root ops/evidence/EXP-2026-004/accepted/evidence
```

The accepted and fresh-instance confirmation bundles each verify 141 files with no
missing or mismatched entries. `armproof ci` verifies both, derives capacity
and quality, binds identities to the contract, then evaluates policy. Run the
safe integrity demonstration with:

```bash
python3.12 scripts/demo_release_gate.py
```

## Capacity Harness

Against a service implementing `POST /infer`:

```bash
PYTHONPATH=src python3.12 -m armproof.cli capacity \
  --endpoint http://127.0.0.1:8000/infer \
  --workload examples/workload-smoke.jsonl \
  --candidates-rps 1,2,4 \
  --measurement-seconds 10 \
  --p95-slo-ms 2000 \
  --output ops/evidence/local-capacity
```

This command is a harness smoke path, not accepted benchmark evidence. Accepted
runs must follow `docs/BENCHMARK_PROTOCOL.md` and `docs/CAPACITY_VALIDATION.md`.

## Network Integration Test

The default suite mocks localhost HTTP because some agent sandboxes prohibit
loopback connections. On a normal host, run the real subprocess test with:

```bash
ARMPROOF_NETWORK_TESTS=1 PYTHONPATH=src python3.12 -m unittest \
  tests.adapters.test_http_service -v
```
