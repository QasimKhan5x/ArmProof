# Glossary

- **Accelerated coverage:** A declared weighting of execution facts that were
  handled by an eligible KleidiAI path. Always name the weighting method.
- **BF16/F16 reference:** High-precision source used for quality comparison and
  primary quantization. Not necessarily the fastest deployment baseline.
- **Candidate:** A generated GGUF model plus recipe and evidence identity.
- **Dispatch:** Runtime selection of backend/kernel implementation for an
  operation under tensor, shape, type, and CPU constraints.
- **Evidence bundle:** Immutable directory containing environment, commands,
  traces, measurements, checksums, and decision for one run.
- **Fallback:** An operation that does not use the intended eligible KleidiAI
  path. A fallback may still be correct and fast; the reason matters.
- **GGML:** Tensor and execution infrastructure used by `llama.cpp`.
- **GGUF:** Model file format used by `llama.cpp`.
- **KleidiAI:** Arm microkernel library integrated into AI/ML frameworks.
- **Kernel eligibility:** Whether a kernel may handle a specific operation on
  the detected CPU, given type, shape, layout, and runtime rules.
- **Observed fact:** Emitted directly by runtime or measured command.
- **Derived fact:** Computed from observed facts and a versioned source rule.
- **Target-BPW:** Upstream llama.cpp optimization that chooses tensor types to
  meet a bits-per-weight target with estimated quality considerations.
- **Trace overhead:** Performance difference caused by enabling instrumentation.
- **Unknown:** Evidence is insufficient. It is not equivalent to fallback.

