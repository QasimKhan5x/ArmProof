# Sources

External pages establish technical and challenge context. Pinned source and raw
measurements override planning prose when they conflict.

## Challenge

- [Arm Create: AI Optimization Challenge](https://arm-ai-optimization-challenge.devpost.com/)
- [Cloud AI track](https://arm-ai-optimization-challenge.devpost.com/details/trackdetails)
- [Challenge updates and optimization guidance](https://arm-ai-optimization-challenge.devpost.com/updates)
- [Challenge resources](https://arm-ai-optimization-challenge.devpost.com/resources)

## Arm And Runtime Stack

- [Arm Phi-4 ONNX Runtime learning path](https://learn.arm.com/learning-paths/servers-and-cloud-computing/onnx/setup/)
- [Arm ONNX Runtime and KleidiAI profiling example](https://learn.arm.com/learning-paths/mobile-graphics-and-gaming/performance_onnxruntime_kleidiai_sme2/profiling_example/)
- [KleidiAI repository](https://github.com/ARM-software/kleidiai)
- [ONNX Runtime GenAI repository](https://github.com/microsoft/onnxruntime-genai)
- [Arm Performix practical analysis](https://community.arm.com/arm-community-blogs/b/servers-and-cloud-computing-blog/posts/arm-performix-practical-performance-analysis-for-arm-based-servers)
- [Arm Performix product page](https://developer.arm.com/servers-and-cloud-computing/arm-performix)
- [Install Arm Performix](https://learn.arm.com/install-guides/performix/)
- [Vociply Performix case study](https://developer.arm.com/community/arm-community-blogs/b/servers-and-cloud-computing-blog/posts/40-faster-image-classification-on-aws-graviton-how-vociply-used-arm-perfomix-to-cut-costs-29)

## Product And Benchmark Context

- [BANKING77 official repository](https://github.com/PolyAI-LDN/task-specific-datasets)
- [BANKING77 paper](https://aclanthology.org/2020.nlp4convai-1.5/)
- [GuideLLM](https://github.com/vllm-project/guidellm)
- [GitHub artifact attestations](https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations/use-artifact-attestations)
- [Chuck'it](https://devpost.com/software/chuck-it)
- [DreamMeridian](https://devpost.com/software/dreammeridian-geoai-on-pi)

GuideLLM and artifact attestations are adjacent systems, not ArmProof features.
ArmProof's scoped contribution is an Arm-aware, fail-closed PR decision that
combines workload quality, fixed-SLO capacity, matched acceleration controls
and executed Arm-path evidence.

## Evidence Sources

The accepted result-first findings are summarized in
[`ESTABLISHED_EVIDENCE.md`](ESTABLISHED_EVIDENCE.md). Exact runtime/model
revisions and checksums must be imported from raw evidence by `EVID-001`; this
document must not invent them.
