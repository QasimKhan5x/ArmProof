"""Core value objects. They contain no collection or presentation behavior."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping


class CausalScope(str, Enum):
    ARTIFACT = "artifact"
    ARM_ACCELERATION = "arm_acceleration"
    WHOLE_DEPLOYMENT = "whole_deployment"
    CLOUD_CAPACITY = "cloud_capacity"
    OVERHEAD = "overhead"
    REPRODUCTION = "reproduction"


class ClaimStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True)
class TreatmentIdentity:
    treatment_id: str
    artifact_sha256: str
    runtime_sha256: str
    workload_sha256: str
    environment_sha256: str
    controls: Mapping[str, Any]


@dataclass(frozen=True)
class Comparison:
    comparison_id: str
    causal_scope: CausalScope
    baseline: TreatmentIdentity
    treatment: TreatmentIdentity
    metrics: Mapping[str, float]
    evidence_kinds: frozenset[str]
    arm_path_baseline_observed: bool | None = None
    arm_path_treatment_observed: bool | None = None


@dataclass(frozen=True)
class ClaimSpec:
    claim_id: str
    causal_scope: CausalScope
    comparison_id: str
    metric: str
    operator: str
    threshold: float
    required_evidence: frozenset[str]
    required: bool
    depends_on: tuple[str, ...] = ()


@dataclass(frozen=True)
class ClaimResult:
    claim_id: str
    status: ClaimStatus
    reason_code: str
    observed: float | None
    threshold: float


@dataclass(frozen=True)
class Decision:
    passed: bool
    claims: tuple[ClaimResult, ...]

