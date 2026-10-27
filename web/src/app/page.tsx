"use client";

import React, { useState } from "react";
import Link from "next/link";
import { ArrowRight, ArrowUpRight } from "lucide-react";
import { Button } from "@/components/ui/button";

const FLOW_STAGES = [
  { key: "01", label: "Input", role: "Untrusted ingress", note: "Prompts, RAG chunks, context" },
  { key: "02", label: "Inspection", role: "Heuristic scanning", note: "Regex fast-path & classifier" },
  { key: "03", label: "Policy", role: "Deterministic decision", note: "Rules, quotas, boundaries" },
  { key: "04", label: "Enforcement", role: "Out-of-band proxy", note: "Tool execution & human hold" },
  { key: "05", label: "Audit", role: "Telemetry ledger", note: "Structured digest in PostgreSQL" },
];

const CAPABILITIES = [
  {
    term: "Inspect",
    title: "Look for suspicious instructions in incoming content",
    description:
      "Scans prompts and retrieved knowledge chunks for direct instruction overrides, persona hijacking, and delimiter collisions before requests touch model infrastructure.",
  },
  {
    term: "Decide",
    title: "Evaluate proposed actions against explicit rules",
    description:
      "Deterministic policy decisions replace probabilistic self-policing. The engine decides whether an action is safe, requires supervisor approval, or must be blocked immediately.",
  },
  {
    term: "Enforce",
    title: "Prevent actions that lack authorization",
    description:
      "A zero-trust Policy Enforcement Point sits between the agent and backing APIs. Tools cannot be executed without parameter validation and verified caller roles.",
  },
  {
    term: "Approve",
    title: "Require a human decision for sensitive operations",
    description:
      "High-impact tool invocations are suspended out-of-band. Execution resumes only after an authorized human reviews the request and signs an approval token.",
  },
  {
    term: "Record",
    title: "Keep a structured record of security decisions",
    description:
      "Every inspection verdict, policy decision, parameter hash, and tool execution is persisted in an append-only audit store with complete contextual telemetry.",
  },
  {
    term: "Evaluate",
    title: "Test the system against known adversarial examples",
    description:
      "PromptProbe harness evaluates detection accuracy and enforcement invariants across 23 single test cases and 10 multi-turn scenarios without live model expenses.",
  },
];

export default function HomePage() {
  const [selectedFlow, setSelectedFlow] = useState(0);

  return (
    <div className="w-full max-w-4xl mx-auto px-6 pt-16 pb-24 space-y-24">
      {/* Hero */}
      <section className="space-y-6">
        <h1 className="text-3xl sm:text-5xl font-medium tracking-tight text-[#f2f2f0] leading-[1.12]">
          A security boundary for LLM-powered systems.
        </h1>

        <p className="text-base sm:text-lg text-[#9d9ea1] leading-relaxed max-w-2xl font-normal">
          SentinelLLM inspects untrusted inputs, enforces deterministic policies at the tool boundary, gates sensitive actions behind human approval, and records security decisions for inspection.
        </p>

        <div className="flex flex-wrap items-center gap-4 pt-2">
          <Link href="/demo">
            <Button size="md" variant="primary">
              Run Interactive Tour &rarr;
            </Button>
          </Link>
          <Link href="/console">
            <Button size="md" variant="secondary">
              Explore Console
            </Button>
          </Link>
          <Link href="/architecture">
            <Button size="md" variant="outline">
              Architecture Overview
            </Button>
          </Link>
        </div>
      </section>

      {/* The Central Visual Flow */}
      <section className="space-y-6 pt-6">
        <div className="space-y-1">
          <div className="text-xs uppercase tracking-wider text-zinc-500 font-medium">Execution Flow</div>
          <p className="text-sm text-[#9d9ea1]">
            How an untrusted input traverses the security boundary
          </p>
        </div>

        {/* Minimal Understated Pipeline Visual */}
        <div className="py-6 border-y border-[#161719]">
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-6 sm:gap-2">
            {FLOW_STAGES.map((s, idx) => (
              <div
                key={s.key}
                onClick={() => setSelectedFlow(idx)}
                className={`cursor-pointer transition-colors space-y-1 ${
                  selectedFlow === idx ? "opacity-100" : "opacity-60 hover:opacity-90"
                }`}
              >
                <div className="text-[11px] font-mono text-zinc-500">{s.key}</div>
                <div className="text-sm font-medium text-[#f2f2f0]">{s.label}</div>
                <div className="text-xs text-[#9d9ea1] leading-tight">{s.role}</div>
              </div>
            ))}
          </div>

          <div className="mt-6 pt-6 border-t border-[#121316] text-xs text-[#9d9ea1] flex items-center justify-between">
            <div>
              <span className="text-[#f2f2f0] font-medium">{FLOW_STAGES[selectedFlow].label} Phase:</span>{" "}
              <span>{FLOW_STAGES[selectedFlow].note}</span>
            </div>
            <Link href="/architecture" className="text-zinc-400 hover:text-white transition-colors">
              Detailed Diagram &rarr;
            </Link>
          </div>
        </div>

        {/* Guided Tour Banner */}
        <div className="p-4 rounded bg-[#0b0c0d] border border-[#1e2023] flex flex-col sm:flex-row sm:items-center justify-between gap-4 text-xs">
          <div>
            <div className="text-sm font-medium text-[#f2f2f0]">Explore the 6-Stage Security Tour</div>
            <div className="text-xs text-[#9d9ea1] mt-0.5">
              Live interactive walkthrough of direct injection defense, RAG isolation, tool authorization, and approval hold gates.
            </div>
          </div>
          <Link href="/demo" className="shrink-0">
            <Button size="sm" variant="primary">
              Launch Tour &rarr;
            </Button>
          </Link>
        </div>
      </section>

      {/* The Core Problem */}
      <section className="space-y-4">
        <div className="text-xs uppercase tracking-wider text-zinc-500 font-medium">The Vulnerability</div>
        <h2 className="text-xl sm:text-2xl font-medium tracking-tight text-[#f2f2f0]">
          Why prompt engineering is not an enforcement boundary.
        </h2>
        <p className="text-sm sm:text-base text-[#9d9ea1] leading-relaxed max-w-3xl">
          Language models cannot reliably differentiate between developer instructions and untrusted data embedded in user inputs, retrieved RAG documents, or tool responses. When applications give models autonomous access to databases, email dispatches, or APIs, system prompts alone cannot guarantee safety.
        </p>
        <p className="text-sm text-[#9d9ea1] leading-relaxed max-w-3xl">
          SentinelLLM introduces hard software boundaries: inspecting text at ingress, evaluating deterministic policies before any tool is invoked, and holding high-consequence operations for human cryptographic sign-off.
        </p>
      </section>

      {/* Six Capabilities (Editorial List, Not Cards) */}
      <section className="space-y-8">
        <div className="space-y-1">
          <div className="text-xs uppercase tracking-wider text-zinc-500 font-medium">Capabilities</div>
          <h2 className="text-xl sm:text-2xl font-medium tracking-tight text-[#f2f2f0]">
            Six layers of runtime governance.
          </h2>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-12 gap-y-10 pt-2">
          {CAPABILITIES.map((c) => (
            <div key={c.term} className="space-y-2">
              <div className="text-xs font-mono text-zinc-500 uppercase">{c.term}</div>
              <h3 className="text-sm font-medium text-[#f2f2f0] leading-snug">{c.title}</h3>
              <p className="text-xs text-[#9d9ea1] leading-relaxed">{c.description}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Evaluation Teaser */}
      <section className="space-y-4 py-8 border-t border-[#161719]">
        <div className="flex flex-col sm:flex-row sm:items-baseline justify-between gap-2">
          <div>
            <div className="text-xs uppercase tracking-wider text-zinc-500 font-medium">Empirical Evaluation</div>
            <h2 className="text-xl font-medium tracking-tight text-[#f2f2f0] mt-1">
              Adversarial benchmark & transparent limits
            </h2>
          </div>
          <Link href="/evaluations" className="text-xs text-[#9d9ea1] hover:text-[#f2f2f0] transition-colors">
            View Evaluation Report &rarr;
          </Link>
        </div>

        <p className="text-xs text-[#9d9ea1] leading-relaxed max-w-2xl">
          Tested against 23 starter cases covering direct injection, jailbreaks, tool abuse, and data exfiltration. Demonstrates 100% precision, 87.5% recall, zero unauthorized tool executions, and full disclosure of a known false negative on Base64 evasion (<code className="font-mono text-zinc-400">INJ-DIR-002</code>).
        </p>
      </section>

      {/* Minimal Footer */}
      <footer className="pt-8 border-t border-[#161719] flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 text-xs text-zinc-500">
        <div>SentinelLLM — Open-source LLM security gateway & PEP</div>
        <div className="flex items-center gap-5">
          <Link href="/architecture" className="hover:text-zinc-300 transition-colors">
            Architecture
          </Link>
          <Link href="/evaluations" className="hover:text-zinc-300 transition-colors">
            Evaluations
          </Link>
          <Link href="/console" className="hover:text-zinc-300 transition-colors">
            Console
          </Link>
          <a
            href="https://github.com/yash-mishraa/SentinelLLM"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-zinc-300 transition-colors"
          >
            GitHub
          </a>
        </div>
      </footer>
    </div>
  );
}
