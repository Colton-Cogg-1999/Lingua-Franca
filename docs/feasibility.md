# Local feasibility assessment — 2026-11-15

Measured host: AMD Ryzen AI 5 340, 6 cores / 12 threads; 30 GiB RAM with approximately 25 GiB available at inspection; Radeon 840M integrated graphics; KFD target 110502 (gfx1152); approximately 751 GiB free storage. Omarchy/Arch, Python 3.14.8. Docker installed but current user cannot access its socket; kind and kubectl not found. No inference runtime was found or benchmarked.

## Recommendation

Build a computational sociolinguistics laboratory using explicit probabilistic speakers. Language is culturally transmitted, so do not treat a biological genome as language or equate communicative success with reproductive success. Start with competition between variants for shared meanings, local contact networks, accommodation, prestige, innovation, migration, and cohort replacement. This is a synthetic model for hypothesis exploration, not a validated model of any actual community.

A language model is optional. Thousands of speakers can each hold small probability tables while sharing one inference service for occasional utterance realization. Generated text must not silently determine the scientific transition rules. Frozen LLM weights plus changing prompts do not demonstrate learned language change. Validate generated utterances against the intended variant and retain model version, sampling settings, and prompts for any later experiment.

## Inference options

- vLLM CPU: the CPU exposes AVX512 and AVX512_BF16. The documented CPU path is worth testing in an isolated supported Python environment. Compatibility and throughput are not measured here.
- vLLM ROCm: current upstream CMake includes gfx1152. That alone does not verify compatible wheels, kernels, operating system, or model execution on this machine. Avoid claiming it is either impossible or plug-and-play.
- llama.cpp: CPU and Vulkan backends make a practical alternative experiment for a small quantized model on integrated graphics. Benchmark before choosing a serving runtime.
- NPU: no working inference backend has been established; do not budget its advertised compute as available simulation capacity.

A 1-billion-parameter model has roughly 0.5 GB of raw 4-bit weights or 2 GB of raw BF16 weights. Actual memory also includes metadata, runtime, KV cache, and workspaces. These are arithmetic estimates, not model fit or throughput measurements. Shared GPU memory competes with the desktop and simulation.

At 1,000 speakers × 10 utterances × 40 output tokens, one round requires 400,000 output tokens. At a hypothetical 20 tokens/sec that is 5.6 hours, excluding prompt processing. This is why model-generated conversation should initially be sampled, not required for every interaction.

Before choosing inference: benchmark one shared 0.5–1.5B model, short contexts, concurrency 1 then 4; record prompt/decode throughput, p95 latency, peak memory and constrained-variant compliance. Compare CPU and Vulkan, then vLLM if installation is practical. No model downloads or GPU throughput claims are part of this assessment.

## Sources

- https://docs.vllm.ai/en/stable/getting_started/installation/cpu/
- https://docs.vllm.ai/en/stable/getting_started/installation/gpu/
- https://github.com/vllm-project/vllm/blob/main/CMakeLists.txt
- https://github.com/ggml-org/llama.cpp/blob/master/docs/build.md
- https://arxiv.org/abs/cs/0701135 — social-network structure and linguistic innovation; motivation, not calibration for this implementation.
