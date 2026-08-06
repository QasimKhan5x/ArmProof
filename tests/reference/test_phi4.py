from __future__ import annotations

import json
import hashlib
import tempfile
import subprocess
import sys
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from armproof.reference.phi4 import (
    OrtInt4Backend,
    RELEASED_RUNTIME_TUNING,
    _aws_instance_type,
    _memory_runtime_identity,
    _ort_model_identity,
    _verify_runtime_artifact_ledger,
    create_ort_variant,
    validate_request,
)

ROOT = Path(__file__).resolve().parents[2]


class Phi4ReferenceTests(unittest.TestCase):
    def test_memory_runtime_identity_reads_allocator_and_thp_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            maps = root / "maps"
            thp = root / "enabled"
            maps.write_text("7f libpython3.12.so\n", encoding="utf-8")
            thp.write_text("always [madvise] never\n", encoding="utf-8")
            self.assertEqual(
                _memory_runtime_identity(maps_path=maps, thp_path=thp),
                {"allocator": "system", "transparent_huge_pages": "madvise"},
            )
            maps.write_text("7f /lib/aarch64-linux-gnu/libmimalloc.so.2\n")
            thp.write_text("[always] madvise never\n", encoding="utf-8")
            self.assertEqual(
                _memory_runtime_identity(maps_path=maps, thp_path=thp),
                {"allocator": "mimalloc", "transparent_huge_pages": "always"},
            )

    def test_runtime_ledger_is_verified_before_runtime_import(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            ledger = Path(directory) / "SHA256SUMS"
            ledger.write_text("invalid ledger\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "runtime artifact ledger is malformed"):
                OrtInt4Backend(
                    Path(directory) / "missing-model",
                    "optimized",
                    runtime_artifact_ledger=ledger,
                    runtime_artifact_ledger_sha256=hashlib.sha256(
                        ledger.read_bytes()
                    ).hexdigest(),
                )

    def test_instance_type_comes_from_aws_imdsv2(self) -> None:
        with patch(
            "armproof.reference.phi4.urllib.request.urlopen",
            side_effect=[BytesIO(b"token"), BytesIO(b"c8g.4xlarge")],
        ) as urlopen:
            self.assertEqual(_aws_instance_type(), "c8g.4xlarge")
        token_request = urlopen.call_args_list[0].args[0]
        metadata_request = urlopen.call_args_list[1].args[0]
        self.assertEqual(token_request.get_method(), "PUT")
        self.assertEqual(metadata_request.get_header("X-aws-ec2-metadata-token"), "token")

    def test_runtime_artifact_ledger_verifies_every_declared_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            wheel = root / "runtime.whl"
            wheel.write_bytes(b"pinned runtime")
            ledger = root / "SHA256SUMS"
            digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
            ledger.write_text(f"{digest}  {wheel.name}\n", encoding="utf-8")
            ledger_digest = hashlib.sha256(ledger.read_bytes()).hexdigest()
            self.assertEqual(
                _verify_runtime_artifact_ledger(ledger, ledger_digest),
                ledger_digest,
            )
            with self.assertRaisesRegex(ValueError, "accepted digest"):
                _verify_runtime_artifact_ledger(ledger, "0" * 64)
            with self.assertRaisesRegex(ValueError, "missing required files"):
                _verify_runtime_artifact_ledger(
                    ledger, ledger_digest, ("required-runtime.whl",)
                )
            wheel.write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "runtime artifact checksum mismatch"):
                _verify_runtime_artifact_ledger(ledger, ledger_digest)

    def test_reference_imports_in_a_fresh_interpreter(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-I",
                "-c",
                (
                    "import sys; sys.path.insert(0, 'src'); "
                    "from armproof.reference import create_ort_variant; "
                    "assert callable(create_ort_variant)"
                ),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_matched_variants_change_only_session_control(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            (source / "model.onnx").write_bytes(b"model")
            (source / "genai_config.json").write_text(
                json.dumps({"model": {"decoder": {"session_options": {"existing": "same"}}}})
            )
            enabled = create_ort_variant(source, root / "enabled", True, 16)
            disabled = create_ort_variant(source, root / "disabled", False, 16)
            enabled_config = json.loads((enabled / "genai_config.json").read_text())
            disabled_config = json.loads((disabled / "genai_config.json").read_text())
            enabled_options = enabled_config["model"]["decoder"]["session_options"]
            disabled_options = disabled_config["model"]["decoder"]["session_options"]
            self.assertEqual(enabled_options["mlas.disable_kleidiai"], "0")
            self.assertEqual(disabled_options["mlas.disable_kleidiai"], "1")
            enabled_options.pop("mlas.disable_kleidiai")
            disabled_options.pop("mlas.disable_kleidiai")
            self.assertEqual(enabled_config, disabled_config)
            self.assertTrue((enabled / "model.onnx").is_symlink())
            enabled_identity, enabled_source, enabled_control, enabled_threads, enabled_tuning = _ort_model_identity(enabled)
            disabled_identity, disabled_source, disabled_control, disabled_threads, disabled_tuning = _ort_model_identity(disabled)
            self.assertEqual(enabled_identity, disabled_identity)
            self.assertEqual(enabled_source, disabled_source)
            self.assertEqual((enabled_control, disabled_control), ("0", "1"))
            self.assertEqual((enabled_threads, disabled_threads), (16, 16))
            self.assertEqual(enabled_tuning, {})
            self.assertEqual(disabled_tuning, {})
            (source / "model.onnx").write_bytes(b"changed-model")
            with self.assertRaisesRegex(ValueError, "no longer matches"):
                _ort_model_identity(enabled)

    def test_variant_accepts_non_reserved_session_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            (source / "model.onnx").write_bytes(b"model")
            (source / "genai_config.json").write_text(
                json.dumps({"model": {"decoder": {"session_options": {}}}})
            )
            variant = create_ort_variant(
                source,
                root / "variant",
                True,
                16,
                session_overrides={
                    "session.intra_op.spin_duration_us": "1000",
                    "session.intra_op.spin_backoff_max": "8",
                },
            )
            options = json.loads(
                (variant / "genai_config.json").read_text(encoding="utf-8")
            )["model"]["decoder"]["session_options"]
            self.assertEqual(options["session.intra_op.spin_duration_us"], "1000")
            self.assertEqual(options["session.intra_op.spin_backoff_max"], "8")
            identity = _ort_model_identity(variant)
            self.assertEqual(
                identity[4],
                {
                    "session.intra_op.spin_backoff_max": "8",
                    "session.intra_op.spin_duration_us": "1000",
                },
            )
            with self.assertRaisesRegex(ValueError, "reserved session option"):
                create_ort_variant(
                    source,
                    root / "invalid",
                    True,
                    16,
                    session_overrides={"mlas.disable_kleidiai": "1"},
                )

    def test_release_tuning_does_not_change_source_model_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            (source / "model.onnx").write_bytes(b"model")
            (source / "genai_config.json").write_text(
                json.dumps({"model": {"decoder": {"session_options": {}}}})
            )
            baseline = create_ort_variant(source, root / "baseline", False, 16)
            optimized = create_ort_variant(
                source,
                root / "optimized",
                True,
                16,
                session_overrides=RELEASED_RUNTIME_TUNING,
            )
            baseline_identity = _ort_model_identity(baseline)
            optimized_identity = _ort_model_identity(optimized)
            self.assertEqual(baseline_identity[:2], optimized_identity[:2])
            self.assertEqual(baseline_identity[4], {})
            self.assertEqual(optimized_identity[4], RELEASED_RUNTIME_TUNING)

    def test_request_contract_is_bounded(self) -> None:
        self.assertEqual(validate_request({"request_id": "r", "prompt": "p"}), ("r", "p", 64))
        with self.assertRaisesRegex(ValueError, "between"):
            validate_request({"request_id": "r", "prompt": "p", "max_new_tokens": 0})
        with self.assertRaisesRegex(ValueError, "fields"):
            validate_request({"request_id": "r", "prompt": "p", "temperature": 1})


if __name__ == "__main__":
    unittest.main()
