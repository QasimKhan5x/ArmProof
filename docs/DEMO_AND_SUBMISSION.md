# Demo And Submission

## Message

> SurgeDesk keeps a banking support queue responsive during a traffic surge by
> deploying a measured KleidiAI optimization on Graviton4. ArmProof proves the
> gain came from the Arm path and blocks unsupported releases.

## Ninety-Second Judge Path

### 0-25 seconds: Real Work

Open SurgeDesk on one live stolen-card request through the tunneled Graviton
endpoint. Show the two-stage route and confirm it. Then use recorded examples
to show one guard rescue and one human correction. State the held-out result:
86.75% queue accuracy, up 12.34 points from direct LLM mapping.

### 25-55 seconds: The Surge

Open **Surge replay**. The machine, model, runtime and 10-second p95 objective
stay fixed; only KleidiAI changes. At the same `0.267 requests/second`, show
three late customer tiles and 12.66s p95 disabled versus zero and 2.21s
enabled. Then reveal the confirmed sustainable boundary: 0.20 versus 0.60.

### 55-80 seconds: Why It Is Arm Optimization

Open **Release proof**. Show enabled-only `kai_*` callchains, the matched INT4
control, 1.72-2.59x direct execution gain, 2.5-3x capacity across all traffic
mixes and exact clean-machine reproduction.

### 80-90 seconds: Community Artifact

Show the executable adoption path and GitHub Action. ArmProof rejects missing
hashes, routing quality below 85%, absent Arm execution or an unmeasured
deployment, and emits the exact passing configuration.

## Three-Minute Video

Use the extra time to distinguish the 35.92% artifact-size reduction from the
KleidiAI-specific comparison, show one raw event, and run the one-command gate.
End on the application, not the report.

## Submission Claim Rules

- Every number names its comparison and environment.
- Label the single endpoint request live and all experiment playback recorded.
- Say "verified by ArmProof," never "Arm certified."
- Queue quality is 86.75%; 77-intent quality is 46.49%; human confirmation is
  mandatory and visible.
- Direct speed, whole-stack size/PSS and service capacity remain separate.
- Failed and inconclusive experiments remain preserved.

## Offline Backup

Ship `surgedesk/`, the generated data payload, screenshots, ArmProof report,
raw summary and checksummed evidence. Judging must not depend on AWS uptime or
a live GitHub workflow.
