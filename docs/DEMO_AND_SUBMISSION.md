# Demo And Submission

## Message

> SurgeDesk keeps a banking support queue responsive during a traffic surge by
> deploying a measured KleidiAI optimization on Graviton4. ArmProof proves the
> gain came from the Arm path and blocks unsupported releases.

## Ninety-Second Judge Path

### 0-25 seconds: Real Work

Open SurgeDesk on a stolen-card request. Load the recorded Phi-4 Mini route,
show the account-security procedure and have the operator confirm it. Load the
known misroute and correct it. State that the model assists; a human decides.

### 25-55 seconds: The Surge

Open **Surge replay**. The machine, model, runtime and 10-second p95 objective
stay fixed; only KleidiAI changes. Replay raw confirmation events. The disabled
control fails at 0.267 requests/second while the enabled treatment passes at
0.600. Reveal the measured sustainable boundary: 0.20 versus 0.60, or 3x.

### 55-80 seconds: Why It Is Arm Optimization

Open **Release proof**. Show enabled-only `kai_*` callchains, the matched INT4
control, 1.72-2.59x direct execution gain, 2.5-3x capacity across all traffic
mixes and exact clean-machine reproduction.

### 80-90 seconds: Community Artifact

Show the GitHub Action. ArmProof rejects missing hashes, quality regression,
absent Arm execution or an unmeasured deployment, and emits the exact passing
configuration.

## Three-Minute Video

Use the extra time to distinguish the 35.92% artifact-size reduction from the
KleidiAI-specific comparison, show one raw event, and run the one-command gate.
End on the application, not the report.

## Submission Claim Rules

- Every number names its comparison and environment.
- Say "recorded replay," never imply that the static demo is calling AWS live.
- Say "verified by ArmProof," never "Arm certified."
- Absolute quality is 46.49%; human confirmation is mandatory and visible.
- Direct speed, whole-stack size/PSS and service capacity remain separate.
- Failed and inconclusive experiments remain preserved.

## Offline Backup

Ship `surgedesk/`, the generated data payload, screenshots, ArmProof report,
raw summary and checksummed evidence. Judging must not depend on AWS uptime or
a live GitHub workflow.
