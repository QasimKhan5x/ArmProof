from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from armproof.workload import (
    RequestInput,
    RequestSample,
    WorkloadError,
    load_requests_jsonl,
    materialize_requests,
    write_samples_jsonl,
)


class WorkloadIoTests(unittest.TestCase):
    def test_load_and_materialize_assign_unique_ids(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "workload.jsonl"
            path.write_text('{"request_id":"base","payload":{"prompt":"hello"}}\n')
            base = load_requests_jsonl(path)
        rows = materialize_requests(base, 3, "trial")
        self.assertEqual([row.request_id for row in rows], [
            "trial-000000-base", "trial-000001-base", "trial-000002-base"
        ])

    def test_duplicate_input_id_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "workload.jsonl"
            line = '{"request_id":"same","payload":{}}\n'
            path.write_text(line + line)
            with self.assertRaisesRegex(WorkloadError, "duplicate"):
                load_requests_jsonl(path)

    def test_samples_are_written_in_schedule_order(self) -> None:
        rows = [
            RequestSample("late", 20, 20, 30, 200, None, {"ok": True}),
            RequestSample("early", 10, 10, 20, 500, "http_error", None),
        ]
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "samples.jsonl"
            write_samples_jsonl(path, rows)
            saved = [json.loads(line) for line in path.read_text().splitlines()]
        self.assertEqual([row["request_id"] for row in saved], ["early", "late"])
        self.assertEqual(saved[0]["error"], "http_error")


if __name__ == "__main__":
    unittest.main()
