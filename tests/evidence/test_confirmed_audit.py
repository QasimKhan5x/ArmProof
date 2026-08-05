from __future__ import annotations

import io
import json
import tarfile
import unittest
from pathlib import Path

from armproof.contracts import parse_contract
from armproof.evidence.confirmed_audit import (
    _end_to_end_samples,
    _parse_samples,
    _verify_matched_control,
    _verify_response_identities,
    validate_confirmed_contract_claims,
)
from armproof.workload import RequestSample


SOURCE = "a" * 64
MODEL = "b" * 64
ROOT = Path(__file__).resolve().parents[2]


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
    @staticmethod
    def _claim_validation_inputs() -> tuple[dict, dict, dict, dict]:
        contract = json.loads(
            (ROOT / "examples/armproof-reference/confirmed-contract.json").read_text()
        )
        experiment = json.loads(
            (ROOT / "ops/experiments/EXP-2026-014.json").read_text()
        )
        protocol = json.loads(
            (ROOT / "ops/aws/sustained-006/protocol.json").read_text()
        )
        performix = json.loads(
            (ROOT / "ops/experiments/EXP-2026-013.json").read_text()
        )
        return contract, experiment, protocol, performix

    def test_contract_claims_match_every_frozen_plan_rule(self) -> None:
        contract, experiment, protocol, performix = self._claim_validation_inputs()
        validate_confirmed_contract_claims(
            parse_contract(contract),
            experiment_id=experiment["experiment_id"],
            acceptance=experiment["acceptance"],
            protocol=protocol,
            performix_acceptance=performix["acceptance"],
            raw_quality_output_count=1540,
        )

    def test_contract_cannot_lower_or_remove_a_frozen_claim(self) -> None:
        contract, experiment, protocol, performix = self._claim_validation_inputs()
        contract["claims"] = [
            claim for claim in contract["claims"]
            if claim["id"] != "performix-sample-count"
        ]
        with self.assertRaisesRegex(ValueError, "claim set"):
            validate_confirmed_contract_claims(
                parse_contract(contract),
                experiment_id=experiment["experiment_id"],
                acceptance=experiment["acceptance"],
                protocol=protocol,
                performix_acceptance=performix["acceptance"],
                raw_quality_output_count=1540,
            )

        contract, experiment, protocol, performix = self._claim_validation_inputs()
        next(
            claim for claim in contract["claims"]
            if claim["id"] == "sustained-capacity-lower-bound"
        )["threshold"] = 1.5
        with self.assertRaisesRegex(ValueError, "sustained-capacity-lower-bound"):
            validate_confirmed_contract_claims(
                parse_contract(contract),
                experiment_id=experiment["experiment_id"],
                acceptance=experiment["acceptance"],
                protocol=protocol,
                performix_acceptance=performix["acceptance"],
                raw_quality_output_count=1540,
            )

    @staticmethod
    def _matched_archive(*, changed_source_identity: bool = False) -> tarfile.TarFile:
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode="w") as archive:
            for lane, control in (("disabled", "1"), ("enabled", "0")):
                config = {
                    "model": {"decoder": {"session_options": {
                        "intra_op_num_threads": 16,
                        "mlas.disable_kleidiai": control,
                    }}}
                }
                identity = {
                    "source_artifact_sha256": (
                        "b" * 64 if changed_source_identity and lane == "enabled" else SOURCE
                    )
                }
                for name, payload in (
                    ("genai_config.json", config),
                    ("armproof_source_identity.json", identity),
                ):
                    body = json.dumps(payload).encode()
                    member = tarfile.TarInfo(
                        f"evidence/capacity/variants/{lane}/{name}"
                    )
                    member.size = len(body)
                    archive.addfile(member, io.BytesIO(body))
                model = tarfile.TarInfo(
                    f"evidence/capacity/variants/{lane}/model.onnx"
                )
                model.type = tarfile.SYMTYPE
                model.linkname = "/models/source/model.onnx"
                archive.addfile(model)
        stream.seek(0)
        return tarfile.open(fileobj=stream, mode="r")

    def test_matched_control_accepts_equal_source_identity_files(self) -> None:
        with self._matched_archive() as archive:
            matched, threads = _verify_matched_control(archive)
        self.assertTrue(matched)
        self.assertEqual(threads, 16)

    def test_matched_control_rejects_different_source_identity_files(self) -> None:
        with self._matched_archive(changed_source_identity=True) as archive:
            matched, _ = _verify_matched_control(archive)
        self.assertFalse(matched)

    def test_timed_out_request_remains_failure_evidence_without_a_response_identity(self) -> None:
        rows = _parse_samples(
            '{"error":"TimeoutError","finished_ns":60000000000,'
            '"latency_ms":60000.0,'
            '"request_id":"confirm-1-kleidiai-disabled-000000-source-1",'
            '"response":null,"scheduled_ns":0,"started_ns":0,'
            '"status_code":null}',
            treatment_id="kleidiai-disabled",
            repetition=1,
            source_ids=("source-1",),
        )
        self.assertEqual(len(rows), 1)
        self.assertFalse(rows[0].accepted)
        self.assertEqual(rows[0].error, "TimeoutError")

    def test_unattributed_success_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "not attributed"):
            _parse_samples(
                '{"error":null,"finished_ns":1,"latency_ms":0.000001,'
                '"request_id":"confirm-1-kleidiai-enabled-000000-source-1",'
                '"response":{"backend":"wrong","request_id":"source-1"},'
                '"scheduled_ns":0,"started_ns":0,"status_code":200}',
                treatment_id="kleidiai-enabled",
                repetition=1,
                source_ids=("source-1",),
            )

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

    def test_runtime_identity_skips_explicit_timeouts_but_requires_a_success(self) -> None:
        timeout = RequestSample(
            request_id="request-timeout",
            scheduled_ns=0,
            started_ns=0,
            finished_ns=60_000_000_000,
            status_code=None,
            error="TimeoutError",
            response=None,
        )
        row = sample(scheduled=0, started=0, finished=1)
        models, runtimes = _verify_response_identities(
            [row, timeout],
            treatment_id="kleidiai-enabled",
            source_artifact_sha256=SOURCE,
            threads=16,
        )
        self.assertEqual(models, {MODEL})
        self.assertEqual(runtimes, {"0.15.0.dev0"})
        with self.assertRaisesRegex(ValueError, "no identity-bearing responses"):
            _verify_response_identities(
                [timeout],
                treatment_id="kleidiai-enabled",
                source_artifact_sha256=SOURCE,
                threads=16,
            )


if __name__ == "__main__":
    unittest.main()
