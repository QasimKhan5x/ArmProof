"""Evidence collection, manifests, and verification."""

from armproof.evidence.checksums import (
    ChecksumResult,
    checksum_ledger_paths,
    verify_checksum_ledger,
)
from armproof.evidence.adapters import (
    EvidenceAdapter,
    get_evidence_adapter,
    list_evidence_adapters,
)
from armproof.evidence.identity import ArtifactFingerprint, fingerprint_path
from armproof.evidence.manifest import build_manifest, verify_manifest
from armproof.evidence.pipeline import ADAPTER_ID, VerifiedEvidence, verify_and_derive
from armproof.evidence.records import EvidenceRecordError, comparison_to_dict, parse_comparison

__all__ = [
    "ArtifactFingerprint",
    "ChecksumResult",
    "EvidenceRecordError",
    "EvidenceAdapter",
    "VerifiedEvidence",
    "ADAPTER_ID",
    "build_manifest",
    "checksum_ledger_paths",
    "fingerprint_path",
    "get_evidence_adapter",
    "list_evidence_adapters",
    "comparison_to_dict",
    "parse_comparison",
    "verify_and_derive",
    "verify_checksum_ledger",
    "verify_manifest",
]
