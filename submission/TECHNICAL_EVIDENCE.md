# Technical Evidence Map

This is the shortest path from each submission claim to its authoritative
artifact. The prose submission is never the source of truth.

## Environment

- AWS `c8g.4xlarge`, Graviton4, CPU-only, 16 vCPUs.
- Phi-4 Mini.
- PyTorch BF16 reference.
- ONNX Runtime GenAI INT4 treatment.
- Matched Arm control: identical INT4 model/runtime with
  `mlas.disable_kleidiai=1`.
- Capacity objective: p95 at or below 10 seconds.

See [`examples/phi4-graviton/runtime-lock.json`](../examples/phi4-graviton/runtime-lock.json),
[`examples/phi4-graviton/passing-deployment.json`](../examples/phi4-graviton/passing-deployment.json)
and the accepted
[`environment.json`](../ops/evidence/EXP-2026-004/accepted/evidence/capacity/experiment/environment.json).

## Claim Ledger

| Claim | Comparison | Result | Authoritative artifact |
|---|---|---:|---|
| Artifact size | INT4 versus BF16 | 35.92% smaller | [`summary.json`](../ops/evidence/result-first/EXP-2026-002/summary.json) |
| Peak PSS | INT4 versus BF16 | 55.34% lower | [`summary.json`](../ops/evidence/result-first/EXP-2026-002/summary.json) |
| Time-weighted PSS | INT4 versus BF16 | 59.66% lower | [`summary.json`](../ops/evidence/result-first/EXP-2026-002/summary.json) |
| Direct Arm speed | KleidiAI enabled versus disabled, same INT4 runtime | 1.72x-2.59x | [`summary.json`](../ops/evidence/result-first/EXP-2026-002/summary.json) |
| Arm execution | Enabled and disabled perf callchains | `kai_*` only when enabled | [`perf-enabled.txt`](../ops/evidence/EXP-2026-004/accepted/evidence/perf-enabled.txt), [`perf-disabled.txt`](../ops/evidence/EXP-2026-004/accepted/evidence/perf-disabled.txt) |
| Confirmed tested fixed-SLO capacity | Enabled versus disabled | 3.0x short, 2.5x long, 3.0x mixed | Re-derived from request JSONL; accepted [`summary.json`](../ops/evidence/EXP-2026-004/accepted/evidence/capacity/experiment/summary.json) is cross-checked |
| Large-set quality | Enabled versus disabled, 770 requests | -0.390 pp accuracy; -0.673 pp macro F1 | [`comparison.json`](../ops/evidence/EXP-2026-004/accepted/evidence/capacity/experiment/quality/comparison.json) |
| Schema validity | Both normalized treatments | 100% | [`comparison.json`](../ops/evidence/EXP-2026-004/accepted/evidence/capacity/experiment/quality/comparison.json) |
| Clean reproduction | Fresh c8g.4xlarge versus accepted ratios | 0% difference for all mixes | [`reproduction-comparison.json`](../ops/evidence/EXP-2026-005/reproduction-comparison.json) |
| Operational routing | Queue guard on disjoint holdout | 86.75%, +12.34 pp | [`comparison.json`](../examples/armproof-reference/comparison.json) |

## Causal Boundaries

- Do not attribute BF16-to-INT4 size or memory reductions to KleidiAI.
- Do not attribute the queue guard's quality gain to Arm.
- The Arm-specific comparison is KleidiAI enabled versus disabled inside the
  otherwise identical INT4 deployment.
- Capacity claims are scoped to the pinned model, runtime, workload,
  `c8g.4xlarge` and 10-second p95 objective.
- ArmProof means verified against the declared contract, not Arm certified.

## Reproduce The Decision

```bash
python3.12 -m pip install -e .
armproof ci examples/armproof-reference/armproof.json
```

Expected exit code: `0`. The command verifies 282 files, re-derives capacity
and quality, binds treatment identities to the contract, checks reproduction,
and then regenerates `verification.json`, `comparison.json`, `decision.json`
and the offline report. A supplied normalized comparison is not accepted.

Test integrity and fail-closed behavior:

```bash
python3.12 scripts/demo_release_gate.py

armproof verify \
  --contract examples/fixture-fail/contract.json \
  --comparison examples/fixture-fail/comparison.json

armproof verify \
  --contract examples/fixture-unknown/contract.json \
  --comparison examples/fixture-unknown/comparison.json
```

Expected exit code for both fixtures: `2`.

## Verify Raw Evidence

```bash
armproof evidence-verify \
  --checksums ops/evidence/EXP-2026-004/accepted/evidence/SHA256SUMS \
  --root ops/evidence/EXP-2026-004/accepted/evidence
```

The accepted and reproduction bundles each contain 141 checksummed guest
files. Empty, changed, duplicate, missing or out-of-root ledger entries fail.
The ledgers prove repository consistency after capture, not independent
attestation of who produced the original measurements.
