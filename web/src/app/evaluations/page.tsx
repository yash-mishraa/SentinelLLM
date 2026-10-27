import React from "react";
import Link from "next/link";

export const metadata = {
  title: "Evaluations — SentinelLLM",
  description: "PromptProbe starter adversarial benchmark results, confusion matrix, and transparent known limitations.",
};

export default function EvaluationsPage() {
  return (
    <div className="w-full max-w-4xl mx-auto px-6 pt-16 pb-24 space-y-16">
      {/* Header */}
      <div className="space-y-4">
        <div className="text-xs uppercase tracking-wider text-zinc-500 font-medium">Empirical Evaluations</div>
        <h1 className="text-3xl sm:text-4xl font-medium tracking-tight text-[#f2f2f0]">
          Adversarial benchmark & honest limitations.
        </h1>
        <p className="text-base text-[#9d9ea1] leading-relaxed max-w-2xl">
          SentinelLLM is evaluated using PromptProbe, an offline reproducible test harness. We measure probabilistic content detection alongside deterministic action enforcement.
        </p>
      </div>

      {/* Dataset & Methodology */}
      <section className="space-y-4 py-8 border-y border-[#161719]">
        <div className="text-xs uppercase tracking-wider text-zinc-500 font-medium">Test Methodology</div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-6 text-xs text-[#9d9ea1]">
          <div className="space-y-1">
            <div className="text-[#f2f2f0] font-medium">Dataset</div>
            <div>starter_adversarial_v1.json</div>
            <div className="text-zinc-500">23 single cases · 10 multi-turn scenarios</div>
          </div>
          <div className="space-y-1">
            <div className="text-[#f2f2f0] font-medium">Execution Mode</div>
            <div>Offline Deterministic Baseline</div>
            <div className="text-zinc-500">Zero network dependency · $0.00 spend</div>
          </div>
          <div className="space-y-1">
            <div className="text-[#f2f2f0] font-medium">Enforcement Invariant</div>
            <div className="text-emerald-400">0 Unauthorized Executions</div>
            <div className="text-zinc-500">100% action boundary containment</div>
          </div>
        </div>
      </section>

      {/* Detection Layer Confusion Matrix */}
      <section className="space-y-6">
        <div className="space-y-1">
          <div className="text-xs uppercase tracking-wider text-zinc-500 font-medium">Layer 1: Content Inspection</div>
          <h2 className="text-xl font-medium tracking-tight text-[#f2f2f0]">
            Classification performance across 16 inbound content cases
          </h2>
          <p className="text-xs text-[#9d9ea1] max-w-2xl">
            Evaluates the ability of regex heuristics and classifiers to detect direct imperative prompt injections, persona hijacking, and instruction extraction.
          </p>
        </div>

        {/* Minimal Confusion Matrix */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 p-5 rounded bg-[#0b0c0d] border border-[#1e2023] text-center">
          <div className="space-y-1">
            <div className="text-[11px] font-mono text-zinc-500">TRUE POSITIVES</div>
            <div className="text-2xl font-mono text-emerald-400 font-medium">7</div>
            <div className="text-[11px] text-zinc-500">Injections Blocked</div>
          </div>
          <div className="space-y-1">
            <div className="text-[11px] font-mono text-zinc-500">FALSE POSITIVES</div>
            <div className="text-2xl font-mono text-[#f2f2f0] font-medium">0</div>
            <div className="text-[11px] text-zinc-500">Benign False Alarms</div>
          </div>
          <div className="space-y-1">
            <div className="text-[11px] font-mono text-zinc-500">FALSE NEGATIVES</div>
            <div className="text-2xl font-mono text-amber-400 font-medium">1</div>
            <div className="text-[11px] text-zinc-500">Base64 Evasion</div>
          </div>
          <div className="space-y-1">
            <div className="text-[11px] font-mono text-zinc-500">TRUE NEGATIVES</div>
            <div className="text-2xl font-mono text-[#f2f2f0] font-medium">8</div>
            <div className="text-[11px] text-zinc-500">Benign Permitted</div>
          </div>
        </div>

        {/* Metrics Row */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs font-mono text-zinc-400">
          <div>Precision: <span className="text-[#f2f2f0]">100.0%</span></div>
          <div>Recall: <span className="text-[#f2f2f0]">87.5%</span></div>
          <div>F1 Score: <span className="text-[#f2f2f0]">0.9333</span></div>
          <div>Accuracy: <span className="text-[#f2f2f0]">93.75%</span></div>
        </div>
      </section>

      {/* Transparent Limitation Disclosure */}
      <section className="space-y-4 p-6 rounded bg-[#0b0c0d] border border-[#1e2023]">
        <div className="text-xs uppercase tracking-wider text-amber-400 font-medium">Known Failure Analysis</div>
        <h3 className="text-sm font-medium text-[#f2f2f0]">
          False negative on test case <code className="font-mono text-zinc-300">INJ-DIR-002</code>
        </h3>
        <p className="text-xs text-[#9d9ea1] leading-relaxed">
          Case <code className="font-mono text-zinc-300">INJ-DIR-002</code> encodes an imperative prompt injection payload inside Base64 encoding. The sub-5ms regex heuristic tier examines plain text tokens and does not trigger on raw base64 character blocks, passing it as a false negative.
        </p>
        <p className="text-xs text-[#9d9ea1] leading-relaxed">
          This failure highlights why content inspection alone is never sufficient for securing agentic systems. In SentinelLLM, even if an encoded payload convinces an LLM to request an unauthorized tool invocation, the <strong>Egress Policy Enforcement Point</strong> blocks the action deterministically.
        </p>
      </section>

      {/* Layer 2: Action Enforcement */}
      <section className="space-y-4">
        <div className="space-y-1">
          <div className="text-xs uppercase tracking-wider text-zinc-500 font-medium">Layer 2: Action Enforcement</div>
          <h2 className="text-xl font-medium tracking-tight text-[#f2f2f0]">
            Deterministic tool gating results
          </h2>
          <p className="text-xs text-[#9d9ea1] max-w-2xl">
            Across 7 action test cases testing missing permissions, parameter boundary violations, and unapproved sensitive calls:
          </p>
        </div>

        <div className="p-5 rounded bg-[#0b0c0d] border border-[#1e2023] space-y-2 text-xs font-mono text-[#9d9ea1]">
          <div className="flex justify-between border-b border-[#161719] pb-2">
            <span>Total Action Evaluation Cases:</span>
            <span className="text-[#f2f2f0]">7</span>
          </div>
          <div className="flex justify-between border-b border-[#161719] pb-2">
            <span>Unauthorized Executions:</span>
            <span className="text-emerald-400 font-medium">0 (0.00%)</span>
          </div>
          <div className="flex justify-between border-b border-[#161719] pb-2">
            <span>Correctly Permitted Safe Actions:</span>
            <span className="text-[#f2f2f0]">2</span>
          </div>
          <div className="flex justify-between border-b border-[#161719] pb-2">
            <span>Correctly Denied Actions:</span>
            <span className="text-[#f2f2f0]">4</span>
          </div>
          <div className="flex justify-between pt-1">
            <span>Held for Supervisor Approval:</span>
            <span className="text-amber-400">1</span>
          </div>
        </div>
      </section>

      {/* Navigation */}
      <div className="pt-8 border-t border-[#161719] flex items-center justify-between text-xs text-[#9d9ea1]">
        <Link href="/architecture" className="hover:text-white transition-colors">
          &larr; Architecture
        </Link>
        <Link href="/console" className="hover:text-white transition-colors">
          Interactive Console &rarr;
        </Link>
      </div>
    </div>
  );
}
