# AWS Budget And Lifecycle

## Final Budget

- Hard project ceiling: USD 15 across all feasibility and product runs.
- Primary machine: `c8g.4xlarge` in `us-east-1`.
- Final conservative cumulative estimate: USD 13.4872.
- Accepted EXP-2026-013 Performix session: USD 0.0607. Its failed cold-import
  attempt cost USD 0.0393 and remains in the registry.
- Accepted EXP-2026-014 capacity confirmation: USD 1.0503.
- Every experiment used a plan-specific runtime and cost ceiling. All instances
  were terminated, temporary storage was removed, and the final inventory is
  empty.

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
