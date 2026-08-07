# Phi-4 Graviton Reference

This is ArmProof's single reference deployment. Use the revisions in
`runtime-lock.json` and restore the checksummed Arm64 ONNX Runtime artifacts
listed in `ops/evidence/imported-migration-measurements/EXP-2026-002/build-artifacts/SHA256SUMS`.

Create matched INT4 overlays:

```bash
PYTHONPATH=src python3.12 scripts/prepare_phi4_variants.py \
  --source /models/phi4-int4 \
  --output-root /models/armproof-variants \
  --threads 16
```

Launch one treatment at a time:

```bash
OMP_NUM_THREADS=16 PYTHONPATH=src python3.12 -m armproof.reference.phi4 \
  --backend ort-int4 \
  --model /models/armproof-variants/kleidiai-enabled \
  --label ort-int4-kleidiai-enabled \
  --port 8000 \
  --threads 16 \
  --max-inflight 1
```

Use the corresponding `kleidiai-disabled` overlay for the matched control.
The BF16 baseline uses `--backend pytorch-bf16` and the pinned BF16 model.

The server binds loopback by default and exposes `GET /health` and `POST
/infer`. A request contains `request_id`, `prompt`, and optional
`max_new_tokens`. Responses include queue and inference latency separately.

`passing-deployment.json` records the exact artifact, runtime, hardware,
service controls and conservative sustained result from `EXP-2026-014`. The reusable systemd
unit and environment template are under `deploy/`.

Verify the immutable sustained audit before trusting the normalized result:

```bash
shasum -a 256 ops/evidence/EXP-2026-014/evidence.tar.gz
PYTHONPATH=src python3.12 -m unittest tests.evidence.test_confirmed_audit -v
```

The real Graviton service smoke, artifact identities, profiler callchains and
fixed-SLO capacity gate all passed. The unit binds loopback by default; place
an authenticated reverse proxy in front of it for remote access.
