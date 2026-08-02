"""Bind normalized treatment identities to the declarations in a contract."""

from __future__ import annotations

from typing import Iterable

from armproof.contracts.parser import Contract, ContractError
from armproof.domain import Comparison


def validate_comparison_identities(
    contract: Contract,
    comparisons: Iterable[Comparison],
) -> None:
    declared = {row.treatment_id: row for row in contract.treatments}
    for comparison in comparisons:
        observed = {
            comparison.baseline.treatment_id: comparison.baseline,
            comparison.treatment.treatment_id: comparison.treatment,
        }
        if set(observed) != set(declared):
            raise ContractError("comparison treatment IDs do not match the contract")
        for treatment_id, identity in observed.items():
            treatment = declared[treatment_id]
            for field in (
                "artifact_sha256",
                "runtime_sha256",
                "workload_sha256",
                "environment_sha256",
            ):
                if getattr(treatment, field) != getattr(identity, field):
                    raise ContractError(
                        f"comparison treatment {treatment_id} has mismatched {field}"
                    )
