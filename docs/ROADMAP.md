# Incremental Roadmap

Each phase has an entry gate, concrete artifacts, verification, and parallel
work lanes. A phase is not complete because its code exists.

## Phase 0: Repository And Source Reconnaissance

Entry: initialized docs.

Deliverables:

- pinned upstream source inventory;
- verified bootstrap and smoke commands;
- trace and environment schemas;
- dispatch path map and minimal patch design;
- fixtures for eligible/fallback/unknown cases;
- CI for docs, schemas, unit tests, and Arm64 compile check.

Parallel lanes:

- upstream source analysis;
- schema/fixture design;
- local/GitHub Actions bootstrap;
- model/data/license selection;
- AWS lifecycle dry run.

Verification gate:

- clean bootstrap succeeds;
- schemas validate fixtures;
- proposed evidence granularity is supported by source;
- no paid cloud required.

## Phase 1: Feasibility Recorder

Entry: Phase 0 passes.

Deliverables:

- minimal tracing patch/hook;
- trace normalizer;
- environment probe;
- source-grounded rule prototype;
- KleidiAI-on/off trace comparison;
- overhead measurement.

Parallel lanes:

- runtime patch;
- parser/rules/tests;
- trace analyzer;
- benchmark harness.

Verification gate:

- observed accelerated and fallback paths reconcile;
- disabled run cannot falsely report acceleration;
- unknowns are explicit;
- overhead is bounded and reported.

## Phase 2: Feasibility Optimizer

Entry: trustworthy trace.

Deliverables:

- baseline matrix;
- deterministic bounded recipe generator;
- quantizer adapter;
- candidate inspection and hashing;
- quality and performance runners;
- target-BPW matched baseline;
- GO/PIVOT/STOP evidence bundle.

Parallel lanes:

- candidate policy;
- quantizer/build adapter;
- quality evaluation;
- performance/server evaluation;
- evidence/report fixtures.

Verification gate:

- requirements FP-01 through FP-09 evaluated;
- clean evidence bundle exists;
- AWS spend within approved budget;
- decision is made before full UI investment.

## Phase 3: MVP Product

Entry: GO, or an accepted PIVOT with revised claims.

Deliverables:

- installable `kleidiscope` CLI;
- record, explain, optimize, compare commands;
- versioned public schemas;
- stable error model;
- resumable local orchestration;
- generated static report;
- one documented 3B worked example.

Parallel lanes:

- CLI/domain layer;
- report application;
- docs/tutorial;
- contract/integration tests;
- upstream patch packaging.

Verification gate:

- fresh-user quickstart succeeds;
- all required baselines enforced;
- report derives from fixture and real evidence;
- failed candidate flow is understandable.

## Phase 4: Full Hackathon Product

Entry: end-to-end MVP.

Deliverables:

- polished interactive X-ray report;
- CI acceleration-regression command/action;
- clean-room Graviton4 reproduction;
- optimized GGUF recipe/checksum/artifact;
- Arm learning-ready walkthrough;
- contribution-ready patch and technical note;
- benchmark methodology and raw evidence release.

Parallel lanes:

- browser UX/accessibility;
- CI integration;
- reproduction and packaging;
- technical writing;
- demo/submission production.

Verification gate:

- claims-to-evidence matrix complete;
- critical browser and CLI workflows tested;
- no unresolved severity-1 defects;
- submission can be judged without private infrastructure.

## Phase 5: Submission Hardening

Deliverables:

- three-minute demo and backup recording;
- Devpost copy aligned with measured claims;
- public repository cleanup;
- licenses/attributions complete;
- cost and reproduction instructions;
- judge quickstart and downloadable evidence;
- final adversarial review against all four criteria.

Verification gate:

- every number in video/copy maps to evidence;
- demo works from a prerecorded evidence bundle if live cloud fails;
- repository contains no credentials, paid resources, or restricted artifacts;
- owner approves final claims.

## Parallelization Rules

- Work in parallel only when write ownership is disjoint.
- Schema changes precede dependent implementations.
- Runtime patch and policy work may proceed together only against frozen fixture
  contracts.
- Report work uses fixtures and must not invent unavailable fields.
- Cloud benchmarks are serialized under one experiment owner to prevent cost
  and environment drift.
- Independent verification should challenge a completed evidence bundle rather
  than duplicate implementation work.

