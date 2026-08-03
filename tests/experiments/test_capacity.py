from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from armproof.experiments.capacity import (
    CapacityProtocol,
    FixedBoundary,
    MixProtocol,
    TreatmentEndpoint,
    run_capacity_experiment,
)
from armproof.quality.banking77 import QualityResult, QualityRow
from armproof.workload import RequestInput, RequestSample


class CapacityProtocolTests(unittest.TestCase):
    def test_protocol_requires_enough_distinct_mixes_and_five_confirmations(self) -> None:
        mix = MixProtocol("short", Path("short.jsonl"), 1000, (0.1, 0.2))
        with self.assertRaisesRegex(ValueError, "minimum passing mixes"):
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

    def test_fixed_boundaries_must_cover_every_mix_and_treatment(self) -> None:
        mix = MixProtocol("mixed", Path("mixed"), 1000, (0.1, 0.2))
        with self.assertRaisesRegex(ValueError, "cover each mix"):
            CapacityProtocol(
                "EXP-2026-009", (mix,), Path("quality"),
                minimum_passing_mixes=1,
                fixed_boundaries=(
                    FixedBoundary("mixed", "kleidiai-enabled", 0.1, 0.2),
                ),
            )

    def test_treatment_value_object_is_serializable(self) -> None:
        endpoint = TreatmentEndpoint("kleidiai-enabled", "http://127.0.0.1:8001/infer")
        self.assertEqual(endpoint.treatment_id, "kleidiai-enabled")

    def test_high_confidence_protocol_enforces_confirmation_sample_count(self) -> None:
        mix = MixProtocol("mixed", Path("mixed.jsonl"), 10_000, (0.20, 0.24))
        protocol = CapacityProtocol(
            "EXP-2026-006",
            (mix,),
            Path("quality.jsonl"),
            confirmation_seconds=500,
            minimum_confirmation_requests=100,
            minimum_passing_mixes=1,
        )
        self.assertEqual(protocol.minimum_confirmation_requests, 100)

        with self.assertRaisesRegex(ValueError, "at least 100 requests"):
            CapacityProtocol(
                "EXP-2026-006",
                (mix,),
                Path("quality.jsonl"),
                confirmation_seconds=30,
                minimum_confirmation_requests=100,
                minimum_passing_mixes=1,
            )

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
                prepared = []
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
                    prepare_window=lambda treatment, window: prepared.append(
                        (treatment, window)
                    ),
                )
            self.assertTrue(summary["passed"])
            self.assertEqual(summary["passing_mixes"], 3)
            self.assertEqual(summary["mixes"]["short"]["ratio"]["ratio"], 2.0)
            self.assertTrue((root / "evidence/summary.json").is_file())
            self.assertEqual(len(prepared), len(set(prepared)))
            self.assertEqual(len(prepared), 84)
            self.assertEqual(
                len(list((root / "evidence/window-warmup").glob("*.jsonl"))),
                84,
            )

            def unstable_confirmation(requests, send, target_rps, max_workers):
                treatment = "enabled" if "kleidiai-enabled" in requests[0].request_id else "disabled"
                capacity = 0.4 if treatment == "enabled" else 0.2
                is_invalid_pass = (
                    "confirm-" in requests[0].request_id
                    and "kleidiai-enabled-pass" in requests[0].request_id
                )
                latency_ns = (
                    2_000_000_000
                    if target_rps > capacity or is_invalid_pass
                    else 1_000_000
                )
                return [
                    RequestSample(item.request_id, 0, 0, latency_ns, 200, None, {})
                    for item in requests
                ]

            with patch(
                "armproof.experiments.capacity.run_open_loop",
                side_effect=unstable_confirmation,
            ):
                invalid = run_capacity_experiment(
                    protocol,
                    [
                        TreatmentEndpoint("kleidiai-disabled", "disabled"),
                        TreatmentEndpoint("kleidiai-enabled", "enabled"),
                    ],
                    root / "invalid-evidence",
                    send=send,
                    precomputed_quality={
                        "kleidiai-disabled": quality_result,
                        "kleidiai-enabled": quality_result,
                    },
                )
            self.assertFalse(invalid["passed"])
            self.assertIsNone(invalid["mixes"]["short"]["ratio"])
            self.assertIsNone(invalid["mixes"]["short"]["capacity_bracket"])

            fixed_protocol = CapacityProtocol(
                "EXP-2026-009",
                tuple(
                    MixProtocol(name, traffic, 1000, (0.1, 0.2))
                    for name in ("short", "long", "mixed")
                ),
                quality,
                confirmation_seconds=10,
                fixed_boundaries=tuple(
                    FixedBoundary(name, treatment, passing, failing)
                    for name in ("short", "long", "mixed")
                    for treatment, passing, failing in (
                        ("kleidiai-disabled", 0.2, 0.3),
                        ("kleidiai-enabled", 0.4, 0.5),
                    )
                ),
            )
            fixed_prepared = []
            with patch(
                "armproof.experiments.capacity.run_open_loop",
                side_effect=no_sleep_open_loop,
            ):
                fixed = run_capacity_experiment(
                    fixed_protocol,
                    [
                        TreatmentEndpoint("kleidiai-disabled", "disabled"),
                        TreatmentEndpoint("kleidiai-enabled", "enabled"),
                    ],
                    root / "fixed-evidence",
                    send=send,
                    precomputed_quality={
                        "kleidiai-disabled": quality_result,
                        "kleidiai-enabled": quality_result,
                    },
                    prepare_window=lambda treatment, window: fixed_prepared.append(
                        (treatment, window)
                    ),
                )
            self.assertTrue(fixed["passed"])
            self.assertEqual(len(fixed_prepared), 60)
            self.assertEqual(
                json.loads((root / "fixed-evidence/discovery.json").read_text())
                ["short"]["kleidiai-enabled"][0]["source"],
                "preregistered_fixed_boundary",
            )


if __name__ == "__main__":
    unittest.main()
