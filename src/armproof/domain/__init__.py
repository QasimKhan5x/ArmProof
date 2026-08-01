"""Immutable domain records shared by collectors, policy, and presenters."""

from armproof.domain.models import (
    CausalScope,
    ClaimResult,
    ClaimSpec,
    ClaimStatus,
    Comparison,
    Decision,
    TreatmentIdentity,
)

__all__ = [
    "CausalScope",
    "ClaimResult",
    "ClaimSpec",
    "ClaimStatus",
    "Comparison",
    "Decision",
    "TreatmentIdentity",
]

