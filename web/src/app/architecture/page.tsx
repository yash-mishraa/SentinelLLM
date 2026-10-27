import React from "react";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";

export const metadata = {
  title: "Architecture — SentinelLLM",
  description: "RFC 2904 PEP/PDP security architecture, trust boundaries, and execution lifecycle in SentinelLLM.",
};

const COMPONENTS = [
  {
    name: "Ingress Policy Enforcement Point",
    role: "PEP (Ingress)",
    boundary: "Untrusted Client / Network Boundary",
    responsibility:
      "Intercepts raw incoming prompt messages, multi-turn chat histories, and retrieved RAG context before any inference worker or model receives data. Routes payloads to the inspection engine.",
  },
  {
    name: "Dual-Tier Detection Pipeline",
    role: "Classifier Registry",
    boundary: "Inspection Boundary",
    responsibility:
      "First tier executes sub-5ms compiled regex heuristics for known imperative instruction overrides and delimiter clashing. Second tier executes transformer classification for semantic prompt injections and extraction attempts.",
  },
  {
    name: "Deterministic Policy Decision Point",
    role: "PDP",
    boundary: "Decision Boundary",
    responsibility:
      "Applies explicit, deterministic rules and risk scoring. Maps detection findings and caller roles to an immutable decision disposition: ALLOW, BLOCK, or REVIEW. Does not employ probabilistic LLM self-reflection.",
  },
  {
    name: "Egress Tool Policy Enforcement Point",
    role: "PEP (Egress)",
    boundary: "Tool / Execution Boundary",
    responsibility:
      "Intercepts model-generated tool calls before dispatch. Enforces parameter schema validation, checks role-based access permissions (RBAC), and verifies cryptographic tokens for sensitive operations.",
  },
  {
    name: "Human-in-the-Loop Hold Gate",
    role: "Cryptographic Authorization",
    boundary: "Two-Man Rule Boundary",
    responsibility:
      "Suspends execution of high-risk actions (e.g. bulk export, deletion). Issues a single-use approval request requiring an authorized supervisor to verify parameters and issue a signed execution token.",
  },
  {
    name: "Append-Only Audit & Telemetry Store",
    role: "Telemetry Store",
    boundary: "Persistence Boundary",
    responsibility:
      "Persists structured, sanitized records in PostgreSQL. Records request IDs, component decisions, latency timings, and SHA-256 parameter digests for compliance verification and incident triage.",
  },
];

export default function ArchitecturePage() {
  return (
    <div className="w-full max-w-4xl mx-auto px-6 pt-16 pb-24 space-y-16">
      {/* Page Header */}
      <div className="space-y-4">
        <div className="text-xs uppercase tracking-wider text-zinc-500 font-medium">System Architecture</div>
        <h1 className="text-3xl sm:text-4xl font-medium tracking-tight text-[#f2f2f0]">
          Separation of decision and enforcement.
        </h1>
        <p className="text-base text-[#9d9ea1] leading-relaxed max-w-2xl">
          SentinelLLM adapts the proven RFC 2904 Policy Enforcement Point (PEP) and Policy Decision Point (PDP) model for modern LLM applications and autonomous agents.
        </p>
      </div>

      {/* Textual Architecture Diagram */}
      <section className="space-y-4 py-8 border-y border-[#161719]">
        <div className="text-xs uppercase tracking-wider text-zinc-500 font-medium">Execution Topology</div>

        <div className="p-6 rounded bg-[#0b0c0d] border border-[#1e2023] font-mono text-xs text-[#9d9ea1] overflow-x-auto leading-relaxed">
          <pre>{`
  [ CLIENT / USER / RAG SOURCE ]
                │
                ▼
  [ 01. INGRESS PEP ] ──────► [ 02. DUAL-TIER DETECTORS ] (Regex <5ms + RoBERTa)
                │                               │
                │◄──────────────────────────────┘
                ▼
  [ 03. POLICY DECISION POINT (PDP) ]
        ├── BLOCK   ──► [ Return 403 Denial & Quarantine Tokens ]
        └── ALLOW   ──► [ Dispatch to LLM Adapter / Model Inference ]
                              │
                              ▼
                        [ PROPOSED TOOL CALL ]
                              │
                              ▼
  [ 04. EGRESS PEP ] ───────► Check RBAC & Argument Schema
        ├── HIGH-RISK ──────► [ 05. HUMAN APPROVAL GATE ] (Signed Token Required)
        └── AUTHORIZED ─────► [ 06. TOOL DISPATCH ] (Isolated Execution)
                              │
                              ▼
  [ 07. AUDIT TELEMETRY ] ──► [ POSTGRESQL APPEND-ONLY STORE ]
`}</pre>
        </div>
      </section>

      {/* Component Responsibilities */}
      <section className="space-y-8">
        <div className="space-y-1">
          <div className="text-xs uppercase tracking-wider text-zinc-500 font-medium">Subsystems</div>
          <h2 className="text-xl font-medium tracking-tight text-[#f2f2f0]">Component Responsibilities</h2>
        </div>

        <div className="space-y-8">
          {COMPONENTS.map((c) => (
            <div key={c.name} className="space-y-1.5 pb-6 border-b border-[#161719] last:border-0">
              <div className="flex flex-col sm:flex-row sm:items-baseline justify-between gap-1">
                <h3 className="text-sm font-medium text-[#f2f2f0]">{c.name}</h3>
                <span className="text-xs font-mono text-zinc-500">{c.role}</span>
              </div>
              <div className="text-xs text-zinc-500 font-mono">Boundary: {c.boundary}</div>
              <p className="text-xs text-[#9d9ea1] leading-relaxed pt-1">{c.responsibility}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Navigation link */}
      <div className="pt-8 border-t border-[#161719] flex items-center justify-between text-xs text-[#9d9ea1]">
        <Link href="/" className="hover:text-white transition-colors">
          &larr; Return to Home
        </Link>
        <Link href="/evaluations" className="hover:text-white transition-colors">
          Empirical Evaluations &rarr;
        </Link>
      </div>
    </div>
  );
}
