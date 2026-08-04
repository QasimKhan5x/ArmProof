# SurgeDesk Demo Guide

## Purpose

SurgeDesk turns the accepted Phi-4 Mini Graviton experiment into a practical
support-operations workflow. The public page exposes checked-in evidence
without AWS access; the local gateway adds live matched Arm64 requests and
fresh archive verification for the video.

## Run

```bash
python3.12 scripts/build_surgedesk_demo.py --verify
python3.12 scripts/serve_surgedesk.py --port 8765
```

Open `http://127.0.0.1:8765/surgedesk/`.

The triage screen exposes three deterministic evidence paths:

- **Straight-through:** the model and queue guard agree.
- **Guard intervention:** the guard repairs an incorrect direct LLM route.
- **Human correction:** the operator catches a guard error.

Direct links are available at `#triage`, `#surge`, and `#proof`.

## Workflow

1. **Triage:** inspect the held-out `86.75%` queue result, load a recorded
   Phi-4 intent, observe the queue guard rescue or error, then confirm or
   correct the proposed route.
2. **Capacity audit:** hand off from the support operator to the platform
   engineer, confirm two matched live Arm lanes, run the canonical audit, and
   inspect all twenty 500-second windows. The short request check is not used
   as performance evidence. The stable
   optimized pass at 0.56 r/s divided by the stable baseline failure at 0.28
   r/s proves at least 2.0x sustainable capacity. The 0.60 r/s optimized probe
   remains visible as a mixed result.
3. **Release gate:** inspect the matched Arm Performix causal experiment,
   nine-claim sustained ledger, authoritative
   verify-derive-bind-decide path, executed Arm path, quality boundary, exact
   deployment and reusable GitHub Action.

## Evidence Provenance

`scripts/build_surgedesk_demo.py` calls
`src/armproof/demo/surgedesk.py`, which uses ArmProof's shared
verify-derive-bind-decide architecture with the EXP009 sustained adapter, then joins:

- accepted BANKING77 quality inputs and recorded Phi-4 outputs;
- four sustained boundaries with five long-window outcomes each;
- a queue guard trained on 2,310 disjoint examples and evaluated on the frozen
  770-case quality set;
- the conservative sustained mixed-traffic lower bound and unstable next probe;
- quality, artifact size, PSS and direct KleidiAI summaries; and
- separately labeled short-window reproduction history plus enabled/disabled
  callchain evidence.

The generated `surgedesk/data.json` is checked into the repository for an
offline demo and clearly labeled as a recorded receipt. `--verify`
byte-compares it with a fresh derivation and fails CI if it drifts. When the
local gateway is running, the audit button streams actual derivation stages and
changes the proof state from **Recorded pass** to **Verified now** only after
the current audit succeeds.

## Integrity Boundary

- The sample picker replays recorded model outputs and is labeled accordingly.
- Editing a message disables lookup and produces an explicit error.
- Operational five-destination accuracy is 86.75%; fine-grained 77-intent accuracy is
  46.49%. The app therefore requires human confirmation.
- All claims are scoped to the pinned Phi-4 Mini workload, ONNX Runtime GenAI
  INT4 runtime and AWS Graviton4 `c8g.4xlarge`.
- The repository SHA-256 ledgers detect post-capture modification; they are not
  independent attestation of who produced the original evidence.

## Live Matched Arm64 Mode

Forward both measured services to localhost, then run:

```bash
python3.12 scripts/serve_surgedesk.py --port 8765 \
  --baseline-endpoint http://127.0.0.1:18001/infer \
  --optimized-endpoint http://127.0.0.1:18002/infer
```

The **Live matched Arm64 endpoint** control becomes available only after the gateway
reads both health records. It requires Arm64 architecture, the same
content-derived model identity, runtime version and thread count; exact
disjoint CPU affinities; and opposite values of `mlas.disable_kleidiai`.
Before each matched request, the gateway reads both health records again and
requires the inference response to carry the same runtime fingerprint. The
gateway accepts only bounded text, builds the
frozen intent prompt, calls the trusted endpoint with a 60-second timeout, and
applies the same local queue guard. Without verified endpoints, live mode
remains disabled and the public recorded-evidence path stays available.

The release-gate view can alter one byte in a temporary archive copy and run
the real outer-digest check. The repository evidence is never modified.

## Validate

```bash
make check
npm run test:logic
npm run test:ui
```

The browser suite covers guided scenarios, confirmation, correction,
edited-text rejection, matched live lanes, fresh audit verification, adoption
scaffolding, proof visibility, console errors and responsive tables down to
320 pixels.
