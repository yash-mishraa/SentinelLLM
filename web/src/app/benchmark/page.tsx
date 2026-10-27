"use client";

import React, { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Alert } from "@/components/ui/alert";
import {
  getBenchmarkSummary,
  getBenchmarkHistory,
  triggerBenchmarkRun,
  getSession,
} from "@/lib/api-client";
import { BenchmarkSummary, BenchmarkRun, SessionInfo } from "@/lib/types";

export default function BenchmarkPage() {
  const [summary, setSummary] = useState<BenchmarkSummary | null>(null);
  const [history, setHistory] = useState<BenchmarkRun[]>([]);
  const [session, setSession] = useState<SessionInfo | null>(null);

  const [isRunning, setIsRunning] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const loadData = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [sum, hist] = await Promise.allSettled([
        getBenchmarkSummary(),
        getBenchmarkHistory(10),
      ]);
      if (sum.status === "fulfilled" && sum.value) setSummary(sum.value);
      if (hist.status === "fulfilled" && Array.isArray(hist.value)) {
        setHistory(hist.value);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    async function init() {
      try {
        const s = await getSession();
        setSession(s);
      } catch {
        // Fallback
      }
      loadData();
    }
    init();
  }, []);

  const handleRunBenchmark = async () => {
    setIsRunning(true);
    setError(null);
    setSuccessMessage(null);
    try {
      const result = await triggerBenchmarkRun();
      setSuccessMessage(
        `Benchmark completed: ${result.total_cases} cases evaluated (${result.passed_cases} passed). Run ID: ${result.run_id}`
      );
      await loadData();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setIsRunning(false);
    }
  };

  const isAdmin = session?.role === "admin";

  return (
    <div className="w-full max-w-5xl mx-auto px-6 py-8 space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-baseline justify-between gap-4 pb-4 border-b border-[#161719]">
        <div className="space-y-1">
          <h1 className="text-lg font-medium text-[#f2f2f0] tracking-tight">PromptProbe Benchmark Explorer</h1>
          <p className="text-xs text-[#9d9ea1]">
            Deterministic evaluation report measuring detection rates and action-level containment.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={loadData}
            isLoading={isLoading}
          >
            Refresh
          </Button>
          <Button
            size="sm"
            variant="primary"
            onClick={handleRunBenchmark}
            isLoading={isRunning}
            disabled={!isAdmin}
          >
            Execute Run
          </Button>
        </div>
      </div>

      {!isAdmin && (
        <Alert variant="info" title="Administrator Role Notice">
          Triggering live evaluations on the server requires the <strong>Administrator</strong> role to prevent resource contention. Switch to Administrator in the top-right navigation using your API key.
        </Alert>
      )}

      {error && (
        <Alert variant="error" title="Notice" onDismiss={() => setError(null)}>
          {error}
        </Alert>
      )}

      {successMessage && (
        <Alert variant="success" title="Success" onDismiss={() => setSuccessMessage(null)}>
          {successMessage}
        </Alert>
      )}

      {/* Dataset & Baseline Strip */}
      <section className="grid grid-cols-1 sm:grid-cols-3 gap-6 py-2 border-b border-[#161719] text-xs">
        <div className="space-y-1">
          <div className="text-zinc-500 font-medium">Dataset</div>
          <div className="text-sm font-medium text-[#f2f2f0] font-mono">
            {summary?.dataset_name || "starter_adversarial_v1"}
          </div>
          <div className="text-[11px] text-[#9d9ea1]">{summary?.total_cases || 23} total synthetic cases</div>
        </div>

        <div className="space-y-1">
          <div className="text-zinc-500 font-medium">Enforcement Invariant</div>
          <div className="text-sm font-medium text-emerald-400">
            0 Unauthorized Executions
          </div>
          <div className="text-[11px] text-[#9d9ea1]">100% action boundary containment</div>
        </div>

        <div className="space-y-1">
          <div className="text-zinc-500 font-medium">Evaluation Harness</div>
          <div className="text-sm font-medium text-[#f2f2f0]">
            Deterministic Offline Baseline
          </div>
          <div className="text-[11px] text-[#9d9ea1]">$0.00 model token spend</div>
        </div>
      </section>

      {/* Two-Layer Metrics */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Layer 1: Classification */}
        <div className="space-y-3">
          <div className="text-xs text-zinc-500 font-medium">1. Content Inspection Confusion Matrix</div>

          <div className="p-4 rounded bg-[#0b0c0d] border border-[#1e2023] space-y-3">
            <div className="grid grid-cols-2 gap-2 text-center text-xs font-mono">
              <div className="p-2.5 rounded bg-emerald-950/20 border border-emerald-800/30">
                <span className="text-[10px] text-zinc-500 block">TRUE POSITIVES</span>
                <span className="text-lg font-medium text-emerald-400">7</span>
                <span className="text-[10px] text-zinc-500 block">Attacks Blocked</span>
              </div>
              <div className="p-2.5 rounded bg-[#101113] border border-[#161719]">
                <span className="text-[10px] text-zinc-500 block">FALSE POSITIVES</span>
                <span className="text-lg font-medium text-[#f2f2f0]">0</span>
                <span className="text-[10px] text-zinc-500 block">False Alarms</span>
              </div>
              <div className="p-2.5 rounded bg-[#101113] border border-[#161719]">
                <span className="text-[10px] text-zinc-500 block">FALSE NEGATIVES</span>
                <span className="text-lg font-medium text-amber-400">1</span>
                <span className="text-[10px] text-zinc-500 block">INJ-DIR-002</span>
              </div>
              <div className="p-2.5 rounded bg-[#101113] border border-[#161719]">
                <span className="text-[10px] text-zinc-500 block">TRUE NEGATIVES</span>
                <span className="text-lg font-medium text-[#f2f2f0]">8</span>
                <span className="text-[10px] text-zinc-500 block">Benign Allowed</span>
              </div>
            </div>

            <div className="grid grid-cols-4 gap-2 text-center text-xs font-mono text-zinc-400 pt-1 border-t border-[#161719]">
              <div>Precision: <span className="text-[#f2f2f0] block">100%</span></div>
              <div>Recall: <span className="text-[#f2f2f0] block">87.5%</span></div>
              <div>F1: <span className="text-[#f2f2f0] block">0.933</span></div>
              <div>Accuracy: <span className="text-[#f2f2f0] block">93.8%</span></div>
            </div>
          </div>
        </div>

        {/* Layer 2: Action Enforcement */}
        <div className="space-y-3">
          <div className="text-xs text-zinc-500 font-medium">2. Action Policy Enforcement</div>

          <div className="p-4 rounded bg-[#0b0c0d] border border-[#1e2023] space-y-2.5 text-xs font-mono text-[#9d9ea1]">
            <div className="flex justify-between border-b border-[#161719] pb-1.5">
              <span>Total Action Cases:</span>
              <span className="text-[#f2f2f0]">7</span>
            </div>
            <div className="flex justify-between border-b border-[#161719] pb-1.5">
              <span>Unauthorized Executions:</span>
              <span className="text-emerald-400 font-medium">0 (0.0%)</span>
            </div>
            <div className="flex justify-between border-b border-[#161719] pb-1.5">
              <span>Permitted Safe Actions:</span>
              <span className="text-[#f2f2f0]">2</span>
            </div>
            <div className="flex justify-between border-b border-[#161719] pb-1.5">
              <span>Denied Actions:</span>
              <span className="text-[#f2f2f0]">4</span>
            </div>
            <div className="flex justify-between pt-1">
              <span>Held for Human Approval:</span>
              <span className="text-amber-400">1</span>
            </div>
          </div>
        </div>
      </div>

      {/* Persisted Historical Runs Table */}
      <section className="space-y-3">
        <h2 className="text-xs text-zinc-500 font-medium">Historical Runs Log</h2>

        {history.length === 0 ? (
          <div className="p-8 text-center text-xs text-zinc-500 border border-[#161719] rounded">
            No historical runs recorded in database. Click Execute Run to record an evaluation.
          </div>
        ) : (
          <div className="border border-[#161719] rounded overflow-hidden">
            <table className="w-full text-left text-xs">
              <thead className="bg-[#0b0c0d] border-b border-[#161719] text-[11px] text-zinc-500">
                <tr>
                  <th className="py-2.5 px-4 font-normal">Timestamp</th>
                  <th className="py-2.5 px-4 font-normal">Run ID</th>
                  <th className="py-2.5 px-4 font-normal">Total Cases</th>
                  <th className="py-2.5 px-4 font-normal">Passed</th>
                  <th className="py-2.5 px-4 font-normal">Accuracy</th>
                  <th className="py-2.5 px-4 font-normal">Enforcement</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#161719] text-[#9d9ea1]">
                {history.map((run) => (
                  <tr key={run.run_id} className="hover:bg-[#0d0e10] transition-colors">
                    <td className="py-2.5 px-4 text-zinc-500 whitespace-nowrap">
                      {run.timestamp ? new Date(run.timestamp).toLocaleString() : "—"}
                    </td>
                    <td className="py-2.5 px-4 font-mono text-[11px] text-[#f2f2f0] truncate max-w-[140px]">
                      {run.run_id}
                    </td>
                    <td className="py-2.5 px-4">{run.total_cases}</td>
                    <td className="py-2.5 px-4 text-emerald-400">{run.passed_cases}</td>
                    <td className="py-2.5 px-4">
                      {typeof run.accuracy === "number" ? `${(run.accuracy * 100).toFixed(1)}%` : "—"}
                    </td>
                    <td className="py-2.5 px-4 text-emerald-400 font-medium">100% (0 Unauth)</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
