#!/usr/bin/env python3
"""Plan or execute the preregistered Code Hotspots confirmation."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from armproof.cloud import execute_aws_run, make_plan


# Uses the maximum projected EXP-2026-012 total so this plan remains safe even
# when the capacity confirmation consumes its full watchdog allowance.
PRIOR_SPEND_USD = 12.3369
EXPERIMENT_TOKEN = "exp-2026-013-performix-confirmation"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan-started-at", required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--approval-token")
    parser.add_argument("--profile", default="kleidiscope-runner")
    parser.add_argument(
        "--performix-cli", type=Path,
        default=Path("/tmp/ArmPerformix-cli-linux-arm64.tar.gz"),
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[3]
    started = datetime.fromisoformat(args.plan_started_at.replace("Z", "+00:00"))
    plan = make_plan(
        "EXP-2026-013", instance_type="c8g.4xlarge", region="us-east-1",
        maximum_runtime_minutes=40, volume_gib=60,
        prior_spend_usd=PRIOR_SPEND_USD, now=started,
    )
    if not args.execute:
        print(json.dumps({
            "plan": plan.payload(), "approval_token": plan.approval_token()
        }, indent=2, sort_keys=True))
        return 0
    if args.approval_token != plan.approval_token():
        raise SystemExit("approval token does not match this immutable plan")

    import boto3

    assets = {
        "RUNTIME_CHECKPOINTS": root.parent / "result-first-bakeoff/evidence/checkpoints/runtime-checkpoints.tar.gz",
        "PERFORMIX_CLI": args.performix_cli,
    }
    for path in assets.values():
        if not path.is_file():
            raise SystemExit(f"immutable prerequisite missing: {path}")
    result = execute_aws_run(
        session=boto3.Session(profile_name=args.profile, region_name=plan.region),
        plan=plan,
        approval_token=args.approval_token,
        experiment_token=EXPERIMENT_TOKEN,
        project=root,
        output_dir=root / "ops/evidence/EXP-2026-013",
        guest_template=root / "ops/aws/performix-001/guest.sh",
        immutable_assets=assets,
        poll_seconds=15,
    )
    print(json.dumps(result.__dict__, indent=2, sort_keys=True))
    return 0 if result.terminated and result.cleanup_complete else 2


if __name__ == "__main__":
    raise SystemExit(main())
