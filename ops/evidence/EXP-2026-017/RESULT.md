# EXP-2026-017 Result: Simplification Rejected

This one-sided Graviton4 experiment tested whether the short-screen winner from
EXP-2026-016 could replace the full runtime recipe. It kept the same Phi-4 Mini
INT4 model, KleidiAI path, 16 threads, BANKING77 mixed workload, 0.62 requests/s
rate, and 10-second p95 rule, but removed the three ONNX Runtime thread options.

| Window | p95 | SLO result | Errors |
| ---: | ---: | --- | ---: |
| 1 | 10.27 s | Fail | 0 |
| 2 | 12.29 s | Fail | 0 |
| 3 | 13.42 s | Fail | 0 |
| 4 | 14.94 s | Fail | 0 |
| 5 | 11.40 s | Fail | 0 |

The simplified `mimalloc + THP` treatment failed all five 300-second windows.
Outputs remained identical to the frozen digest and the host THP policy was
restored, so the rejection is caused by the response-time rule rather than
errors or output drift.

EXP-2026-015 remains the release evidence: at the same 0.62 requests/s, the
KleidiAI-only service failed 5/5 windows while the complete ONNX Runtime thread
tuning, mimalloc, and THP recipe passed 5/5. The final product therefore retains
the complete sustained recipe. The short ablation is useful diagnostic evidence
but does not override the long test.

## Audit Artifacts

- Evidence archive: `ops/evidence/EXP-2026-017/evidence.tar.gz`
- Archive SHA-256: `19c55410275b75d23c5dfce15ed0d735e2e608ca1106a8146bce6bcb12364761`
- Archived checksums: 26 files, passed
- Session cost: `$0.3303`
- Conservative cumulative project estimate: `$14.8019`
- AWS cleanup: complete; instance terminated; post-run inventory empty
