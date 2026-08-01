"""Deterministic BANKING77 exact-intent quality evaluation."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

from armproof.workload import RequestInput, RequestSample


@dataclass(frozen=True)
class QualityCase:
    request: RequestInput
    expected_intent: str
    source_text: str


@dataclass(frozen=True)
class QualityRow:
    request_id: str
    expected_intent: str
    predicted_intent: str | None
    schema_valid: bool
    correct: bool
    error: str | None


@dataclass(frozen=True)
class QualityResult:
    total: int
    correct: int
    schema_valid: int
    missing: int
    accuracy: float
    macro_f1: float
    schema_valid_rate: float
    rows: tuple[QualityRow, ...]


@dataclass(frozen=True)
class QualityComparison:
    accuracy_delta_pp: float
    macro_f1_delta_pp: float
    schema_valid_rate: float
    prediction_agreement: float


def load_quality_cases(path: Path) -> list[QualityCase]:
    cases = []
    seen: set[str] = set()
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid quality JSON on line {line_number}: {exc}") from exc
        required = {"request_id", "payload", "expected_intent", "source_text"}
        if not isinstance(row, dict) or set(row) != required:
            raise ValueError(f"invalid quality row fields on line {line_number}")
        request_id = row["request_id"]
        if not isinstance(request_id, str) or not request_id or request_id in seen:
            raise ValueError(f"invalid or duplicate quality request_id on line {line_number}")
        if not isinstance(row["payload"], dict):
            raise ValueError(f"invalid payload on line {line_number}")
        if not isinstance(row["expected_intent"], str) or not isinstance(row["source_text"], str):
            raise ValueError(f"invalid quality labels on line {line_number}")
        seen.add(request_id)
        cases.append(
            QualityCase(
                RequestInput(request_id, row["payload"]),
                row["expected_intent"],
                row["source_text"],
            )
        )
    if not cases:
        raise ValueError("quality dataset contains no cases")
    return cases


_JSON_FENCE = re.compile(r"^```(?:json)?\s*\n(?P<body>.*)\n```$", re.DOTALL | re.IGNORECASE)


def _parse_intent(output: Any, valid_intents: set[str]) -> tuple[str | None, bool, str | None]:
    if not isinstance(output, str):
        return None, False, "output_missing"
    normalized = output.strip()
    fenced = _JSON_FENCE.fullmatch(normalized)
    if fenced:
        normalized = fenced.group("body").strip()
    try:
        payload = json.loads(normalized)
    except json.JSONDecodeError:
        return None, False, "malformed_json"
    if not isinstance(payload, dict) or set(payload) != {"intent"} or not isinstance(payload["intent"], str):
        return None, False, "schema_mismatch"
    intent = payload["intent"]
    if intent not in valid_intents:
        return None, True, "unknown_intent"
    return intent, True, None


def _macro_f1(rows: Sequence[QualityRow], labels: set[str]) -> float:
    scores = []
    for label in sorted(labels):
        true_positive = sum(row.expected_intent == label and row.predicted_intent == label for row in rows)
        false_positive = sum(row.expected_intent != label and row.predicted_intent == label for row in rows)
        false_negative = sum(row.expected_intent == label and row.predicted_intent != label for row in rows)
        denominator = 2 * true_positive + false_positive + false_negative
        scores.append(2 * true_positive / denominator if denominator else 0.0)
    return sum(scores) / len(scores)


def evaluate_quality(cases: Sequence[QualityCase], samples: Iterable[RequestSample]) -> QualityResult:
    sample_index: dict[str, RequestSample] = {}
    for sample in samples:
        if sample.request_id in sample_index:
            raise ValueError(f"duplicate sample: {sample.request_id}")
        sample_index[sample.request_id] = sample
    expected_ids = {case.request.request_id for case in cases}
    unexpected = set(sample_index) - expected_ids
    if unexpected:
        raise ValueError(f"unexpected samples: {sorted(unexpected)[:3]}")
    labels = {case.expected_intent for case in cases}
    rows = []
    missing = 0
    for case in cases:
        sample = sample_index.get(case.request.request_id)
        if sample is None:
            missing += 1
            rows.append(QualityRow(case.request.request_id, case.expected_intent, None, False, False, "missing"))
            continue
        if not sample.accepted or sample.response is None:
            rows.append(QualityRow(case.request.request_id, case.expected_intent, None, False, False, sample.error or "request_failed"))
            continue
        predicted, schema_valid, error = _parse_intent(sample.response.get("output"), labels)
        rows.append(
            QualityRow(
                case.request.request_id,
                case.expected_intent,
                predicted,
                schema_valid,
                predicted == case.expected_intent,
                error,
            )
        )
    total = len(rows)
    correct = sum(row.correct for row in rows)
    schema_valid = sum(row.schema_valid for row in rows)
    return QualityResult(
        total=total,
        correct=correct,
        schema_valid=schema_valid,
        missing=missing,
        accuracy=correct / total,
        macro_f1=_macro_f1(rows, labels),
        schema_valid_rate=schema_valid / total,
        rows=tuple(rows),
    )


def quality_to_dict(result: QualityResult) -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "total": result.total,
        "correct": result.correct,
        "schema_valid": result.schema_valid,
        "missing": result.missing,
        "accuracy": result.accuracy,
        "macro_f1": result.macro_f1,
        "schema_valid_rate": result.schema_valid_rate,
        "rows": [asdict(row) for row in result.rows],
    }


def quality_from_dict(payload: Any) -> QualityResult:
    if not isinstance(payload, dict):
        raise ValueError("quality result must be an object")
    required = {
        "schema_version", "total", "correct", "schema_valid", "missing",
        "accuracy", "macro_f1", "schema_valid_rate", "rows",
    }
    if set(payload) != required or payload["schema_version"] != "1.0.0":
        raise ValueError("invalid quality result fields or schema version")
    rows = tuple(QualityRow(**row) for row in payload["rows"])
    result = QualityResult(
        total=payload["total"], correct=payload["correct"],
        schema_valid=payload["schema_valid"], missing=payload["missing"],
        accuracy=payload["accuracy"], macro_f1=payload["macro_f1"],
        schema_valid_rate=payload["schema_valid_rate"], rows=rows,
    )
    if result.total != len(rows) or result.correct != sum(row.correct for row in rows):
        raise ValueError("quality result aggregates do not match rows")
    if result.schema_valid != sum(row.schema_valid for row in rows):
        raise ValueError("quality schema-valid aggregate does not match rows")
    return result


def compare_quality(baseline: QualityResult, treatment: QualityResult) -> QualityComparison:
    baseline_rows = {row.request_id: row for row in baseline.rows}
    treatment_rows = {row.request_id: row for row in treatment.rows}
    if set(baseline_rows) != set(treatment_rows) or not baseline_rows:
        raise ValueError("quality comparisons require identical non-empty request IDs")
    agreement = sum(
        baseline_rows[request_id].predicted_intent == treatment_rows[request_id].predicted_intent
        for request_id in baseline_rows
    ) / len(baseline_rows)
    return QualityComparison(
        accuracy_delta_pp=(treatment.accuracy - baseline.accuracy) * 100,
        macro_f1_delta_pp=(treatment.macro_f1 - baseline.macro_f1) * 100,
        schema_valid_rate=treatment.schema_valid_rate,
        prediction_agreement=agreement,
    )
