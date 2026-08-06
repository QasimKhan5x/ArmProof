# EXP-2026-015 Result: Accepted

The preregistered Graviton4 experiment tested three additions to the existing
KleidiAI-enabled SurgeDesk runtime: ONNX Runtime thread-pool tuning, mimalloc,
and a combined thread-and-memory treatment that also enabled transparent huge
pages (THP). The model, 16-thread allocation, workload, instance, and 10-second
p95 objective remained fixed.

## Sustained result

At `0.62 requests/s`, five matched 300-second windows produced:

| Runtime | Passing windows | Median p95 | Median observed RSS |
| --- | ---: | ---: | ---: |
| Current KleidiAI runtime | 0/5 | 14.81 s | 5.30 GB |
| Combined thread-memory treatment | 5/5 | 8.15 s | 4.14 GB |

The selected treatment reduced median p95 by 44.98%. It also raised the
accepted sustainable-capacity lower bound from `0.56` to `0.62 requests/s`, a
10.71% increase beyond the existing KleidiAI result. Every request completed
without an error, and the compared model outputs were identical.

The observed median RSS was 21.89% lower during these windows. That value
describes process memory under the measured queueing pressure; it is not
presented as a standalone allocator-footprint reduction.

## Screening result

The two 120-second screens per variant showed why a combined treatment was
selected:

| Variant | Median p95 | Result |
| --- | ---: | --- |
| Current | 7.22 s | Reference |
| Thread tuning | 8.19 s | Regression |
| mimalloc | 7.36 s | No p95 improvement |
| Thread tuning + mimalloc + THP | 3.84 s | 46.79% lower |

EXP-2026-016 separately isolates these mechanisms. Its short screens indicate
that THP supplies a real gain, mimalloc interacts strongly with THP, and thread
tuning is not useful. The sustained claim here remains limited to the exact
combined treatment that received five long confirmations.

## Audit artifacts

- Evidence archive: `ops/evidence/EXP-2026-015/evidence.tar.gz`
- Accepted session cost: `$0.8336`
- Conservative cumulative project estimate: `$14.3208`
- Output equivalence: passed
- Archived checksums: passed
- THP restoration: passed
- AWS cleanup: complete; instance terminated; post-run inventory empty
