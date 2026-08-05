# Demo And Submission

The canonical submission package is [`../submission/README.md`](../submission/README.md).

## Message

> SurgeDesk keeps a banking-support queue responsive during a traffic surge by
> deploying a measured KleidiAI optimization on Graviton4. ArmProof proves the
> gain came from the executed Arm path and blocks unsupported releases.

## Canonical Artifacts

- Copy-ready Devpost entry: [`../submission/DEVPOST_SUBMISSION.md`](../submission/DEVPOST_SUBMISSION.md)
- Under-three-minute script: [`../submission/DEMO_SCRIPT.md`](../submission/DEMO_SCRIPT.md)
- Judge setup and validation: [`../submission/JUDGE_GUIDE.md`](../submission/JUDGE_GUIDE.md)
- Claim-to-evidence map: [`../submission/TECHNICAL_EVIDENCE.md`](../submission/TECHNICAL_EVIDENCE.md)
- Upload-ready images: [`../submission/assets/`](../submission/assets/)
- Final owner checklist: [`../submission/SUBMISSION_CHECKLIST.md`](../submission/SUBMISSION_CHECKLIST.md)

The recording starts with a message typed into the live support application.
After that request is routed through the control service, the app recomputes
the accepted release decision from the published capacity, quality, and native
Arm Performix evidence. That decision unlocks the measured KleidiAI treatment,
and a second typed message is routed through the newly activated service.

## Submission Claim Rules

- Every number names its comparison and environment.
- Label endpoint output live only when the gateway has verified the Arm64 runtime identity.
- Say "verified by ArmProof," never "Arm certified."
- Queue quality is 86.75%; 77-intent quality is 46.49%; human confirmation is
  mandatory and visible.
- Direct speed, whole-stack size/PSS and service capacity remain separate.
- The queue guard is product quality work, not an Arm speedup.
- Failed and inconclusive experiments remain preserved.

## Offline Backup

The repository ships `surgedesk/`, the generated data payload, screenshots,
the ArmProof report, derived summaries, verification receipt, and the evidence
used to produce the release decision. If the recording host is unavailable,
the public explorer opens that checked-in receipt and preserves the same order:
support request, measured release decision, Arm execution evidence, deployment
identity, and developer adoption path. The backup does not simulate inference,
capacity traffic, or a release failure.
