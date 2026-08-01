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
| C-08 | ArmProof overhead is below 5% | NFR-02 | `LOAD-001` overhead comparison | pending |
| C-09 | Missing or swapped evidence fails the contract | INV-04, FR-08, FR-09 | `tests/policy/`, `tests/evidence/test_checksums.py` | established |
| C-10 | A clean machine reproduces within 10% | INV-05, FR-13 | `ops/evidence/EXP-2026-005/reproduction-comparison.json` | established |
| C-11 | One config and one command produce the CI decision | FR-01, FR-11 | `tests/test_ci_command.py` | established |
| C-12 | Report and deployment derive from the same accepted treatment | INV-05, FR-10, FR-12 | `tests/reference/test_deployment_artifact.py`, `tests/report/test_generator.py` | established |

The 24-item result supports only the BF16-to-INT4 feasibility comparison. The
matched KleidiAI control uses the frozen 770-case evaluation for its accepted
quality claim.
