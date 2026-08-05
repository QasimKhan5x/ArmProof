# Devpost Media Assets

Upload these in order from `submission/assets/`:

1. `01-live-shadow.png` - cover image. One customer message reaches the current
   service and the optimized Arm candidate, with fresh request receipts and an
   explicit shadow-only label.
2. `02-capacity-result.png` - the release decision re-derived from ten long
   traffic windows, application quality, and the conservative capacity bound.
3. `03-release-proof.png` - the guarded traffic switch, deployment identity,
   Arm Performix samples, and observed Neoverse I8MM kernel.
4. `04-live-cutover.png` - two different customer requests before and after the
   release, routed by the standard and optimized services respectively.

Suggested captions:

- **A live Arm candidate earns its release.** SurgeDesk first sends a real
  request to the current Graviton4 service and then to the optimized candidate
  as a shadow copy. ArmProof still keeps the candidate away from customers
  until sustained evidence passes.
- **The release rests on a measured boundary.** The standard service failed all
  five long windows at 0.28 requests/s; the KleidiAI service passed all five at
  0.56 requests/s, establishing at least twice the sustainable capacity while
  operational queue accuracy remained 86.75%.
- **The Arm path is visible.** The gateway validates the deployed artifacts and
  placement, while Arm Performix attributes 245,876 of 365,062 treatment
  samples to `kai_*`, including the Neoverse I8MM matrix kernel.
- **The result changes a real workflow.** A stolen-card message is handled by
  the standard route before release. A different expiring-card request is
  handled by the optimized route afterward, and both remain human-confirmed.

Do not use raw profiler text as the cover image. It remains available in the
repository for technical inspection.
