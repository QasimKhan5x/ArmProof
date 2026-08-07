# SurgeDesk, powered by ArmProof

**Track:** Cloud AI

**Tagline:** A banking-support triage app that switches its connected gateway to an optimized Graviton service only after checking speed, quality, and the exact release identity.

## What We Built

SurgeDesk routes banking-support messages with Phi-4 Mini on a CPU-only AWS
Graviton4 server. The model suggests an intent, the application selects the
matching procedure and queue, and a support operator confirms the route.

The application begins on its standard service. A candidate may receive shadow
requests, but the gateway does not select it until ArmProof validates the
performance, quality, Arm execution, and exact runtime configuration behind the
release. In connected mode, each receipt includes the service identity plus digests of the
request and model output. If the running deployment drifts from the measured
one, the gateway returns to the standard route.

## Why We Built It

Cloud teams eventually need to decide whether a measured configuration is the
same one they are about to release. SurgeDesk connects archived Graviton tests
to a connected gateway route change. ArmProof verifies those tests and produces the
decision consumed by the gateway.

## What We Optimized

We developed the service in three measured stages. Each stage uses a separate
comparison and claim.

### 1. Fit Phi-4 To CPU Serving

Moving Phi-4 Mini from BF16 to the public CPU INT4 ONNX Runtime GenAI model cut
model files by 35.92%. With KleidiAI still disabled, peak proportional set size
fell by 43.09%. The complete KleidiAI-enabled INT4 stack used 55.34% less peak
PSS than BF16. Model quality remained within the required tolerance.

### 2. Move The Hot Compute Path Onto Arm I8MM

For the Arm-specific comparison, the INT4 model files, ONNX Runtime build,
workload, 16 threads, Graviton4 instance, and ten-second p95 rule stayed fixed.
Only `mlas.disable_kleidiai` changed: `1` for the control and `0` for the
treatment.

The control failed all five 500-second windows at 0.28 requests per second, so
its SLO-compliant capacity is below that rate. The KleidiAI treatment passed all
five at 0.56 requests per second, so its capacity is at least 0.56 requests per
second, equivalent to 2,016 offered messages per hour. The two boundaries
establish a conservative lower bound of at least twice the sustainable traffic
on the same `c8g.4xlarge`.

Arm Performix separately confirmed the code path running on the CPU. No control
samples landed in `kai_*` functions. With KleidiAI enabled, 67.35% of measured
function samples landed in KleidiAI code, including the Neoverse I8MM
matrix-kernel family. Linux perf provided a separate cycle-attribution view.

### 3. Remove The Next Graviton Runtime Limit

With I8MM compute active, we tested the complete service at 0.62 requests per
second. KleidiAI alone missed the p95 rule in every 300-second window. A recipe
combining three ONNX Runtime scheduling options, mimalloc, and transparent huge
pages passed all five. Median p95 fell from 14.806 to 8.147 seconds, a 44.98%
reduction, and the verified traffic floor rose from 0.56 to 0.62 requests per
second, or 2,232 offered messages per hour.

A simpler mimalloc-plus-huge-pages recipe failed all five sustained windows.
The complete recipe passed all five, so that is the configuration ArmProof
releases. Its verifier re-derives all 31 Stage 3 window summaries from 3,678 raw
rows. The sustained output-equivalence check covers 2,790 rows and 186 request
cases. Archived configs bind the released runtime settings; per-window readbacks
verify transparent huge pages. Allocator loading remains a declared setting
because those archives do not contain process-map observations.

This third stage is a whole-runtime result measured on Graviton4. The controlled
KleidiAI/I8MM comparison remains the Arm-specific compute result.

## How We Built It

- Phi-4 Mini CPU INT4 with pinned Arm64 ONNX Runtime and ONNX Runtime GenAI builds
- KleidiAI 1.20 on AWS Graviton4 Neoverse V2
- fixed-rate HTTP load generation with scheduled-to-finished latency
- 770 BANKING77 quality cases for each compute treatment
- native Arm Performix Code Hotspots exports and a separate Linux perf profile
- checksum-bound raw requests, outputs, identities, host state, and experiment plans
- a verifier that recalculates results from raw measurements
- a gateway that checks deployment identity before promotion and on every optimized response

## Results

- At least 2.0x sustainable mixed-traffic capacity from the matched KleidiAI comparison
- 67.35% Performix `kai_*` function-sample share in the treatment and 0% in the control
- A further 10.71% increase in verified traffic floor from the Graviton runtime recipe
- 44.98% lower median p95 at 0.62 requests per second
- Five of five sustained windows passed for the released recipe
- Less than one percentage point change in accuracy and macro F1 across 1,540 raw model outputs
- 35.92% smaller model files and 43.09% lower peak PSS from INT4 before KleidiAI
- Five-queue routing accuracy improved from 74.42% to 86.75%; the harder 77-intent diagnostic scored 46.49%, and an operator confirms every route

## Community Contribution

ArmProof 1.1 provides a reusable collector and verifier for bounded HTTP
classifiers. It includes versioned claim contracts, fixed-rate collection, raw-evidence
verification, native Performix parsing, deployment-identity binding,
machine-readable decisions, an offline report, a GitHub Action, and
`armproof init` for another bounded HTTP inference service. The starter begins
blocked and requires five boundary confirmations with at least 100 raw requests
each before it can pass.

Adopters provide matched service measurements, Linux perf output, identity
manifests, and the `/infer` response contract. Other workload shapes need a new
adapter. The built-in workflow targets bounded HTTP classifiers; other workloads
require an adapter.

The repository includes the complete SurgeDesk reference integration, public
schemas, evidence archives, validation commands, and an explicitly scoped
llama.cpp HTTP compatibility example. The GitHub Action and release attestation
bundle include all three runtime-treatment archives in version 1.1.0.

## What We Learned

Short screens are useful for finding candidates, but sustained traffic must
decide what ships. We also found that profiling is most useful when it drives a
deployment decision: Performix attributes the Arm compute path, sustained tests
select the runtime recipe, and the gateway checks that the running service still
matches the evidence.

## What's Next

The next application step is to connect SurgeDesk to a real support queue while
keeping the same operator confirmation and rollback behavior. For ArmProof, the
next adapter will carry a second inference runtime through the complete measured
workflow, including performance, quality, profiler attribution, and release
identity.
