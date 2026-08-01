# Security And Licensing

## Input Trust

Contracts, workloads, runtime output and external metadata are untrusted data.
They must never supply shell fragments, file traversal or executable report
content.

- Use structured subprocess arguments.
- Resolve paths inside approved roots.
- Apply process timeouts and output limits.
- Escape all report content and use a restrictive content security policy.
- Do not embed secrets or environment dumps in evidence.

## CI And Cloud

- Pin third-party GitHub Actions by immutable revision for releases.
- Limit workflow permissions and protect self-hosted runner credentials.
- Treat pull-request code from forks as untrusted; do not expose AWS secrets.
- Run paid or privileged jobs only after an approved maintainer action.
- Use least-privilege AWS credentials and reject account-root identity.

## Evidence Integrity

ArmProof uses hashes and reproducible validation, not formal cryptographic
attestation. A bundle is invalid when required files, identities or hashes do
not match. The UI must not imply a stronger guarantee.

## Models And Data

For every reference artifact record:

- canonical source and revision;
- license and redistribution terms;
- download command and checksum;
- whether acceptance or authentication is required; and
- whether the repository stores the artifact or only its manifest.

Do not commit model weights or datasets unless redistribution is explicitly
permitted. Prefer scripted downloads with fixed IDs.

## Project License

ArmProof source is MIT licensed. BANKING77 remains under CC-BY-4.0 with its
license, pinned source revision, attribution and derivation notice preserved in
`THIRD_PARTY_NOTICES.md` and `data/banking77/`.

## Release Checks

- secret scan;
- dependency and action review;
- model/data license review;
- generated report injection test;
- archive content inspection; and
- confirmation that no private AWS or local paths appear in public artifacts.
