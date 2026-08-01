from __future__ import annotations

import unittest

from armproof.quality.banking77 import (
    QualityCase,
    compare_quality,
    evaluate_quality,
    quality_from_dict,
    quality_to_dict,
)
from armproof.workload import RequestInput, RequestSample


def case(request_id: str, expected: str) -> QualityCase:
    return QualityCase(RequestInput(request_id, {"request_id": request_id, "prompt": "p"}), expected, "source")


def sample(request_id: str, output: str, status: int = 200) -> RequestSample:
    return RequestSample(
        request_id=request_id,
        scheduled_ns=0,
        started_ns=0,
        finished_ns=1,
        status_code=status,
        error=None if status == 200 else "http_error",
        response={"output": output} if status == 200 else None,
    )


class Banking77QualityTests(unittest.TestCase):
    def test_scores_accuracy_macro_f1_and_schema_validity(self) -> None:
        cases = [case("a", "intent_a"), case("b", "intent_b"), case("c", "intent_b")]
        samples = [
            sample("a", '{"intent":"intent_a"}'),
            sample("b", '{"intent":"intent_a"}'),
            sample("c", '{"intent":"intent_b"}'),
        ]
        result = evaluate_quality(cases, samples)
        self.assertAlmostEqual(result.accuracy, 2 / 3)
        self.assertAlmostEqual(result.schema_valid_rate, 1.0)
        self.assertAlmostEqual(result.macro_f1, (2 / 3 + 2 / 3) / 2)

    def test_fenced_json_is_normalized_and_unknown_intent_is_schema_valid(self) -> None:
        cases = [case("a", "intent_a"), case("b", "intent_b"), case("c", "intent_c")]
        samples = [
            sample("a", "```json\n{\"intent\":\"intent_a\"}\n```"),
            sample("b", '{"intent":"invented"}'),
        ]
        result = evaluate_quality(cases, samples)
        self.assertEqual(result.correct, 1)
        self.assertEqual(result.schema_valid, 2)
        self.assertEqual(result.missing, 1)

    def test_result_round_trip_validates_aggregates(self) -> None:
        result = evaluate_quality(
            [case("a", "intent_a")], [sample("a", '{"intent":"intent_a"}')]
        )
        self.assertEqual(quality_from_dict(quality_to_dict(result)), result)
        payload = quality_to_dict(result)
        payload["correct"] = 0
        with self.assertRaisesRegex(ValueError, "aggregates"):
            quality_from_dict(payload)

    def test_duplicate_sample_is_rejected(self) -> None:
        cases = [case("a", "intent_a")]
        with self.assertRaisesRegex(ValueError, "duplicate"):
            evaluate_quality(cases, [sample("a", '{"intent":"intent_a"}')] * 2)

    def test_comparison_reports_delta_and_agreement(self) -> None:
        cases = [case("a", "intent_a"), case("b", "intent_b")]
        baseline = evaluate_quality(
            cases,
            [sample("a", '{"intent":"intent_a"}'), sample("b", '{"intent":"intent_a"}')],
        )
        treatment = evaluate_quality(
            cases,
            [sample("a", '{"intent":"intent_a"}'), sample("b", '{"intent":"intent_b"}')],
        )
        result = compare_quality(baseline, treatment)
        self.assertEqual(result.accuracy_delta_pp, 50.0)
        self.assertEqual(result.prediction_agreement, 0.5)
        self.assertEqual(result.schema_valid_rate, 1.0)


if __name__ == "__main__":
    unittest.main()
