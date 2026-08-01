from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from armproof.experiments.capacity import (
    CapacityProtocol,
    MixProtocol,
    TreatmentEndpoint,
    run_capacity_experiment,
)
from armproof.quality.banking77 import QualityResult, QualityRow
from armproof.workload import RequestInput, RequestSample


class CapacityProtocolTests(unittest.TestCase):
    def test_protocol_requires_three_mixes_and_five_confirmations(self) -> None:
        mix = MixProtocol("short", Path("short.jsonl"), 1000, (0.1, 0.2))
        with self.assertRaisesRegex(ValueError, "three"):
            CapacityProtocol("EXP-2026-003", (mix,), Path("quality.jsonl"))
        with self.assertRaisesRegex(ValueError, "five"):
            CapacityProtocol(
                "EXP-2026-003",
                (
                    mix,
                    MixProtocol("long", Path("long"), 2000, (0.1, 0.2)),
                    MixProtocol("mixed", Path("mixed"), 1500, (0.1, 0.2)),
                ),
                Path("quality"),
                confirmations=4,
            )

    def test_candidates_must_be_ascending_and_distinct(self) -> None:
        with self.assertRaisesRegex(ValueError, "ascending"):
            MixProtocol("short", Path("short"), 1000, (0.2, 0.1))
        with self.assertRaisesRegex(ValueError, "ascending"):
            MixProtocol("short", Path("short"), 1000, (0.1, 0.1))

    def test_treatment_value_object_is_serializable(self) -> None:
        endpoint = TreatmentEndpoint("kleidiai-enabled", "http://127.0.0.1:8001/infer")
        self.assertEqual(endpoint.treatment_id, "kleidiai-enabled")

    def test_nominal_rate_rounding_uses_actual_offered_rate(self) -> None:
        from armproof.experiments.capacity import _run_window

        captured = {}

        def fake_open_loop(requests, send, target_rps, max_workers):
            captured["target_rps"] = target_rps
            return [RequestSample(item.request_id, 0, 0, 1, 200, None, {}) for item in requests]

        with patch("armproof.experiments.capacity.run_open_loop", side_effect=fake_open_loop):
            samples, summary, offered = _run_window(
                "endpoint", [RequestInput("one", {})], 0.075, 30, 1, 1,
                "rounded", lambda *_: None,  # type: ignore[arg-type]
            )
        self.assertEqual(len(samples), 2)
        self.assertAlmostEqual(offered, 2 / 30)
        self.assertAlmostEqual(captured["target_rps"], 2 / 30)
        self.assertAlmostEqual(summary["accepted_rps"], 2 / 30)

    def test_complete_orchestration_confirms_distinct_capacity_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            traffic = root / "traffic.jsonl"
            traffic.write_text(
                json.dumps({
                    "request_id": "traffic-1",
                    "payload": {"prompt": "route this", "max_new_tokens": 1},
                }) + "\n"
            )
            quality = root / "quality.jsonl"
            quality.write_text(json.dumps({
                "request_id": "quality-1",
                "payload": {"prompt": "route this", "max_new_tokens": 1},
                "expected_intent": "label",
                "source_text": "route this",
            }) + "\n")
            protocol = CapacityProtocol(
                "EXP-2026-003",
                tuple(
                    MixProtocol(name, traffic, 1000, (0.1, 0.2, 0.3, 0.4, 0.5))
                    for name in ("short", "long", "mixed")
                ),
                quality,
                discovery_seconds=10,
                confirmation_seconds=10,
            )
            row = QualityRow("quality-1", "label", "label", True, True, None)
            quality_result = QualityResult(1, 1, 1, 0, 1.0, 1.0, 1.0, (row,))

            def send(endpoint, item, scheduled, timeout):
                return RequestSample(
                    item.request_id, scheduled, scheduled, scheduled + 1_000_000,
                    200, None, {"output": '{"intent":"label"}'},
                )

            def no_sleep_open_loop(requests, send, target_rps, max_workers):
                treatment = "enabled" if "kleidiai-enabled" in requests[0].request_id else "disabled"
                capacity = 0.4 if treatment == "enabled" else 0.2
                latency_ns = 1_000_000 if target_rps <= capacity else 2_000_000_000
                return [
                    RequestSample(item.request_id, 0, 0, latency_ns, 200, None, {})
                    for item in requests
                ]

            with patch("armproof.experiments.capacity.run_open_loop", side_effect=no_sleep_open_loop):
                summary = run_capacity_experiment(
                    protocol,
                    [
                        TreatmentEndpoint("kleidiai-disabled", "disabled"),
                        TreatmentEndpoint("kleidiai-enabled", "enabled"),
                    ],
                    root / "evidence",
                    send=send,
                    precomputed_quality={
                        "kleidiai-disabled": quality_result,
                        "kleidiai-enabled": quality_result,
                    },
                )
            self.assertTrue(summary["passed"])
            self.assertEqual(summary["passing_mixes"], 3)
            self.assertEqual(summary["mixes"]["short"]["ratio"]["ratio"], 2.0)
            self.assertTrue((root / "evidence/summary.json").is_file())


if __name__ == "__main__":
    unittest.main()
