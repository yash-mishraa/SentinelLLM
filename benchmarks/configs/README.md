# Benchmark Configurations

This directory stores configuration files for benchmark execution runs in PromptProbe.

## Purpose

To ensure scientific reproducibility, all evaluation runs should be driven by versioned configuration files specifying:
- **Target Model / System:** Model identifier, sampling parameters (temperature, max tokens), system prompts.
- **Defense Configuration:** Active defense layers, detector thresholds, trust boundary rules.
- **Dataset Reference:** Selected attack datasets and benign workload sets.
- **Evaluation Parameters:** Batch size, random seed, timeout limits, and repeat counts.

## Structure (Planned)

```text
configs/
├── baselines/            # Unprotected baseline configurations
├── detectors/            # Configurations for individual detection mechanisms
└── layered/              # Full defense-in-depth policy configurations
```

> **Note:** Configuration schemas and concrete benchmark presets will be authored in upcoming milestones alongside the PromptProbe evaluation harness.
