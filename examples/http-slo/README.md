# Generic HTTP SLO Example

This executable example shows how an Arm inference service can adopt ArmProof
without SurgeDesk or the reference KleidiAI adapter. It builds a small synthetic
bundle with the same trust properties expected from real evidence:

- raw request rows for three passing and failing boundary confirmations;
- baseline and optimized profiler outputs;
- observed model, runtime, workload, environment and control identities;
- a SHA-256 ledger binding every consumed file;
- a contract, CI config and GitHub Action template.

Run it from the repository root:

```bash
python3 examples/http-slo/build_example.py --output /tmp/armproof-http-slo
PYTHONPATH=src python3 -m armproof.cli ci \
  /tmp/armproof-http-slo/armproof.json
open /tmp/armproof-http-slo/report/index.html
```

The generated data is intentionally synthetic and is not a performance claim.
Replace its request rows, profiles and identity source files with outputs from
your own matched Arm experiment. The protocol is documented in
[`docs/ADAPTERS.md`](../../docs/ADAPTERS.md).
