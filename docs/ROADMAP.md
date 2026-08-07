# Roadmap

ArmProof 1.1 supports fixed-SLO HTTP inference comparisons, raw-output quality
checks, native Performix attribution, identity-bound release decisions, an
offline report, and a GitHub Action. SurgeDesk is the reference deployment.

Planned extensions:

- publish a fully measured llama.cpp reference adapter;
- add a vLLM deployment recipe for larger Graviton instances;
- validate the evidence contract on Axion and Cobalt Arm servers;
- support signed evidence manifests and external provenance providers; and
- add workload plugins for generation and embedding services.

These are extensions, not requirements for reproducing the checked-in Phi-4
Mini result. New runtime or cloud claims require their own matched measurements
and cannot inherit the Graviton4 reference result.
