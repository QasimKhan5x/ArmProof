from __future__ import annotations

import unittest

from armproof.workload import (
    RequestInput,
    RequestSample,
    SloPolicy,
    find_sustainable_capacity,
    run_closed_loop,
    run_open_loop,
    summarize_samples,
)


def sample(request_id: str, latency_ms: float, status: int = 200) -> RequestSample:
    return RequestSample(
        request_id=request_id,
        scheduled_ns=0,
        started_ns=0,
        finished_ns=int(latency_ms * 1_000_000),
        status_code=status,
        error=None if status == 200 else "http_error",
        response=None,
    )


class LoadSummaryTests(unittest.TestCase):
    def test_open_and_closed_loop_preserve_request_ids(self) -> None:
        requests = [RequestInput(str(index), {"value": index}) for index in range(4)]

        def send(item: RequestInput, scheduled_ns: int) -> RequestSample:
            return RequestSample(
                request_id=item.request_id,
                scheduled_ns=scheduled_ns,
                started_ns=scheduled_ns,
                finished_ns=scheduled_ns + 1_000_000,
                status_code=200,
                error=None,
                response={"value": item.payload["value"]},
            )

        closed = run_closed_loop(requests, send, concurrency=2)
        opened = run_open_loop(requests, send, target_rps=1000, max_workers=2)
        self.assertEqual({row.request_id for row in closed}, {"0", "1", "2", "3"})
        self.assertEqual({row.request_id for row in opened}, {"0", "1", "2", "3"})
        scheduled = sorted(row.scheduled_ns for row in opened)
        self.assertEqual([b - a for a, b in zip(scheduled, scheduled[1:])], [1_000_000] * 3)

    def test_summary_preserves_errors_and_percentiles(self) -> None:
        summary = summarize_samples(
            [sample("a", 10), sample("b", 20), sample("c", 30), sample("d", 40, 500)],
            duration_seconds=1.0,
        )
        self.assertEqual(summary.total, 4)
        self.assertEqual(summary.accepted, 3)
        self.assertEqual(summary.error_rate, 0.25)
        self.assertEqual(summary.accepted_rps, 3.0)
        self.assertEqual(summary.p50_ms, 20.0)
        self.assertEqual(summary.p95_ms, 30.0)

    def test_capacity_search_stops_at_first_failed_candidate(self) -> None:
        calls = []

        def run(target_rps: float) -> list[RequestSample]:
            calls.append(target_rps)
            latency = 50 if target_rps <= 20 else 150
            return [sample(str(index), latency) for index in range(int(target_rps))]

        result = find_sustainable_capacity(
            candidates_rps=[10, 20, 30, 40],
            run_candidate=run,
            policy=SloPolicy(p95_latency_ms=100, max_error_rate=0.0),
            measurement_seconds=1.0,
        )
        self.assertEqual(result.sustainable_rps, 20)
        self.assertEqual(calls, [10, 20, 30])
        self.assertEqual([attempt.passed for attempt in result.attempts], [True, True, False])

    def test_no_passing_candidate_returns_zero(self) -> None:
        result = find_sustainable_capacity(
            candidates_rps=[10],
            run_candidate=lambda _: [sample("failed", 200)],
            policy=SloPolicy(p95_latency_ms=100, max_error_rate=0.0),
            measurement_seconds=1.0,
        )
        self.assertEqual(result.sustainable_rps, 0.0)

    def test_invalid_slo_policy_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            SloPolicy(p95_latency_ms=0, max_error_rate=0.0)
        with self.assertRaises(ValueError):
            SloPolicy(p95_latency_ms=100, max_error_rate=1.1)


if __name__ == "__main__":
    unittest.main()
