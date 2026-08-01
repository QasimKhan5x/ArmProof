"""Workload-specific quality adapters."""

from armproof.quality.banking77 import (
    QualityCase,
    QualityComparison,
    QualityResult,
    compare_quality,
    evaluate_quality,
    load_quality_cases,
    quality_from_dict,
    quality_to_dict,
)
from armproof.quality.ort_batch import run_ort_batched_quality

__all__ = [
    "QualityCase",
    "QualityComparison",
    "QualityResult",
    "compare_quality",
    "evaluate_quality",
    "load_quality_cases",
    "quality_from_dict",
    "quality_to_dict",
    "run_ort_batched_quality",
]
