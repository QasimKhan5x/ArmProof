from __future__ import annotations

import unittest
from pathlib import Path

from armproof.quality import run_ort_batched_quality


class OrtBatchQualityTests(unittest.TestCase):
    def test_empty_cases_and_invalid_batch_fail_before_runtime_import(self) -> None:
        with self.assertRaisesRegex(ValueError, "empty"):
            run_ort_batched_quality(Path("missing"), [], label="test")
        with self.assertRaisesRegex(ValueError, "positive"):
            run_ort_batched_quality(Path("missing"), [object()], batch_size=0, label="test")  # type: ignore[list-item]


if __name__ == "__main__":
    unittest.main()
