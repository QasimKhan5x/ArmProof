# Final Submission Checklist

## Already Complete

- [x] Public source repository.
- [x] MIT license at repository root.
- [x] Track 2 Cloud AI alignment.
- [x] Copy-ready overview, functionality and setup instructions.
- [x] Exact baseline, treatment and Arm-specific control documented.
- [x] Raw checksummed evidence and normalized decisions included.
- [x] Negative fixtures demonstrate fail-closed behavior.
- [x] Native Arm64, x86 and browser CI.
- [x] Third-party dataset attribution and license notice.
- [x] Free local judging path without AWS credentials.
- [x] Public GitHub Pages workflow and judge URLs.
- [x] Devpost image selection and captions.
- [x] Under-three-minute recording script.

## Owner Actions

- [ ] Confirm the GitHub repository About section shows the MIT license.
- [ ] Confirm https://qasimkhan5x.github.io/ArmProof/surgedesk/ works in a
  logged-out browser.
- [ ] Record the video from [`DEMO_SCRIPT.md`](DEMO_SCRIPT.md).
- [ ] Upload it publicly to YouTube or Vimeo with embedding enabled.
- [ ] Replace the video placeholder in [`DEVPOST_SUBMISSION.md`](DEVPOST_SUBMISSION.md).
- [ ] Upload the four images in [`ASSET_CHECKLIST.md`](ASSET_CHECKLIST.md).
- [ ] Paste the submission text and select **Cloud AI**.
- [ ] Add only actual team members and confirm the authorized representative.
- [ ] Confirm the project was built or significantly updated during the
  submission period.
- [ ] Test every Devpost link while logged out.
- [ ] Submit before August 14, 2026 at 4:00 PM PDT.
- [ ] Reopen the submitted project and verify formatting, video playback and
  repository visibility.

## Final Claim Audit

- [ ] Every percentage identifies its comparison.
- [ ] KleidiAI claims use the matched INT4 enabled/disabled control.
- [ ] BF16-to-INT4 claims are not presented as KleidiAI gains.
- [ ] Queue-guard quality is not presented as an Arm speedup.
- [ ] Recorded evidence is labeled and not called live inference.
- [ ] ArmProof is not described as Arm certification.
- [ ] The at-least-2x result is scoped to the pinned Graviton4 deployment and SLO.
- [ ] The 2.33x number is labeled a tested pass-point ratio, not exact capacity.
- [ ] The rejected original 2.5x bracket remains visible.
