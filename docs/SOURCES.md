# Source Ledger

Last reviewed: 2026-07-29

External facts must be rechecked when implementation begins because upstream
interfaces and challenge guidance can change.

## Challenge

- [Cloud AI track details](https://arm-ai-optimization-challenge.devpost.com/details/trackdetails)
  defines eligible Arm cloud targets, CPU inference, quantization, pruning,
  llama.cpp, agentic workloads, and production workflows.
- [Challenge resources](https://arm-ai-optimization-challenge.devpost.com/resources)
  links the Arm Developer Program, learning paths, GitHub ecosystem, Discord,
  workshops, and office hours. It does not currently promise cloud credits.
- [Challenge updates](https://arm-ai-optimization-challenge.devpost.com/updates)
  emphasize measurable optimization rather than merely running on Arm.
- [Challenge rules](https://arm-ai-optimization-challenge.devpost.com/rules)
  are authoritative for eligibility and submission requirements.

## Runtime And Arm Optimization

- [`llama.cpp` build documentation](https://github.com/ggml-org/llama.cpp/blob/master/docs/build.md)
  documents `GGML_CPU_KLEIDIAI`, runtime CPU-feature dispatch, and the Arm
  features used by KleidiAI.
- [`llama.cpp` quantize documentation](https://github.com/ggml-org/llama.cpp/blob/master/tools/quantize/README.md)
  documents source-model quantization, requantization warnings,
  `--tensor-type`, importance matrices, and related options.
- [`llama.cpp` target-BPW discussion](https://github.com/ggml-org/llama.cpp/discussions/15576)
  establishes an existing quality-oriented automatic per-tensor optimizer.
  KleidiScope must compare against it rather than claim generic automatic
  mixed quantization as novel.
- [KleidiAI repository](https://github.com/ARM-software/kleidiai)
  documents microkernel scope, supported instruction families, naming, build,
  and CPU compatibility.
- [Arm KleidiAI and SME2 learning path](https://learn.arm.com/learning-paths/mobile-graphics-and-gaming/performance_llama_cpp_sme2/introduction/)
  demonstrates a 3B llama.cpp test shape and explains dispatch into KleidiAI.

## Infrastructure And Cost

- [AWS C8g](https://aws.amazon.com/ec2/instance-types/c8g/) identifies C8g as
  Graviton4 compute-optimized infrastructure.
- [AWS C8g CPU options](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/cpu-options-supported-instances-values.html)
  confirms single-threaded physical-core topology.
- [AWS EBS pricing](https://aws.amazon.com/ebs/pricing/) explains provisioned
  storage billing and Free Tier allowances.
- [AWS On-Demand billing](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-on-demand-instances.html)
  explains per-second compute billing and persistent storage charges.
- [AWS Pricing Calculator](https://calculator.aws/) is the final authority to
  recheck before provisioning.

## Long-Horizon Agent Engineering

- [OpenAI: Harness engineering](https://openai.com/index/harness-engineering/)
  recommends a short `AGENTS.md` as a map into deeper sources of truth rather
  than a giant instruction file.
- [OpenAI: Unrolling the Codex agent loop](https://openai.com/index/unrolling-the-codex-agent-loop/)
  describes the role of the execution harness, instructions, tools, and
  approval boundaries.
- [Anthropic: Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)
  recommends durable progress state, a structured feature list, startup smoke
  tests, incremental work, and evidence before marking features complete.
- [Anthropic: Harness design for long-running application development](https://www.anthropic.com/engineering/harness-design-long-running-apps)
  reinforces file-mediated coordination and verifiable application outcomes.

## Methodological Use

The repository adopts the following implications from those sources:

- small routing instructions plus selective context loading;
- machine-readable work items with explicit verification;
- a startup health check before new work;
- append-only experiment records and immutable raw evidence;
- falsifiable claims connected to acceptance gates;
- incremental commits and clear handoffs across context windows.

