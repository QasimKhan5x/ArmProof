# Sources

These references document the runtime, profiler, dataset, and publication tools
used by the project. Pinned source revisions and raw measurements are
authoritative for the checked-in result.

## Arm And Runtime Stack

- [Arm Phi-4 ONNX Runtime learning path](https://learn.arm.com/learning-paths/servers-and-cloud-computing/onnx/setup/)
- [Arm ONNX Runtime and KleidiAI profiling example](https://learn.arm.com/learning-paths/mobile-graphics-and-gaming/performance_onnxruntime_kleidiai_sme2/profiling_example/)
- [KleidiAI repository](https://github.com/ARM-software/kleidiai)
- [ONNX Runtime GenAI repository](https://github.com/microsoft/onnxruntime-genai)
- [Arm Performix practical analysis](https://community.arm.com/arm-community-blogs/b/servers-and-cloud-computing-blog/posts/arm-performix-practical-performance-analysis-for-arm-based-servers)
- [Arm Performix product page](https://developer.arm.com/servers-and-cloud-computing/arm-performix)
- [Install Arm Performix](https://learn.arm.com/install-guides/performix/)
- [Vociply Performix case study](https://developer.arm.com/community/arm-community-blogs/b/servers-and-cloud-computing-blog/posts/40-faster-image-classification-on-aws-graviton-how-vociply-used-arm-perfomix-to-cut-costs-29)

## Dataset And Benchmarking

- [BANKING77 official repository](https://github.com/PolyAI-LDN/task-specific-datasets)
- [BANKING77 paper](https://aclanthology.org/2020.nlp4convai-1.5/)
- [GuideLLM](https://github.com/vllm-project/guidellm)
- [GitHub artifact attestations](https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations/use-artifact-attestations)

GuideLLM and artifact attestations are adjacent systems, not ArmProof features.
ArmProof's scoped contribution is an Arm-aware, fail-closed PR decision that
combines workload quality, fixed-SLO capacity, matched acceleration controls
and executed Arm-path evidence.

## Repository Evidence

The accepted imported migration findings are summarized in
[`ESTABLISHED_EVIDENCE.md`](ESTABLISHED_EVIDENCE.md). Exact runtime and model
revisions are recorded in the reference configuration and checksummed evidence
archives.
