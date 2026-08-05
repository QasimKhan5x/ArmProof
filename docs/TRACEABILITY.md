# Claim And Requirement Traceability

Status values: `established`, `pending`, `unavailable`, `rejected`.

| Claim ID | Claim | Requirements | Evidence | Status |
|---|---|---|---|---|
| C-01 | INT4 artifacts are 35.92% smaller than BF16 | INV-02, FR-02 | `ops/evidence/result-first/EXP-2026-002/summary.json` | established |
| C-02 | INT4 peak PSS is 55.34% lower than BF16 | FR-05 | `ops/evidence/result-first/EXP-2026-002/summary.json` | established |
| C-03 | INT4 time-weighted PSS is 59.66% lower | FR-05 | `ops/evidence/result-first/EXP-2026-002/summary.json` | established |
| C-04 | KleidiAI improved direct E2E speed 1.72x-2.59x | INV-01, INV-02 | `ops/evidence/result-first/EXP-2026-002/ort-enabled.json`, `ort-disabled.json` | established |
| C-05 | Quality did not regress on the 24-item feasibility slice | INV-03, FR-06 | `ops/evidence/result-first/EXP-2026-002/bf16.json`, `ort-enabled.json` | established |
| C-06 | Enabled execution contains `kai_*`; disabled does not | INV-01, FR-07 | `ops/evidence/result-first/EXP-2026-002/perf-enabled.txt`, `perf-disabled.txt` | established |
| C-07 | KleidiAI improves fixed-SLO server capacity >=1.5x | FR-04, FR-05 | `ops/evidence/EXP-2026-004/accepted/evidence/capacity/experiment/summary.json` | established |
| C-08 | Capacity samples exclude policy, report and profiler execution | NFR-02 | `docs/BENCHMARK_PROTOCOL.md`, separate capacity and profiler archives | established |
| C-09 | Missing or swapped evidence fails the contract | INV-04, FR-08, FR-09 | `tests/policy/`, `tests/evidence/test_checksums.py` | established |
| C-10 | A clean machine reproduces within 10% | INV-05, FR-13 | `ops/evidence/EXP-2026-005/reproduction-comparison.json` | established |
| C-11 | One config and one command produce the CI decision | FR-01, FR-11 | `tests/test_ci_command.py` | established |
| C-12 | Report and deployment derive from the same accepted treatment | INV-05, FR-10, FR-12 | `tests/reference/test_deployment_artifact.py`, `tests/report/test_generator.py` | established |
| C-13 | Historical EXP-2026-009 derives an at-least-2.0x sustained lower bound from four boundaries and twenty trials | FR-14, FR-15, FR-16, NFR-08 | `ops/evidence/EXP-2026-009/evidence.tar.gz`, `tests/evidence/test_sustained_audit.py` | established |
| C-14 | Queue guard achieves 86.75% held-out operational accuracy | INV-03, FR-17 | `src/armproof/demo/queue_guard.py`, `tests/surgedesk/test_queue_guard.py`, reference contract claim `quality-operational-queue` | established |
| C-15 | Live mode cannot masquerade as recorded evidence, and matched lanes require distinct endpoints with verified backend identity and CPU affinity | FR-18, NFR-08, NFR-09, P-08 | `scripts/serve_surgedesk.py`, `tests/test_serve_surgedesk.py`, `tests/ui/surgedesk.spec.mjs` | established |
| C-16 | Historical EXP-2026-009 established a conservative capacity result while rejecting its original exact bracket | FR-04, FR-05, INV-04 | `ops/evidence/EXP-2026-009/evidence.tar.gz`, `ops/evidence/EXP-2026-009/RESULT.md`, `tests/evidence/test_sustained_audit.py` | established |
| C-17 | Historical EXP-2026-010 matched Arm Performix Code Hotspots showed enabled `kai_*` function samples versus zero in the control | INV-01, FR-07, FR-19 | `ops/evidence/EXP-2026-010/evidence.tar.gz`, `src/armproof/evidence/performix.py`, `tests/evidence/test_performix.py` | established |
| C-18 | Performix CPU Microarchitecture and Instruction Mix are unavailable on this c8g.4xlarge because the virtual PMU exposes two counters and both recipes require at least three | FR-19 | readiness failures in `ops/evidence/EXP-2026-010/` and `ops/evidence/EXP-2026-011/` | unavailable |
| C-19 | The runtime-neutral adapter derives identities, profiler attribution and task quality from checksummed source files before capacity can pass | INV-01, INV-03, INV-04, P-09 | `src/armproof/evidence/adapters.py`, `examples/http-slo/`, `tests/evidence/test_adapters.py` | established |
| C-20 | The final capacity release uses only the two EXP-2026-014 rates committed before launch and re-derives all ten identity-bound long windows | FR-04, FR-05, INV-04 | `ops/experiments/EXP-2026-014.json`, `ops/evidence/EXP-2026-014/`, `src/armproof/evidence/confirmed_audit.py` | established |
| C-21 | The final quality release reparses 1,540 ledger-locked original model outputs bound to the release model and runtime | INV-03, INV-04 | `ops/evidence/EXP-2026-003/attempt-002/evidence/capacity/quality-batch/`, `src/armproof/evidence/raw_quality.py` | established |
| C-22 | The final Arm execution release uses thresholds from the committed EXP-2026-013 plan and native matched Performix exports | INV-01, FR-07, FR-19 | `ops/experiments/EXP-2026-013.json`, `ops/evidence/EXP-2026-013/`, `src/armproof/evidence/performix.py` | established |
| C-23 | One real localhost flow routes through the control, verifies evidence, binds activation to the audited runtime, then routes through the treatment | FR-18, NFR-08, NFR-09 | `scripts/serve_surgedesk.py`, `tests/test_surgedesk_gateway_e2e.py`, `tests/ui/surgedesk.spec.mjs` | established |
| C-24 | A capacity archive that matches the rates but omits response-level source identity is rejected and remains public | INV-04, NFR-08 | `ops/evidence/EXP-2026-012/`, `ops/experiments/EXP-2026-014.json`, `tests/evidence/test_confirmed_audit.py` | established |
| C-25 | Size and memory percentages are calculated from four hash-locked aggregate measurement files, direct-speed medians from raw repetitions, and the ten-claim contract is bound to the frozen capacity and profiler plans | INV-01, INV-02, INV-04 | `src/armproof/evidence/supporting.py`, `src/armproof/evidence/confirmed_audit.py`, `tests/evidence/test_supporting.py`, `tests/evidence/test_confirmed_audit.py` | established |
| C-26 | The final capacity plan matches a Git object whose time predates the recorded instance launch and appears byte-for-byte in both source and measurement archives; this is integrity and chronology evidence rather than independent AWS attestation | INV-04, NFR-08 | `examples/armproof-reference/preregistration-publication.json`, `src/armproof/evidence/publication.py`, `tests/evidence/test_publication.py` | established |

The 24-item result supports only the BF16-to-INT4 feasibility comparison. The
matched KleidiAI control uses the frozen 770-case evaluation for its accepted
quality claim.
