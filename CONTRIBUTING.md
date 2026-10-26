# Contributing to SentinelLLM

Thank you for your interest in contributing to SentinelLLM and PromptProbe. We welcome contributions from researchers, security practitioners, and software engineers.

---

## 1. Code of Conduct and Responsible Security Testing

As a security-focused project, we operate under strict responsible-testing ethics:
- **Authorized Testing Only:** Adversarial evaluations and security probes developed or tested within this project must **only target owned systems or explicitly authorized test environments**.
- **No Malicious Targeting:** Under no circumstances should tools, test suites, or attack vectors developed in this repository be aimed at third-party services, commercial model endpoints, or production deployments without explicit, verifiable written permission from the system owners.
- **Isolated Synthetic Payloads:** Pull requests adding benchmark attacks or regression tests must use synthetic test fixtures, mock tools, or benign proof-of-concept markers rather than weaponized exploit payloads.

---

## 2. Bug Reports and Feature Proposals

- **Bug Reports:** If you encounter unexpected behavior, build failures, or documentation errors, please open an issue on GitHub detailing your environment, steps to reproduce, and expected versus actual behavior.
- **Security Vulnerabilities:** If you discover a security flaw or vulnerability within SentinelLLM itself, please **do not open a public GitHub issue**. Instead, follow the responsible disclosure guidelines outlined in [SECURITY.md](SECURITY.md).
- **Feature Proposals:** For architectural changes or major enhancements, open an issue labeled `RFC` or discussion thread first to align on technical design before writing code.

---

## 3. Local Development & Quality Gates

Before opening a pull request, verify that your changes adhere to our engineering standards:

1. **Format and Lint:** Ensure your code satisfies Ruff rules:
   ```bash
   make format
   make lint
   ```
2. **Type Check:** Static typing must pass in strict mode:
   ```bash
   make typecheck
   ```
3. **Tests & Coverage:** All automated tests must pass with minimum coverage maintained:
   ```bash
   make test
   ```
4. **Complete Verification:** Run the unified verification gate:
   ```bash
   make check
   ```

---

## 4. Pull Request Guidelines

1. **Branch Naming:** Use clear branch names like `feat/trust-boundary-tagger`, `fix/canary-leak-detector`, `docs/threat-model-update`.
2. **Commit Hygiene:** Follow Conventional Commits (`feat:`, `fix:`, `docs:`, `chore:`, `test:`, `refactor:`).
3. **Documentation:** Any new architectural component or configuration setting must include accompanying docstrings and documentation updates in `docs/`.
4. **Testing:** New features and bug fixes must be accompanied by relevant unit or integration tests.
