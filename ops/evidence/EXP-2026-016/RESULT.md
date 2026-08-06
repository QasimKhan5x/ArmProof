# EXP-2026-016 Result: Mechanism Isolation Passed

This cost-bounded Graviton4 ablation tested which memory treatment produced the
additional EXP-2026-015 gain. Each variant ran two alternating 60-second
screens near `0.62 requests/s` with the same Phi-4 Mini INT4 model, 16 threads,
KleidiAI-enabled runtime, workload, and 10-second p95 objective.

| Variant | Median p95 | Change from current | Passing screens |
| --- | ---: | ---: | ---: |
| Current | 5.37 s | Reference | 2/2 |
| THP only | 4.13 s | 23.14% lower | 2/2 |
| Thread tuning + THP | 4.26 s | 20.74% lower | 2/2 |
| mimalloc + THP | 3.06 s | 43.06% lower | 2/2 |

The result supports three conclusions:

1. THP independently reduces latency for this Arm inference workload.
2. Thread-pool tuning does not improve the THP result and should not be part of
   the recommended recipe.
3. mimalloc is useful in combination with THP even though mimalloc alone did
   not improve p95 in EXP-2026-015, indicating an allocator/page interaction.

The compared outputs were identical. These short screens establish mechanism
direction, not a new sustained capacity claim. EXP-2026-015 remains the
sustained five-run evidence for the full combined treatment. A future sustained
confirmation can test the simpler `mimalloc + THP` recipe without thread
tuning.

## Audit artifacts

- Evidence archive: `ops/evidence/EXP-2026-016/evidence.tar.gz`
- Accepted session cost: `$0.1508`
- Conservative cumulative project estimate: `$14.4716`
- Output equivalence: passed
- Archived checksums: passed
- THP restoration: passed
- AWS cleanup: complete; instance terminated; post-run inventory empty
