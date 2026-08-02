"""Evidence collection, manifests, and verification."""

from armproof.evidence.checksums import ChecksumResult, verify_checksum_ledger
from armproof.evidence.adapters import EvidenceAdapter, get_evidence_adapter
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
    "fingerprint_path",
    "get_evidence_adapter",
    "comparison_to_dict",
    "parse_comparison",
    "verify_and_derive",
    "verify_checksum_ledger",
    "verify_manifest",
]
