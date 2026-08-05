# EXP-2026-012 Result: Rejected

The raw capacity outcomes matched the preregistered one-sided design on a fresh
AWS `c8g.4xlarge`:

- the KleidiAI-disabled service failed all five 500-second windows at
  `0.28 requests/s`;
- the KleidiAI-enabled service passed all five windows at `0.56 requests/s`;
- reanalysis from each scheduled send through completion produced enabled p95
  latency from `3.297 s` to `3.353 s`; and
- quality remained inside the one-percentage-point tolerance with 100% schema
  validity.

Those outcomes do not approve a release from this archive. The committed
`EXP-2026-012-analysis.json` requires successful responses to carry
`source_artifact_sha256` with the model, runtime, Arm64, thread and treatment
identity. The response records contain the other fields but omit that source
hash. The canonical release adapter therefore rejects the archive before policy
approval.

The raw archive and its 48-entry internal SHA-256 ledger remain unchanged.
EXP-2026-014 repeats the same rates, workload, SLO, model and runtime after the
missing field was added to the response identity. No result from EXP-2026-012 is
used to approve the public release.

## Audit artifacts

- `evidence.tar.gz`: SHA-256 `9d45bdca8d82e1254a1c1f37014e44b953d9001ff201f3999dc8c496e483654b`
- `project.tar.gz`: SHA-256 `afa3a6c8249eb3af986ee90dcfac9acf06607de2aa22c864c8835bbc90bfa487`
- Session cost: `$1.0438`
- Estimated cumulative project cost after this run: `$11.9837`
- AWS cleanup: complete; instance terminated; post-run inventory empty
