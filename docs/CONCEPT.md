# ArmProof Concept

## One Sentence

ArmProof is the CI release gate that prevents an Arm AI optimization pull
request from merging unless its quality, cloud capacity, Arm execution and
reproducibility claims are supported by matched evidence.

## Application Showcase

SurgeDesk makes that infrastructure legible through a realistic banking
support workflow. An operator reviews recorded Phi-4 Mini routing suggestions,
then replays an accepted burst of BANKING77 traffic. With the model, runtime,
machine and SLO fixed, enabling KleidiAI raises sustainable mixed-traffic
capacity from 0.20 to 0.60 requests/second. ArmProof then shows why that result
is releasable and provides the exact passing deployment.

SurgeDesk is not a second benchmark dashboard. It is the application whose
customer queue benefits from the optimization; ArmProof is the reusable
developer artifact that prevents unsupported optimization claims.

## User And Painful Moment

The primary user is an inference-framework maintainer or ML platform engineer
reviewing an Arm64 deployment change. The PR author supplies benchmark charts,
but the reviewer cannot tell whether:

- the workload and controls are comparable;
- quality regressed;
- the Arm acceleration path actually executed;
- the improvement survives concurrent cloud serving; or
- another developer can reproduce the result.

The current workaround is a collection of ad hoc benchmark scripts, profiler
reports and manually reviewed spreadsheets. It does not produce an enforceable
merge decision.

## Product Experience

The developer adds one `armproof.json` config to the repository. A trusted Arm
benchmark job records the declared baseline and treatments; ArmProof evaluates
the contract and posts a GitHub Check. A passing check links to a static
interactive report and the exact deployable configuration. A failed check
explains which claim lacks evidence.

The reference PR migrates a Phi-4 Mini service from PyTorch BF16 to INT4 ONNX
Runtime GenAI with KleidiAI on Graviton4. A public labeled workload is a test
fixture, not the product story.

## Distinctive Mechanism

ArmProof uses a fail-closed claim ledger. Each claim records:

- exact baseline and treatment identities;
- artifact, runtime, workload and environment hashes;
- raw samples and statistical summary;
- quality result and tolerance;
- Arm execution evidence; and
- reproduction command.

It also separates causal scopes:

- BF16 PyTorch versus INT4 ONNX Runtime GenAI describes the whole deployment
  transformation.
- Identical INT4 runtime with KleidiAI disabled versus enabled isolates the
  Arm acceleration contribution.
- Fixed-instance load testing describes the cloud-serving consequence.

## What Ships

- Python CLI and versioned schemas.
- Matched-control process and HTTP workload runner.
- Quality, PSS, latency and throughput evaluation.
- KleidiAI execution detector backed by `perf`/Performix evidence.
- Fail-closed claim ledger and verifier.
- Static interactive report.
- Portable GitHub Action plus a documented Graviton evidence producer.
- Phi-4 reference contract, deployment manifest and tutorial.
- Checksummed evidence and clean-room reproduction instructions.

## Non-Goals

- Finding optimization parameters automatically.
- Certifying universal quality, safety or optimality.
- Acting as an official Arm certification authority.
- Building an inference scheduler or new kernel.
- Supporting many shallow runtime integrations.
- Hosted SaaS, multi-cloud orchestration, training or fine-tuning.

## Honest Claim Form

> For pinned model M, workload W, runtime R and Arm target H, treatment T met
> contract C. Claim X is supported by matched control B and evidence E.
