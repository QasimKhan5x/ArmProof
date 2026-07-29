# AWS Budget And Cost Controls

## Approved Planning Envelope

- Expected total AWS spend: **USD 8-9**.
- Hard project ceiling without new owner approval: **USD 15**.
- Primary instance: `c8g.2xlarge` in `us-east-1`.
- Fallback: `c8g.4xlarge` only after measured memory pressure or when a final
  run demonstrates lower cost-to-completion.
- Pricing must be rechecked in the AWS calculator immediately before launch.

Planning rate as of 2026-07-29:

- `c8g.2xlarge`: approximately USD 0.319/hour On-Demand.
- `c8g.4xlarge`: approximately USD 0.638/hour On-Demand.

These are planning values, not permanent constants.

## Planned Runtime

| Activity | c8g.2xlarge hours | Planning cost |
|---|---:|---:|
| Native build and trace smoke test | 2 | $0.64 |
| Baseline trace/profile matrix | 3 | $0.96 |
| Candidate generation | 4 | $1.28 |
| Quality and performance evaluation | 5 | $1.60 |
| Final repeated benchmark | 4 | $1.28 |
| Contingency | 6 | $1.91 |
| Compute subtotal | 24 | $7.66 |

Allow $0.25-$0.75 for short-lived gp3 storage, public IPv4, and minor transfer.

## Before Launch

The agent must present and the owner must approve:

- instance type, region, current hourly price, and maximum runtime;
- storage size and estimated prorated price;
- exact experiment ID and command;
- expected artifact destination;
- automatic shutdown and cleanup mechanism;
- current cumulative project spend.

No approval may be inferred from an earlier general discussion.

## Required Resource Controls

- Tag every resource with `Project=KleidiScope`, `Experiment=<id>`,
  `Owner=QasimKhan`, and `ExpiresAt=<UTC timestamp>`.
- Use On-Demand for final benchmark evidence; Spot may be used only for
  non-headline dry runs with interruption-aware scripts.
- Attach the smallest practical gp3 root volume, initially 40-50 GB.
- Do not create a NAT gateway, load balancer, database, snapshot, reserved
  instance, Savings Plan, or persistent Elastic IP.
- Restrict SSH ingress to the current owner IP or use an approved managed
  access path.
- Install a local watchdog and instance-side shutdown timer.
- The experiment script must terminate on success, failure, timeout, and
  quality-gate failure after evidence upload.
- Budget alerts are warnings, not hard enforcement; TTL automation is the
  primary control.

## Local-First Cost Reduction

Do locally or on free standard GitHub Arm64 runners:

- implementation and unit tests;
- report design and browser testing with fixtures;
- schema and command validation;
- source analysis and patch review;
- model/data download verification;
- orchestration dry runs;
- Arm64 compile checks;
- experiment preregistration.

AWS is reserved for hardware truth: native build, runtime trace, Arm kernel
coverage, real candidate generation when needed, and controlled benchmarks.

## Spend Ledger

Every experiment record includes:

- launch and termination timestamps;
- instance/volume/resource IDs;
- expected and actual runtime;
- estimated compute, storage, IPv4, and transfer cost;
- cumulative project estimate;
- cleanup verification timestamp.

The owner should verify the Billing console after each cloud session.

## Stop Rules

Terminate immediately when:

- the predeclared experiment completes;
- the watchdog reaches six hours for one session;
- required model/data/build prerequisites fail;
- projected cumulative cost exceeds $12, preserving $3 emergency margin;
- an unplanned resource appears;
- results can no longer satisfy the experiment's decision gate.

Crossing the $15 ceiling requires a new written budget and owner approval.

