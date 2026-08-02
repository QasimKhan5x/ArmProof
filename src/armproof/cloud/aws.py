"""Immutable AWS plans with a cumulative project budget barrier."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from typing import Any


# Frozen on-demand us-east-1 planning rates. The paid runner records a refreshed
# price before launch and must use the greater value for its final ledger.
INSTANCE_HOURLY_USD = {"c8g.2xlarge": 0.31904, "c8g.4xlarge": 0.63808}
GP3_GIB_MONTH_USD = 0.08
HARD_PROJECT_CEILING_USD = 15.0


@dataclass(frozen=True)
class AwsExperimentPlan:
    experiment_id: str
    region: str
    instance_type: str
    maximum_runtime_minutes: int
    volume_gib: int
    expires_at: str
    prior_spend_usd: float
    maximum_compute_cost_usd: float
    maximum_storage_cost_usd: float
    maximum_projected_total_usd: float
    tags: dict[str, str]

    def payload(self) -> dict[str, Any]:
        return asdict(self)

    def approval_token(self) -> str:
        encoded = json.dumps(self.payload(), sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()[:16]


def make_plan(
    experiment_id: str,
    *,
    instance_type: str = "c8g.4xlarge",
    region: str = "us-east-1",
    maximum_runtime_minutes: int = 120,
    volume_gib: int = 60,
    prior_spend_usd: float = 1.43,
    now: datetime | None = None,
) -> AwsExperimentPlan:
    if instance_type not in INSTANCE_HOURLY_USD:
        raise ValueError(f"instance type not allowed: {instance_type}")
    if not experiment_id.startswith("EXP-"):
        raise ValueError("experiment_id must start with EXP-")
    if not 1 <= maximum_runtime_minutes <= 360:
        raise ValueError("maximum_runtime_minutes must be between 1 and 360")
    if not 40 <= volume_gib <= 80:
        raise ValueError("volume_gib must be between 40 and 80")
    if prior_spend_usd < 0:
        raise ValueError("prior_spend_usd cannot be negative")

    current = now or datetime.now(UTC)
    expires = current + timedelta(minutes=maximum_runtime_minutes)
    compute = INSTANCE_HOURLY_USD[instance_type] * maximum_runtime_minutes / 60
    storage = GP3_GIB_MONTH_USD * volume_gib * maximum_runtime_minutes / (30 * 24 * 60)
    projected = prior_spend_usd + compute + storage
    if projected >= HARD_PROJECT_CEILING_USD:
        raise ValueError("planned cumulative spend reaches the hard project ceiling")
    expires_at = expires.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return AwsExperimentPlan(
        experiment_id=experiment_id,
        region=region,
        instance_type=instance_type,
        maximum_runtime_minutes=maximum_runtime_minutes,
        volume_gib=volume_gib,
        expires_at=expires_at,
        prior_spend_usd=round(prior_spend_usd, 4),
        maximum_compute_cost_usd=round(compute, 4),
        maximum_storage_cost_usd=round(storage, 4),
        maximum_projected_total_usd=round(projected, 4),
        tags={
            "Project": "ArmProof",
            "Experiment": experiment_id,
            "Owner": "QasimKhan",
            "ExpiresAt": expires_at,
        },
    )


def assert_approved(plan: AwsExperimentPlan, supplied_token: str | None) -> None:
    if supplied_token != plan.approval_token():
        raise PermissionError("execution refused: approval token does not match immutable plan")
    if plan.maximum_projected_total_usd >= HARD_PROJECT_CEILING_USD:
        raise PermissionError("execution refused: cumulative project budget ceiling reached")
