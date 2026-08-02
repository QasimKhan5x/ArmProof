"""Fail-closed parser for the ArmProof 1.0 contract mapping."""

from __future__ import annotations

import re
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

from armproof.domain import CausalScope, ClaimSpec


SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class ContractError(ValueError):
    """Contract input is incomplete, ambiguous, or unsupported."""


@dataclass(frozen=True)
class Treatment:
    treatment_id: str
    command: tuple[str, ...]
    artifact_sha256: str
    runtime_sha256: str
    workload_sha256: str
    environment_sha256: str
    environment: Mapping[str, str]


@dataclass(frozen=True)
class Contract:
    schema_version: str
    contract_id: str
    treatments: tuple[Treatment, ...]
    claims: tuple[ClaimSpec, ...]


def _exact_fields(payload: Mapping[str, Any], allowed: set[str], where: str) -> None:
    unknown = set(payload) - allowed
    if unknown:
        raise ContractError(f"{where} has unknown fields: {sorted(unknown)}")
    missing = allowed - set(payload)
    if missing:
        raise ContractError(f"{where} is missing fields: {sorted(missing)}")


def _digest(value: Any, field: str) -> str:
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        raise ContractError(f"{field} must be a lowercase SHA-256 digest")
    return value


def _treatment(payload: Any, index: int) -> Treatment:
    if not isinstance(payload, Mapping):
        raise ContractError(f"treatment {index} must be an object")
    fields = {
        "id", "command", "artifact_sha256", "runtime_sha256",
        "workload_sha256", "environment_sha256", "environment",
    }
    _exact_fields(payload, fields, f"treatment {index}")
    command = payload["command"]
    environment = payload["environment"]
    if not isinstance(command, list) or not command or not all(isinstance(v, str) and v for v in command):
        raise ContractError(f"treatment {index} command must be a non-empty string array")
    if not isinstance(environment, Mapping) or not all(
        isinstance(key, str) and isinstance(value, str) for key, value in environment.items()
    ):
        raise ContractError(f"treatment {index} environment must contain string pairs")
    treatment_id = payload["id"]
    if not isinstance(treatment_id, str) or not treatment_id:
        raise ContractError(f"treatment {index} id must be non-empty")
    return Treatment(
        treatment_id=treatment_id,
        command=tuple(command),
        artifact_sha256=_digest(payload["artifact_sha256"], "artifact_sha256"),
        runtime_sha256=_digest(payload["runtime_sha256"], "runtime_sha256"),
        workload_sha256=_digest(payload["workload_sha256"], "workload_sha256"),
        environment_sha256=_digest(payload["environment_sha256"], "environment_sha256"),
        environment=MappingProxyType(dict(environment)),
    )


def _claim(payload: Any, index: int) -> ClaimSpec:
    if not isinstance(payload, Mapping):
        raise ContractError(f"claim {index} must be an object")
    fields = {
        "id",
        "causal_scope",
        "comparison_id",
        "metric",
        "operator",
        "threshold",
        "required_evidence",
        "required",
        "depends_on",
    }
    _exact_fields(payload, fields, f"claim {index}")
    try:
        scope = CausalScope(payload["causal_scope"])
    except (ValueError, TypeError) as exc:
        raise ContractError(f"claim {index} has unsupported causal_scope") from exc
    if payload["operator"] not in {"gte", "lte", "gt", "lt", "eq"}:
        raise ContractError(f"claim {index} has unsupported operator")
    evidence = payload["required_evidence"]
    dependencies = payload["depends_on"]
    if not isinstance(evidence, list) or not all(isinstance(item, str) and item for item in evidence):
        raise ContractError(f"claim {index} required_evidence must be a string array")
    if not isinstance(dependencies, list) or not all(isinstance(item, str) and item for item in dependencies):
        raise ContractError(f"claim {index} depends_on must be a string array")
    threshold = payload["threshold"]
    if not isinstance(threshold, (int, float)) or isinstance(threshold, bool):
        raise ContractError(f"claim {index} threshold must be numeric")
    for field in ("id", "comparison_id", "metric"):
        if not isinstance(payload[field], str) or not payload[field]:
            raise ContractError(f"claim {index} {field} must be non-empty")
    if not isinstance(payload["required"], bool):
        raise ContractError(f"claim {index} required must be boolean")
    return ClaimSpec(
        claim_id=payload["id"],
        causal_scope=scope,
        comparison_id=payload["comparison_id"],
        metric=payload["metric"],
        operator=payload["operator"],
        threshold=float(threshold),
        required_evidence=frozenset(evidence),
        required=payload["required"],
        depends_on=tuple(dependencies),
    )


def parse_contract(payload: Mapping[str, Any]) -> Contract:
    if not isinstance(payload, Mapping):
        raise ContractError("contract must be an object")
    _exact_fields(payload, {"schema_version", "contract_id", "treatments", "claims"}, "contract")
    if payload["schema_version"] != "1.0.0":
        raise ContractError("unsupported schema_version")
    if not isinstance(payload["contract_id"], str) or not payload["contract_id"]:
        raise ContractError("contract_id must be non-empty")
    if not isinstance(payload["treatments"], list) or len(payload["treatments"]) < 2:
        raise ContractError("contract requires at least two treatments")
    if not isinstance(payload["claims"], list) or not payload["claims"]:
        raise ContractError("contract requires at least one claim")
    treatments = tuple(_treatment(item, index) for index, item in enumerate(payload["treatments"]))
    claims = tuple(_claim(item, index) for index, item in enumerate(payload["claims"]))
    treatment_ids = [item.treatment_id for item in treatments]
    if len(treatment_ids) != len(set(treatment_ids)):
        raise ContractError("duplicate treatment id")
    claim_ids = [item.claim_id for item in claims]
    if len(claim_ids) != len(set(claim_ids)):
        raise ContractError("duplicate claim id")
    if not any(item.required for item in claims):
        raise ContractError("contract requires at least one required claim")
    unknown_dependencies = {
        dependency for item in claims for dependency in item.depends_on if dependency not in claim_ids
    }
    if unknown_dependencies:
        raise ContractError(f"unknown claim dependencies: {sorted(unknown_dependencies)}")
    claim_index = {item.claim_id: item for item in claims}
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(claim_id: str) -> None:
        if claim_id in visiting:
            raise ContractError(f"claim dependency cycle includes {claim_id}")
        if claim_id in visited:
            return
        visiting.add(claim_id)
        for dependency in claim_index[claim_id].depends_on:
            visit(dependency)
        visiting.remove(claim_id)
        visited.add(claim_id)

    for claim_id in claim_index:
        visit(claim_id)
    return Contract(
        schema_version="1.0.0",
        contract_id=payload["contract_id"],
        treatments=treatments,
        claims=claims,
    )
