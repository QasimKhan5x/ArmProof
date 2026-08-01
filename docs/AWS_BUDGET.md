# AWS Budget And Lifecycle

## Budget

- Target additional spend: USD 2-4.
- Hard project ceiling: USD 15 total across all feasibility and product runs.
- Prior feasibility spend carried into every plan: approximately USD 1.43.
- Primary instance: one `c8g.4xlarge` in `us-east-1`.
- Capacity run: 60-90 minutes expected, two-hour hard stop.
- Final reproduction: one additional bounded session.
- Actual accepted cumulative evidence cost after reproduction: USD 3.8689.

Prices must be refreshed before launch and recorded in the spend ledger.

## Approval Boundary

The owner granted standing approval on 2026-07-31 for minimal AWS use within
the all-in USD 15 ceiling. Every paid run still requires a plan-specific token
derived from the immutable plan. The software enforces the cumulative ceiling;
routine execution does not require another owner round trip.

## Required Controls

- Least-privilege IAM user, role or SSO session; never account-root keys.
- Tags: `Project=ArmProof`, `Experiment=<id>`, `Owner=QasimKhan`, and an expiry.
- Encrypted gp3 volume with delete-on-termination.
- No public inbound access unless the experiment requires it and the source is
  restricted.
- Instance-side timeout and controller-side watchdog.
- Cleanup in success, failure, timeout and interrupted paths.
- Before/after inventories for instances, volumes, snapshots, addresses and
  temporary object storage.

## Session Procedure

1. Verify credentials are non-root.
2. Inventory relevant resources.
3. Render dry-run plan and maximum cost.
4. Verify the plan-specific token and cumulative budget gate.
5. Launch one tagged instance.
6. Restore checksummed artifacts rather than rebuilding when possible.
7. Run only the preregistered experiment.
8. Download evidence and verify checksums.
9. Terminate and delete temporary resources.
10. Record final inventory, lifetime and estimated spend.

## Stop Conditions

Stop immediately for root credentials, unexpected resources, artifact hash
mismatch, missing cleanup path, approaching timeout, unplanned instance type,
or projected ceiling breach.
