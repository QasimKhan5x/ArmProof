from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from armproof.evidence.pipeline import _assert_reproduction_inputs_match


ROOT = Path(__file__).resolve().parents[2]
PRIMARY = ROOT / "ops/evidence/EXP-2026-004/accepted/evidence"
REPRODUCTION = ROOT / "ops/evidence/EXP-2026-005/accepted/evidence"


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class ReproductionInputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.primary_experiment = _json(PRIMARY / "experiment.json")
        cls.reproduction_experiment = _json(REPRODUCTION / "experiment.json")
        cls.primary_protocol = _json(
            PRIMARY / "capacity/experiment/protocol.json"
        )
        cls.reproduction_protocol = _json(
            REPRODUCTION / "capacity/experiment/protocol.json"
        )

    def test_accepted_reproduction_uses_the_same_protocol_and_workload_ids(self) -> None:
        _assert_reproduction_inputs_match(
            PRIMARY,
            REPRODUCTION,
            self.primary_experiment,
            self.reproduction_experiment,
            self.primary_protocol,
            self.reproduction_protocol,
        )

    def test_structurally_different_reproduction_protocol_is_rejected(self) -> None:
        changed = copy.deepcopy(self.reproduction_protocol)
        changed["protocol"]["mixes"][0]["p95_slo_ms"] = 20_000.0
        with self.assertRaisesRegex(ValueError, "protocol differs"):
            _assert_reproduction_inputs_match(
                PRIMARY,
                REPRODUCTION,
                self.primary_experiment,
                self.reproduction_experiment,
                self.primary_protocol,
                changed,
            )


if __name__ == "__main__":
    unittest.main()
