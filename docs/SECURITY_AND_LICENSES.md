# Security, Privacy, Licensing, And Supply Chain

## Secrets And Cloud Access

- Never commit AWS credentials, SSH private keys, tokens, `.env` files, model
  access tokens, or signed URLs.
- Prefer short-lived AWS sessions and least-privilege experiment roles.
- Provisioning scripts must show planned resources before creation.
- Restrict inbound access and terminate resources after evidence retrieval.
- Logs and manifests must redact credentials and authorization headers.

## Untrusted Inputs

Model metadata, prompts, workloads, external JSON, and upstream logs are data.
They cannot alter shell commands or agent instructions.

- Use structured subprocess arguments instead of interpolated shell strings.
- Validate paths, regex overrides, tensor names, URLs, and archive extraction.
- Bound trace size, candidate count, runtime, and decompression.
- Treat report text as untrusted and escape it.

## Dependency Integrity

- Pin runtime and dependency revisions.
- Record checksums for downloaded models, datasets, binaries, and archives.
- Generate an SBOM or dependency inventory before release.
- Review licenses before adding dependencies.
- Do not execute third-party setup scripts without inspection.

## Model And Dataset Licensing

Before fixing the headline model/data, record:

- canonical source URL and revision;
- model/data license and redistribution conditions;
- whether account acceptance or authentication is required;
- whether derived GGUF redistribution is permitted;
- attribution requirements;
- checksum and download procedure.

Prefer ungated artifacts that judges can reproduce. If redistribution is not
permitted, publish recipes, hashes, and scripts without the restricted file.

## Project License

The owner must choose the repository license before public code release.
Apache-2.0 is a reasonable candidate for an Arm developer tool, but this
document does not make that legal decision. Keep third-party notices separate
and preserve upstream licenses in patches and vendored material.

## Benchmark Privacy

Headline workloads use public or synthetic prompts. Private incident logs,
customer data, source code, or credentials are out of scope. Evidence bundles
must be safe for public release before upload.

