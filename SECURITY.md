# Security Policy

SentinelLLM is dedicated to building robust, verifiable security controls for AI applications. We take the security of this project and responsible disclosure seriously.

---

## 1. Reporting a Security Vulnerability

If you discover a security vulnerability within SentinelLLM or PromptProbe (such as an execution bypass in policy enforcement, secret disclosure, or arbitrary code execution flaw), please report it responsibly:

- **Do NOT report security vulnerabilities through public GitHub issues.**
- **Private Advisory:** Please use [GitHub Private Vulnerability Reporting](https://github.com/yash-mishraa/SentinelLLM/security/advisories/new) on the repository.
- Include in your report:
  - A clear description of the vulnerability.
  - Minimal steps or a synthetic proof-of-concept script to reproduce the behavior.
  - The potential security impact and affected versions.
  - Any suggested remediation or patches.

### Response Timeline
- **Acknowledgment:** Within 48 hours of receipt.
- **Triage & Assessment:** Within 7 business days with a severity rating and remediation roadmap.
- **Disclosure Coordination:** We coordinate a responsible public disclosure and release date once a patch has been developed, tested, and validated.

---

## 2. Responsible Security Testing Policy

SentinelLLM and its companion harness PromptProbe contain adversarial evaluation components designed for defensive research. All contributors and researchers must strictly follow these rules:

1. **Explicit Authorization:** Testing must be conducted **only against systems, models, and environments you own or have explicit written permission to test**.
2. **No Unsanctioned Scanning:** Do not execute PromptProbe attack suites against shared production endpoints, proprietary cloud LLM APIs in violation of terms of service, or third-party infrastructure.
3. **Simulated Sandboxing:** All local regression tests and evaluation harnesses must execute against mock backends, synthetic tools, or isolated sandbox environments.
4. **No Destructive Actions:** Do not create or run payloads intended to cause physical harm, data corruption, persistent denial-of-service, or privacy violations.

---

## 3. Supported Versions

| Version | Supported |
| :--- | :--- |
| `0.1.x` (Development) | :white_check_mark: |
