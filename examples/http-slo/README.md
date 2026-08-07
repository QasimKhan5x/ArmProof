# Generic HTTP SLO Example

This executable example shows how an Arm inference service can adopt ArmProof
without SurgeDesk or the reference KleidiAI adapter. It generates parser-valid
synthetic files for exercising the verifier; it does not reproduce measurement
provenance:

- raw request rows for three passing and failing boundary confirmations;
- raw baseline and optimized quality-response samples;
- parser-ready baseline and optimized `perf report --stdio` exports;
- observed model, runtime, workload, environment and control identities;
- a SHA-256 ledger binding every consumed file;
- a contract, CI config and GitHub Action template.

Run it from the repository root:

```bash
python3 examples/http-slo/build_example.py --output /tmp/armproof-http-slo
python3 -m pip install -e .
armproof seal /tmp/armproof-http-slo/armproof.json
armproof ci \
  /tmp/armproof-http-slo/armproof.json
open /tmp/armproof-http-slo/report/index.html
```

The generated data is intentionally synthetic and is not a performance claim.
It demonstrates integrity and consistency checks; it cannot prove that an
evidence producer collected measurements honestly. Real adopters replace the
synthetic request windows, quality samples, profiler exports, and identity files
with outputs from their own preregistered matched Arm experiment. The protocol is documented in
[`docs/ADAPTERS.md`](../../docs/ADAPTERS.md).
