from __future__ import annotations

import importlib.util
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from armproof.cli import main
from armproof.scaffold import create_scaffold


ROOT = Path(__file__).resolve().parents[1]
REAL_REPOSITORY_COMMIT = "f64fd473e304f8116e4971e24a4a49e2efad81e9"


def _load_http_example():
    script = ROOT / "examples/http-slo/build_example.py"
    spec = importlib.util.spec_from_file_location("scaffold_http_slo_example", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _build_five_by_100_evidence(root: Path) -> Path:
    example = _load_http_example()
    config = example.build(root)
    evidence = root / "evidence"
    protocol_path = evidence / "protocol.json"
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    protocol["minimum_requests_per_file"] = 100
    groups = {
        "baseline-pass": (100, 1_000.0),
        "baseline-fail": (150, 12_000.0),
        "treatment-pass": (300, 1_000.0),
        "treatment-fail": (350, 12_000.0),
    }
    boundaries = {
        lane: {outcome: [] for outcome in ("pass", "fail")}
        for lane in ("baseline", "treatment")
    }
    for group, (count, latency_ms) in groups.items():
        lane, outcome = group.split("-")
        interval_ns = int(protocol["measurement_seconds"] * 1_000_000_000 / count)
        for repetition in range(1, 6):
            path = evidence / "requests" / f"{group}-{repetition}.jsonl"
            path.write_text(
                "\n".join(
                    example._sample(
                        f"{group}-{repetition}-{index}",
                        latency_ms,
                        1_000_000_000 + index * interval_ns,
                    )
                    for index in range(count)
                )
                + "\n",
                encoding="utf-8",
            )
            boundaries[lane][outcome].append(path.relative_to(evidence).as_posix())
    protocol["boundaries"] = boundaries
    protocol_path.write_text(
        json.dumps(protocol, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    with redirect_stdout(io.StringIO()):
        if main(["seal", str(config)]) != 0 or main(["ci", str(config)]) != 0:
            raise AssertionError("five-by-100 evidence fixture must pass before mutation")
    return config


class ScaffoldTests(unittest.TestCase):
    def test_cli_accepts_an_immutable_action_commit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "kit"
            with redirect_stdout(io.StringIO()):
                result = main([
                    "init",
                    "--endpoint", "http://127.0.0.1:8000/infer",
                    "--output", str(output),
                    "--action-commit", REAL_REPOSITORY_COMMIT,
                ])

            self.assertEqual(result, 0)
            workflow = (output / ".github/workflows/armproof.yml").read_text()
            self.assertIn(f"QasimKhan5x/ArmProof@{REAL_REPOSITORY_COMMIT}", workflow)

    def test_generated_workflow_accepts_an_immutable_release_commit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "kit"
            create_scaffold(
                output,
                "http://127.0.0.1:8000/infer",
                action_commit=REAL_REPOSITORY_COMMIT,
            )

            workflow = (output / ".github/workflows/armproof.yml").read_text()
            self.assertIn(f"QasimKhan5x/ArmProof@{REAL_REPOSITORY_COMMIT}", workflow)
            self.assertNotIn("QasimKhan5x/ArmProof@v1.1.0", workflow)

    def test_generated_protocol_rejects_four_collected_confirmations(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "kit"
            config = _build_five_by_100_evidence(root)
            (root / "evidence/requests/baseline-pass-5.jsonl").unlink()
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["seal", str(config)]), 0)
            with redirect_stderr(io.StringIO()) as stderr:
                self.assertEqual(main(["ci", str(config)]), 1)
            self.assertIn("absent from the checksum ledger", stderr.getvalue())

    def test_generated_protocol_rejects_99_raw_requests(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "kit"
            config = _build_five_by_100_evidence(root)
            path = root / "evidence/requests/baseline-pass-1.jsonl"
            rows = path.read_text(encoding="utf-8").splitlines()
            path.write_text("\n".join(rows[:99]) + "\n", encoding="utf-8")
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["seal", str(config)]), 0)
            with redirect_stderr(io.StringIO()) as stderr:
                self.assertEqual(main(["ci", str(config)]), 1)
            self.assertIn("fewer than 100 requests", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
