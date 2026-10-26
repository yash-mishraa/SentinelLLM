# Benchmark Datasets

This directory holds dataset schemas, download/generation scripts, and metadata references for LLM security benchmarking.

## Dataset Categories (Planned)

1. **Direct Injection Workloads:** User inputs attempting goal hijacking, system prompt extraction, and instruction overrides.
2. **Indirect Injection Workloads:** Simulated untrusted third-party content (e.g., poisoned web pages, malicious emails, manipulated API payloads).
3. **Tool Manipulation Scenarios:** Multi-step agent interaction traces designed to test tool unauthorized invocation boundaries.
4. **Benign Task Baselines:** Standard non-adversarial utility tasks (e.g., text summarization, data extraction, Q&A) used to quantify false-positive rates (FPR) and benign task completion degradation.

## Data Governance and Responsible Research

- **Synthetic & Simulated Payloads Only:** Datasets must contain synthetic test fixtures and simulated vulnerability triggers. Never store active exploits, malware payloads, or proprietary operational secrets.
- **Licensing and Attribution:** External research datasets integrated here must document upstream license terms and citation metadata.
- **Git Storage Policy:** Large datasets should be stored in external artifact repositories with content-addressed hashes (e.g., SHA256) tracked in this repository, rather than committing large binary blobs to Git.
