from __future__ import annotations

import unittest

from armproof.evidence.confirmed_audit import (
    _end_to_end_samples,
    _verify_response_identities,
)
from armproof.workload import RequestSample


SOURCE = "a" * 64
MODEL = "b" * 64


def sample(*, scheduled: int, started: int, finished: int) -> RequestSample:
    return RequestSample(
        request_id="request-1",
        scheduled_ns=scheduled,
        started_ns=started,
        finished_ns=finished,
        status_code=200,
        error=None,
        response={
            "request_id": "source-1",
            "backend": "kleidiai-enabled",
            "runtime_identity": {
                "model_identity": MODEL,
                "source_artifact_sha256": SOURCE,
                "runtime": "onnxruntime-genai",
                "runtime_version": "0.15.0.dev0",
                "threads": 16,
                "architecture": "aarch64",
                "cpu_affinity": list(range(16)),
                "optimization_control": {"mlas.disable_kleidiai": "0"},
            },
        },
    )


class ConfirmedAuditTests(unittest.TestCase):
    def test_end_to_end_latency_includes_dispatch_delay(self) -> None:
        row = sample(scheduled=0, started=2_000_000_000, finished=3_000_000_000)
        adjusted, maximum_dispatch_ms = _end_to_end_samples(
            [row], duration_seconds=5, slo_ms=1_000
        )
        self.assertEqual(adjusted[0].latency_ms, 3_000)
        self.assertEqual(maximum_dispatch_ms, 2_000)
        self.assertTrue(adjusted[0].accepted)

    def test_completion_after_window_and_slo_drain_is_rejected(self) -> None:
        row = sample(scheduled=0, started=1, finished=6_000_000_001)
        adjusted, _ = _end_to_end_samples(
            [row], duration_seconds=5, slo_ms=1_000
        )
        self.assertFalse(adjusted[0].accepted)
        self.assertEqual(adjusted[0].error, "completion_after_slo_drain")

    def test_runtime_identity_is_bound_to_every_capacity_response(self) -> None:
        row = sample(scheduled=0, started=0, finished=1)
        models, runtimes = _verify_response_identities(
            [row],
            treatment_id="kleidiai-enabled",
            source_artifact_sha256=SOURCE,
            threads=16,
        )
        self.assertEqual(models, {MODEL})
        self.assertEqual(runtimes, {"0.15.0.dev0"})

        changed = RequestSample(
            **{
                **row.__dict__,
                "response": {
                    **row.response,
                    "runtime_identity": {
                        **row.response["runtime_identity"],
                        "optimization_control": {"mlas.disable_kleidiai": "1"},
                    },
                },
            }
        )
        with self.assertRaisesRegex(ValueError, "runtime identity"):
            _verify_response_identities(
                [changed],
                treatment_id="kleidiai-enabled",
                source_artifact_sha256=SOURCE,
                threads=16,
            )


if __name__ == "__main__":
    unittest.main()
