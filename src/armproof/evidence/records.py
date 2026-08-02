"""Strict parser for normalized comparison evidence."""

from __future__ import annotations

import math
from types import MappingProxyType
from typing import Any, Mapping

from armproof.contracts.parser import SHA256_RE
from armproof.domain import CausalScope, Comparison, TreatmentIdentity


class EvidenceRecordError(ValueError):
    """Normalized evidence is malformed or carries unknown semantics."""


def _exact(payload: Mapping[str, Any], fields: set[str], where: str) -> None:
    unknown = set(payload) - fields
    missing = fields - set(payload)
    if unknown:
        raise EvidenceRecordError(f"{where} has unknown fields: {sorted(unknown)}")
    if missing:
        raise EvidenceRecordError(f"{where} is missing fields: {sorted(missing)}")


def _identity(payload: Any, where: str) -> TreatmentIdentity:
    if not isinstance(payload, Mapping):
        raise EvidenceRecordError(f"{where} must be an object")
    fields = {
        "treatment_id", "artifact_sha256", "runtime_sha256", "workload_sha256",
        "environment_sha256", "controls",
    }
    _exact(payload, fields, where)
    for field in ("artifact_sha256", "runtime_sha256", "workload_sha256", "environment_sha256"):
        value = payload[field]
        if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
            raise EvidenceRecordError(f"{where}.{field} must be a lowercase SHA-256 digest")
    if not isinstance(payload["controls"], Mapping):
        raise EvidenceRecordError(f"{where}.controls must be an object")
    if not isinstance(payload["treatment_id"], str) or not payload["treatment_id"]:
        raise EvidenceRecordError(f"{where}.treatment_id must be non-empty")
    return TreatmentIdentity(
        treatment_id=payload["treatment_id"],
        artifact_sha256=payload["artifact_sha256"],
        runtime_sha256=payload["runtime_sha256"],
        workload_sha256=payload["workload_sha256"],
        environment_sha256=payload["environment_sha256"],
        controls=MappingProxyType(dict(payload["controls"])),
    )


def parse_comparison(payload: Mapping[str, Any]) -> Comparison:
    if not isinstance(payload, Mapping):
        raise EvidenceRecordError("comparison must be an object")
    fields = {
        "schema_version", "comparison_id", "causal_scope", "baseline", "treatment",
        "metrics", "evidence_kinds", "arm_attribution",
    }
    _exact(payload, fields, "comparison")
    if payload["schema_version"] != "1.0.0":
        raise EvidenceRecordError("unsupported comparison schema_version")
    try:
        scope = CausalScope(payload["causal_scope"])
    except (TypeError, ValueError) as exc:
        raise EvidenceRecordError("unsupported causal_scope") from exc
    metrics = payload["metrics"]
    evidence_kinds = payload["evidence_kinds"]
    attribution = payload["arm_attribution"]
    if not isinstance(metrics, Mapping) or not all(
        isinstance(key, str)
        and isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        for key, value in metrics.items()
    ):
        raise EvidenceRecordError("metrics must contain finite numbers")
    if not isinstance(evidence_kinds, list) or not all(isinstance(item, str) for item in evidence_kinds):
        raise EvidenceRecordError("evidence_kinds must be a string array")
    if not isinstance(attribution, Mapping):
        raise EvidenceRecordError("arm_attribution must be an object")
    _exact(attribution, {"baseline_observed", "treatment_observed"}, "arm_attribution")
    for value in attribution.values():
        if value is not None and not isinstance(value, bool):
            raise EvidenceRecordError("arm attribution values must be boolean or null")
    comparison_id = payload["comparison_id"]
    if not isinstance(comparison_id, str) or not comparison_id:
        raise EvidenceRecordError("comparison_id must be non-empty")
    return Comparison(
        comparison_id=comparison_id,
        causal_scope=scope,
        baseline=_identity(payload["baseline"], "baseline"),
        treatment=_identity(payload["treatment"], "treatment"),
        metrics=MappingProxyType({key: float(value) for key, value in metrics.items()}),
        evidence_kinds=frozenset(evidence_kinds),
        arm_path_baseline_observed=attribution["baseline_observed"],
        arm_path_treatment_observed=attribution["treatment_observed"],
    )


def comparison_to_dict(comparison: Comparison) -> dict[str, Any]:
    def identity_to_dict(identity: TreatmentIdentity) -> dict[str, Any]:
        return {
            "treatment_id": identity.treatment_id,
            "artifact_sha256": identity.artifact_sha256,
            "runtime_sha256": identity.runtime_sha256,
            "workload_sha256": identity.workload_sha256,
            "environment_sha256": identity.environment_sha256,
            "controls": dict(identity.controls),
        }

    return {
        "schema_version": "1.0.0",
        "comparison_id": comparison.comparison_id,
        "causal_scope": comparison.causal_scope.value,
        "baseline": identity_to_dict(comparison.baseline),
        "treatment": identity_to_dict(comparison.treatment),
        "metrics": dict(comparison.metrics),
        "evidence_kinds": sorted(comparison.evidence_kinds),
        "arm_attribution": {
            "baseline_observed": comparison.arm_path_baseline_observed,
            "treatment_observed": comparison.arm_path_treatment_observed,
        },
    }
