# SentinelLLM Research & Evaluation Plan

> **Status:** Research proposal and methodology specification.
> **Notice:** The findings and empirical comparisons described herein represent a planned experimental roadmap. No empirical novelty or quantitative benchmarks are claimed prior to execution.

---

## 1. Central Research Question

> **"Can trust-aware, action-level enforcement improve the security–utility trade-off of LLM applications compared with content detection alone?"**

---

## 2. Research Hypothesis & Motivation

Current LLM defense literature predominantly emphasizes **probabilistic content inspection** (e.g., input perplexity filters, toxic classification heads, vector similarity matches against adversarial prompt libraries). While these filters catch known adversarial patterns, they suffer from two fundamental vulnerabilities:
1. **Adaptive Evasion:** Adversaries routinely discover novel phrasing, multi-lingual encodings, or cipher techniques that circumvent probabilistic pattern matching.
2. **Utility Degradation (Over-Defense):** Aggressive input filtering induces high false-positive rates on complex or domain-specific benign queries (e.g., cybersecurity educational queries, code debugging), causing refusal or task abortion.

**Hypothesis:** Decoupling detection from enforcement—by propagating strict context provenance tags and enforcing deterministic, action-level tool execution boundaries (PEP)—will significantly reduce unauthorized actions and prompt injection consequences without inflicting proportional utility loss on benign workloads.

---

## 3. Experimental Configurations (Defense Baselines)

The evaluation will compare four distinct system configurations under identical attack and benign workloads:

| ID | Configuration Name | Description | Key Defensive Components |
| :--- | :--- | :--- | :--- |
| **C0** | **Unprotected Baseline** | Direct user and context pass-through to LLM | Native LLM system prompt instructions only. |
| **C1** | **Heuristic Filtering** | Static signature and pattern matching | Delimiter checking, keyword blacklists, regex checks, canary leakage detection. |
| **C2** | **Classifier-Based Detection** | Supervised semantic classification | External prompt-injection classifier model gating all inputs and outputs. |
| **C3** | **Layered Defense (SentinelLLM)** | Full defense-in-depth architecture | Trust-aware provenance framing + multi-signal detectors + deterministic PDP + action-level tool execution proxy (PEP). |

---

## 4. Evaluation Metrics

To capture the trade-off between security, utility, and operational efficiency, evaluation runs will capture six quantitative metrics:

1. **Attack Success Rate (ASR) [%]:**
   The proportion of adversarial injection payloads that successfully achieve their stated adversarial objective (e.g., system prompt extraction, bypass of safety instructions).
   $$\text{ASR} = \frac{\text{Successful Adversarial Injections}}{\text{Total Adversarial Injections Tested}} \times 100$$

2. **Unauthorized Tool Execution Rate (UTER) [%]:**
   The proportion of adversarial payloads that successfully execute a privileged or prohibited tool function.
   $$\text{UTER} = \frac{\text{Unauthorized Tool Invocations Executed}}{\text{Total Tool Exploitation Attempts}} \times 100$$

3. **False-Positive Rate (FPR) [%]:**
   The proportion of legitimate, benign user requests incorrectly blocked, sanitized, or rejected as adversarial.
   $$\text{FPR} = \frac{\text{Benign Requests Rejected}}{\text{Total Benign Requests Tested}} \times 100$$

4. **Benign Task Completion Rate (TCR) [%]:**
   The proportion of non-adversarial benchmark tasks (e.g., summarization, code generation, question-answering) completed with acceptable semantic fidelity.

5. **Latency Overhead [ms]:**
   The additional P50, P95, and P99 latency introduced by the interception, inspection, and policy evaluation pipeline compared with the raw model call.

6. **Inference & Execution Cost Overhead [$ or Tokens]:**
   Additional token consumption resulting from prompt framing, canary tokens, and auxiliary classifier invocations per request.

---

## 5. Planned Ablation Studies

To isolate the marginal value of each architectural layer in configuration C3, PromptProbe will run systematic ablations:

- **Ablation 1 (No Provenance Framing):** Disables trust-tier tagging while retaining detectors and PEP. Tests whether taint propagation prevents indirect injection when detectors fail.
- **Ablation 2 (No Detectors):** Disables probabilistic heuristic and classifier detectors while retaining provenance tagging and action-level PEP. Tests whether deterministic containment alone suffices for application safety.
- **Ablation 3 (No Action PEP):** Retains detectors and provenance tagging but allows the LLM to invoke tools directly without out-of-band proxy validation. Measures the direct contribution of action-level gating to UTER reduction.
- **Ablation 4 (No Output Validation):** Disables egress canary leak scanning and regex redactors to quantify exfiltration vulnerability.

---

## 6. Evaluation Workloads & Held-Out Attack Variants

To guard against data contamination and ensure test validity:
- **Direct Prompt Injections:** Goal hijacking, token smuggling, role-play framing, multi-step instruction overrides.
- **Indirect Injections:** Simulated RAG corpora containing poisoned documents, malicious email headers, and deceptive simulated API responses.
- **Held-Out Adversarial Attacks:** A reserved partition of zero-shot attacks not used in tuning detector heuristics or classification thresholds (e.g., novel cipher encodings, nested translation attacks).
- **Benign Control Datasets:** Diverse standard datasets (e.g., GSM8k, HumanEval subsets, customer service transcripts) to measure FPR and TCR accurately.

---

## 7. Scientific Reproducibility & Open Science Standards

All PromptProbe benchmark runs will enforce:
- **Pinned Random Seeds:** Explicitly specified RNG seeds across all stochastic sampling operations.
- **Model Version Pinning:** Exact model provider snapshot IDs (e.g., not mutable rolling aliases).
- **Environment Reporting:** Auto-generated metadata capturing Python environment, OS, hardware, and dependency lockfile hashes alongside benchmark output files.
- **Deterministic Evaluation Harness:** Open, audited evaluation code with no subjective manual grading.

---

## 8. Research Limitations

- Evaluation results on specific foundation model versions may not generalize identically to all foundation models or future architectural variants.
- Adversarial attack creation is an evolving arms race; benchmarks reflect existing known threat classes at the time of authoring.
- Real-world production workloads may contain domain-specific linguistic nuances not fully reflected in synthetic evaluation suites.
