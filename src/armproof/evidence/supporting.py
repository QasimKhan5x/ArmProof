"""Re-derive supporting EXP-2026-002 optimization measurements."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from statistics import median
from typing import Any


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"supporting evidence is not an object: {path.name}")
    return value


def _reduction(reference: float, treatment: float) -> float:
    if reference <= 0 or treatment <= 0:
        raise ValueError("supporting size and memory values must be positive")
    return (1 - treatment / reference) * 100


def _recomputed_median_seconds(shape: dict[str, Any]) -> float:
    rows = shape.get("rows")
    repetitions = shape.get("repetitions")
    if (
        not isinstance(rows, list)
        or not isinstance(repetitions, int)
        or isinstance(repetitions, bool)
        or repetitions < 3
        or len(rows) != repetitions
    ):
        raise ValueError("supporting direct-inference repetitions are incomplete")
    values: list[float] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("supporting direct-inference row is invalid")
        value = row.get("end_to_end_seconds")
        if (
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or not math.isfinite(float(value))
            or value <= 0
        ):
            raise ValueError("supporting direct-inference time is invalid")
        values.append(float(value))
    observed = median(values)
    stored = shape.get("median", {}).get("end_to_end_seconds")
    if not isinstance(stored, (int, float)) or not math.isclose(
        observed, float(stored), rel_tol=1e-12, abs_tol=1e-12
    ):
        raise ValueError("supporting stored median disagrees with raw repetitions")
    return observed


def derive_supporting_optimization(root: Path, lock_path: Path) -> dict[str, Any]:
    lock = _json(lock_path)
    expected = lock.get("files")
    required = {"bf16.json", "ort-disabled.json", "ort-enabled.json", "summary.json"}
    if (
        lock.get("schema_version") != "1.0.0"
        or lock.get("experiment_id") != "EXP-2026-002"
        or not isinstance(expected, dict)
        or set(expected) != required
    ):
        raise ValueError("supporting evidence lock is invalid")
    for name, digest in expected.items():
        path = root / name
        if not path.is_file() or _sha256(path) != digest:
            raise ValueError(f"supporting evidence digest mismatch: {name}")

    bf16 = _json(root / "bf16.json")
    disabled = _json(root / "ort-disabled.json")
    enabled = _json(root / "ort-enabled.json")
    stored = _json(root / "summary.json").get("summary")
    if not isinstance(stored, dict):
        raise ValueError("supporting summary is invalid")
    disabled_shapes = disabled.get("performance")
    enabled_shapes = enabled.get("performance")
    if (
        not isinstance(disabled_shapes, list)
        or not isinstance(enabled_shapes, list)
        or len(disabled_shapes) != 4
        or len(enabled_shapes) != 4
    ):
        raise ValueError("supporting direct-inference matrix must contain four shapes")

    gains: list[float] = []
    shapes: list[dict[str, Any]] = []
    for control, treatment in zip(disabled_shapes, enabled_shapes, strict=True):
        identity = (control.get("batch"), control.get("prompt_length"))
        if identity != (treatment.get("batch"), treatment.get("prompt_length")):
            raise ValueError("supporting direct-inference shapes are not matched")
        gain = _recomputed_median_seconds(control) / _recomputed_median_seconds(
            treatment
        )
        gains.append(gain)
        shapes.append({"batch": identity[0], "prompt_length": identity[1], "speedup": gain})

    result = {
        "experiment_id": "EXP-2026-002",
        "checksummed_files": len(required),
        "disk_reduction_percent": _reduction(
            float(bf16["model_bytes"]), float(enabled["model_bytes"])
        ),
        "peak_pss_reduction_percent": _reduction(
            float(bf16["memory"]["peak_pss_bytes"]),
            float(enabled["memory"]["peak_pss_bytes"]),
        ),
        "weighted_pss_reduction_percent": _reduction(
            float(bf16["memory"]["time_weighted_pss_bytes"]),
            float(enabled["memory"]["time_weighted_pss_bytes"]),
        ),
        "migration_bf16_quality_correct": int(bf16["quality"]["correct"]),
        "migration_int4_quality_correct": int(enabled["quality"]["correct"]),
        "migration_quality_total": int(enabled["quality"]["total"]),
        "direct_shape_gains": gains,
        "direct_shapes": shapes,
    }
    comparisons = {
        "disk_reduction_percent": result["disk_reduction_percent"],
        "peak_pss_reduction_percent": result["peak_pss_reduction_percent"],
        "weighted_pss_reduction_percent": result["weighted_pss_reduction_percent"],
        "kleidiai_shape_gains": result["direct_shape_gains"],
    }
    for key, observed in comparisons.items():
        recorded = stored.get(key)
        observed_values = observed if isinstance(observed, list) else [observed]
        recorded_values = recorded if isinstance(recorded, list) else [recorded]
        if len(observed_values) != len(recorded_values) or any(
            not math.isclose(float(left), float(right), rel_tol=1e-12)
            for left, right in zip(observed_values, recorded_values, strict=True)
        ):
            raise ValueError(f"supporting summary disagrees with raw measurements: {key}")
    return result


def verified_deployment_summary(
    summary_path: Path,
    *,
    evidence_root: Path,
    lock_path: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return a deployment summary whose visible metrics were re-derived."""
    derived = derive_supporting_optimization(evidence_root, lock_path)
    summary = _json(summary_path)
    expected_metrics = {
        "disk_reduction_percent": derived["disk_reduction_percent"],
        "peak_pss_reduction_percent": derived["peak_pss_reduction_percent"],
        "weighted_pss_reduction_percent": derived["weighted_pss_reduction_percent"],
        "minimum_kleidiai_speedup": min(derived["direct_shape_gains"]),
        "maximum_kleidiai_speedup": max(derived["direct_shape_gains"]),
    }
    metrics = summary.get("metrics")
    if (
        summary.get("schema_version") != "1.0.0"
        or summary.get("experiment_id") != derived["experiment_id"]
        or not isinstance(metrics, dict)
        or set(metrics) != set(expected_metrics)
    ):
        raise ValueError("deployment summary does not match the supporting evidence schema")
    for name, observed in expected_metrics.items():
        if not math.isclose(
            float(metrics[name]), float(observed), rel_tol=1e-12, abs_tol=1e-12
        ):
            raise ValueError(
                f"deployment summary metric {name} disagrees with rederived evidence"
            )
    verified = dict(summary)
    verified["metrics"] = expected_metrics
    verified["metric_source"] = {
        "experiment_id": derived["experiment_id"],
        "checksummed_files": derived["checksummed_files"],
        "derivation": "locked_aggregate_footprint_and_raw_timing_repetitions",
    }
    return verified, derived
