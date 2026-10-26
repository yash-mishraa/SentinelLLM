# PromptProbe

**PromptProbe** is the companion adversarial evaluation and benchmarking suite for SentinelLLM.

## Mission and Scope

PromptProbe provides reproducible security evaluation harnesses for LLM applications and AI agents. It is designed to evaluate both unprotected baselines and defensive frameworks (including SentinelLLM) against structured adversarial attacks.

Key responsibilities:
- **Adversarial Test Execution:** Executing direct prompt injections, indirect prompt injections, jailbreaks, and tool-manipulation vectors.
- **Metric Collection:** Measuring quantitative metrics including Attack Success Rate (ASR), Benign Task Completion Rate (TCR), False Positive Rate (FPR), and Unauthorized Tool Execution Rate (UTER).
- **Ablation Studies:** Systematically toggling individual defense components (e.g., input filtering, trust-boundary tagging, action-level policy gates) to evaluate their distinct contribution to system security.
- **Reproducible Benchmarking:** Running parameterized benchmark datasets with pinned seeds, standardized environment reporting, and deterministic output serialization.

## Logical Separation from SentinelLLM

PromptProbe is logically decoupled from `sentinelllm` runtime protection:
1. **Independent Operation:** Evaluators can assess external systems, alternative defense frameworks, or raw foundation model endpoints without loading SentinelLLM runtime interceptors.
2. **Independent Dependency Footprint:** Benchmark datasets and adversarial payload runners do not pollute the core runtime package dependencies.
3. **Objective Evaluation:** Preserves separation between defense implementation and evaluation harness to prevent circular dependencies or evaluation bias.

## Current Status

> **Status:** Foundation milestone in progress. Evaluation harnesses, dataset runners, and scoring routines are planned for subsequent milestones.
