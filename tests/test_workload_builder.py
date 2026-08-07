from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.build_banking77_workload import serialize_jsonl, verify_or_write


class WorkloadBuilderTests(unittest.TestCase):
    def test_verify_rejects_stale_generated_content(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workload.jsonl"
            path.write_text('{"request_id":"old"}\n', encoding="utf-8")

            with self.assertRaisesRegex(SystemExit, "generated data is stale"):
                verify_or_write(path, '{"request_id":"new"}\n', verify=True)

    def test_serialization_is_stable_and_compact(self) -> None:
        self.assertEqual(
            serialize_jsonl([{"z": 1, "a": "value"}]),
            '{"a":"value","z":1}\n',
        )


if __name__ == "__main__":
    unittest.main()
