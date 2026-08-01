# Context Pack: EVID-001 Import Established Evidence

## Gate

Local evidence work is permitted. Do not run AWS or modify accepted result
values. Raw artifacts currently live outside this Git repository.

## Task

Import the selected result-first evidence into `ops/evidence/`, calculate
checksums, preserve the original experiment/follow-up distinction, and produce
a machine-readable source manifest.

## Load These Files

- `STATUS.md`
- `docs/ESTABLISHED_EVIDENCE.md`
- `docs/BENCHMARK_PROTOCOL.md`, Evidence Bundle section
- `docs/TRACEABILITY.md`
- sibling workspace `result-first-bakeoff/RESULT.md`
- sibling workspace `result-first-bakeoff/FOLLOWUP-RESULT.md`
- evidence archives and summaries named by those files

## Trusted Inputs

- Raw archives, JSON samples, checksums and frozen experiment documents.
- Existing tested summarizer code only as a description of derivation.

## Verify Before Acting

- Human-readable summaries.
- File paths and inferred relationships.
- Any artifact lacking a checksum or immutable identity.

## Expected Outputs

- `ops/evidence/result-first/manifest.json`
- Imported immutable evidence files or checksummed archive references.
- Updated evidence paths in `docs/TRACEABILITY.md`.
- Registry entry in `ops/experiments/registry.jsonl`.
- Focused manifest/hash tests.

## Non-Goals

- Recalculate or improve accepted numbers.
- Rerun AWS.
- Build the ArmProof claim validator.
- Rename a failed historical gate as passed.

## Verification

- Every imported file matches its recorded hash.
- Manifest references resolve inside the repository evidence root.
- Original no-go and independent follow-up remain separate records.
- `python3 scripts/validate_context.py` passes.

## Stop And Ask

Stop for missing archives, contradictory summaries, unknown provenance,
unexpected private data, or an import too large for the public repository.

