# Demo And Submission

## Message

> ArmProof catches Arm optimization pull requests that run on Graviton but are
> not actually accelerated by the required Arm path.

## Ninety-Second Judge Path

### 0-15 seconds: The Decision

Open a real repository PR migrating the Phi-4 service from PyTorch BF16 to INT4
ONNX Runtime GenAI with KleidiAI. Show the declared optimization contract.

### 15-40 seconds: Catch The False Claim

Show the run with KleidiAI disabled. The GitHub Check is red because `kai_*`
execution is absent and the Arm performance contract fails.

### 40-65 seconds: Prove The Optimization

Enable KleidiAI. Show the green check, fixed-SLO capacity result, preserved
quality, clean-instance reproduction and separate whole-stack versus
Arm-specific comparisons.

### 65-90 seconds: Reuse It

Open the report provenance, show the one-command reproduction and launch or
display the exact passing deployment manifest.

## Three-Minute Video

Add enough time to explain:

- why BF16-to-INT4 and KleidiAI on/off answer different questions;
- how the claim ledger fails closed;
- how PSS and capacity are measured;
- which artifacts another developer can reuse; and
- the limits of the evidence.

## Report Views

1. Decision and failed requirements.
2. Transformation and causal comparison map.
3. Fixed-SLO cloud capacity and queue behavior.
4. Quality and malformed-output inspection.
5. Arm environment, `kai_*` evidence and raw provenance.

## Submission Claim Rules

- Every number names its comparison and environment.
- "Verified by ArmProof" is allowed; "Arm certified" is not.
- Direct speed and PSS results remain distinct from the accepted server
  capacity comparison.
- Failed and inconclusive experiments remain visible.
- The report is a product artifact, not evidence by itself.

## Offline Backup

Ship the static report, short recorded terminal sequence, raw summary and
screenshots so judging does not depend on a live AWS instance or GitHub Action.
