"""Compare a clean reproduction against an accepted capacity summary."""

from __future__ import annotations

from typing import Any, Mapping


def compare_reproduction(
    reference: Mapping[str, Any],
    reproduction: Mapping[str, Any],
    *,
    maximum_relative_difference: float = 0.10,
) -> dict[str, Any]:
    if not 0 <= maximum_relative_difference < 1:
        raise ValueError("maximum_relative_difference must be in [0, 1)")
    rows: dict[str, dict[str, Any]] = {}
    for mix in ("short", "long", "mixed"):
        try:
            expected = float(reference["mixes"][mix]["ratio"]["ratio"])
            observed = float(reproduction["mixes"][mix]["ratio"]["ratio"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"missing capacity ratio for {mix}") from exc
        if expected <= 0 or observed <= 0:
            raise ValueError(f"capacity ratios must be positive for {mix}")
        relative_difference = abs(observed - expected) / expected
        rows[mix] = {
            "reference_ratio": expected,
            "reproduction_ratio": observed,
            "relative_difference": relative_difference,
            "within_tolerance": relative_difference <= maximum_relative_difference,
        }
    reproduction_gate_passed = reproduction.get("passed") is True
    return {
        "schema_version": "1.0.0",
        "maximum_relative_difference": maximum_relative_difference,
        "mixes": rows,
        "reproduction_gate_passed": reproduction_gate_passed,
        "passed": reproduction_gate_passed and all(
            row["within_tolerance"] for row in rows.values()
        ),
    }
