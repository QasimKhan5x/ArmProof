"""Stable machine-readable policy output."""

from __future__ import annotations

from typing import Any

from armproof.domain import Decision


def decision_to_dict(decision: Decision) -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "passed": decision.passed,
        "claims": [
            {
                "claim_id": claim.claim_id,
                "status": claim.status.value,
                "reason_code": claim.reason_code,
                "observed": claim.observed,
                "threshold": claim.threshold,
            }
            for claim in decision.claims
        ],
    }
