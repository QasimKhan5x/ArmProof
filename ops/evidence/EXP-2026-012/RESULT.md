# EXP-2026-012 Result: Accepted

The preregistered one-sided confirmation passed on a fresh AWS
`c8g.4xlarge`. The same Phi-4 Mini INT4 artifact, ONNX Runtime GenAI build,
16-thread configuration, workload and 10-second p95 objective were used in both
lanes. The only treatment control was `mlas.disable_kleidiai`.

- The KleidiAI-disabled service failed all five 500-second windows at
  `0.28 requests/s`.
- The KleidiAI-enabled service passed all five 500-second windows at
  `0.56 requests/s` with zero errors.
- Reanalysis from each request's scheduled send through completion produced
  enabled p95 latency from `3.297 s` to `3.353 s`. Maximum client dispatch
  delay was `3.307 ms`.
- Disabled p95 latency was at least `60.060 s`, with timeout errors in every
  window.
- The frozen result therefore establishes a conservative lower bound of
  `0.56 / 0.28 = at least 2.0x` sustained capacity on the same server.
- Quality stayed within the preregistered one-percentage-point tolerance and
  schema validity was 100%.

The release adapter ignores the collector's stored pass field. It re-derives
the decision from 2,100 raw request rows under the committed
`EXP-2026-012-analysis.json` rules, verifies a runtime identity on every
successful response, and checks the 48-entry internal SHA-256 ledger.

## Audit artifacts

- `evidence.tar.gz`: SHA-256 `9d45bdca8d82e1254a1c1f37014e44b953d9001ff201f3999dc8c496e483654b`
- `project.tar.gz`: SHA-256 `afa3a6c8249eb3af986ee90dcfac9acf06607de2aa22c864c8835bbc90bfa487`
- Session cost: `$1.0438`
- Estimated cumulative project cost: `$11.9837`
- AWS cleanup: complete; instance terminated; post-run inventory empty
