# EXP-2026-013 Result: Accepted

The fresh native Arm Performix Code Hotspots confirmation passed on AWS
Graviton4. Both profiles used the same source model fingerprint, frozen
BANKING77 workload, ONNX Runtime build, 16-thread configuration and
`c8g.4xlarge`. The only model-session difference was the preregistered KleidiAI
control.

- Control run `51e4d24b6c03`: 0 `kai_*` samples out of 944,847 function samples.
- Treatment run `2a6259add5fe`: 245,876 `kai_*` samples out of 365,062, or
  67.35%.
- The treatment export names the Neoverse I8MM matrix kernel family.
- Both profiles exceed the frozen minimum of 100,000 function samples, and the
  treatment exceeds the frozen 50% KleidiAI share.
- The archive records the exact source-model SHA-256
  `9ef697ababdc0b4ffc63b098bbd4760f79795eb0502ca4d41c80e20843ac0ab1`
  and workload SHA-256
  `86b756c46ef2c647ddd779ccc4dd6bafd2aad0c261f4e24cf6177c224a1e1118`.

ArmProof derives these values again from the two native Performix ZIP exports.
The 40-entry guest ledger, outer archive digest, committed preregistration,
captured treatment configs, Graviton4 identity, commands, run IDs, model and
workload digests must all agree before this evidence can approve the release.

Attempt 1 failed before profiling because of a cold-import cycle and remains
preserved under `attempt-001/`; it contributes no evidence to this result.

## Audit artifacts

- `evidence.tar.gz`: SHA-256 `9301e9da951ce8b294b8b1a2153a2d333017cbeecef73ab5d930b90bde2d7d4e`
- `project.tar.gz`: SHA-256 `a59440982882440a0aff95f63ba3616f54fe0918242e9cf298bd18e7da19df33`
- Accepted session cost: `$0.0607`
- Conservative cumulative project estimate: `$12.4369`
- AWS cleanup: complete; instance terminated; post-run inventory empty
