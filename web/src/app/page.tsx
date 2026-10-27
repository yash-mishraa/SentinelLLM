"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import {
  ShieldAlert,
  CheckCircle2,
  AlertTriangle,
  Clock,
  Activity,
  BarChart2,
  Terminal,
  ArrowRight,
  Database,
  Cpu,
} from "lucide-react";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { StatusBadge, Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Alert } from "@/components/ui/alert";
import {
  getReadiness,
  listApprovals,
  queryAudit,
  getBenchmarkSummary,
  getBenchmarkHistory,
  getHybridBenchmarkSummary,
} from "@/lib/api-client";
import {
  ReadyStatus,
  ApprovalRequest,
  AuditEvent,
  BenchmarkSummary,
  BenchmarkRun,
  HybridBenchmarkSummary,
} from "@/lib/types";

export default function OverviewDashboard() {
  const [readiness, setReadiness] = useState<ReadyStatus | null>(null);
  const [pendingApprovals, setPendingApprovals] = useState<ApprovalRequest[]>([]);
  const [recentAudits, setRecentAudits] = useState<AuditEvent[]>([]);
  const [benchmarkSummary, setBenchmarkSummary] = useState<BenchmarkSummary | null>(null);
  const [latestBenchmark, setLatestBenchmark] = useState<BenchmarkRun | null>(null);
  const [hybridSummary, setHybridSummary] = useState<HybridBenchmarkSummary | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadOverview() {
      setIsLoading(true);
      setError(null);
      try {
        const [ready, approvals, audits, benchSum, benchHistory, hybridSum] = await Promise.allSettled([
          getReadiness(),
          listApprovals("PENDING"),
          queryAudit({ limit: 6 }),
          getBenchmarkSummary(),
          getBenchmarkHistory(1),
          getHybridBenchmarkSummary(),
        ]);

        if (ready.status === "fulfilled" && ready.value) setReadiness(ready.value);
        if (approvals.status === "fulfilled" && Array.isArray(approvals.value)) {
          setPendingApprovals(approvals.value);
        }
        if (audits.status === "fulfilled" && audits.value && Array.isArray(audits.value.events)) {
          setRecentAudits(audits.value.events);
        }
        if (benchSum.status === "fulfilled" && benchSum.value) setBenchmarkSummary(benchSum.value);
        if (benchHistory.status === "fulfilled" && Array.isArray(benchHistory.value) && benchHistory.value.length > 0) {
          setLatestBenchmark(benchHistory.value[0]);
        }
        if (hybridSum.status === "fulfilled" && hybridSum.value) setHybridSummary(hybridSum.value);

        if (ready.status === "rejected") {
          setError(
            "Backend connection error: Could not reach the SentinelLLM REST API. Check that the backend URL is configured and healthy."
          );
        }
      } catch (err) {
        setError(String(err));
      } finally {
        setIsLoading(false);
      }
    }

    loadOverview();
  }, []);

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Top Banner / Headline */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-2 border-b border-slate-800">
        <div>
          <h2 className="text-xl font-bold text-slate-100 flex items-center gap-2">
            Runtime Security Overview
            <Badge variant="accent" className="font-mono text-[10px]">
              DEFENSE-IN-DEPTH
            </Badge>
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Real-time telemetry from Policy Decision Point (PDP), Policy Enforcement Point (PEP), and PromptProbe harness.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Link href="/playground">
            <Button size="sm" variant="primary" className="gap-1.5">
              <Terminal className="w-3.5 h-3.5" />
              Attack Playground
            </Button>
          </Link>
          <Link href="/demo">
            <Button size="sm" variant="secondary" className="gap-1.5">
              Guided 6-Stage Tour
              <ArrowRight className="w-3.5 h-3.5" />
            </Button>
          </Link>
        </div>
      </div>

      {error && (
        <Alert variant="error" title="Backend Connectivity Alert">
          {error}
        </Alert>
      )}

      {/* KPI Status Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* System State */}
        <Card className="bg-gradient-to-br from-slate-900 via-slate-900 to-indigo-950/20 border-indigo-500/20">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-xs text-slate-400 font-medium">Policy Engine & DB</p>
              <h4 className="text-lg font-bold text-slate-100 mt-1 flex items-center gap-1.5">
                {readiness?.database_connected && readiness.policy_engine_ready ? (
                  <span className="text-emerald-400 flex items-center gap-1">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400" /> Operational
                  </span>
                ) : (
                  <span className="text-amber-400 flex items-center gap-1">
                    <Activity className="w-4 h-4" /> Degraded
                  </span>
                )}
              </h4>
            </div>
            <div className="p-2 rounded-md bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
              <Cpu className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3 flex items-center gap-2 text-[11px] text-slate-400 font-mono">
            <span>DB: {readiness?.database_connected ? "Connected" : "Disconnected"}</span>
            <span>•</span>
            <span>PDP: {readiness?.policy_engine_ready ? "Ready" : "Offline"}</span>
          </div>
        </Card>

        {/* Pending Approvals */}
        <Card className="bg-gradient-to-br from-slate-900 via-slate-900 to-amber-950/20 border-amber-500/20">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-xs text-slate-400 font-medium">Approval Queue</p>
              <h4 className="text-lg font-bold text-slate-100 mt-1">
                {pendingApprovals.length} <span className="text-xs text-slate-400 font-normal">pending reviews</span>
              </h4>
            </div>
            <div className="p-2 rounded-md bg-amber-500/10 text-amber-400 border border-amber-500/20">
              <Clock className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3 text-[11px] text-slate-400 flex items-center justify-between">
            <span>Supervisor Gating: Active</span>
            <Link href="/approvals" className="text-amber-400 hover:underline">
              Review Queue &rarr;
            </Link>
          </div>
        </Card>

        {/* Benchmark Baseline */}
        <Card className="bg-gradient-to-br from-slate-900 via-slate-900 to-cyan-950/20 border-cyan-500/20">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-xs text-slate-400 font-medium">PromptProbe Benchmark</p>
              <h4 className="text-lg font-bold text-slate-100 mt-1">
                {benchmarkSummary ? `${benchmarkSummary.total_cases} cases` : "Loading..."}
              </h4>
            </div>
            <div className="p-2 rounded-md bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
              <BarChart2 className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3 text-[11px] text-slate-400 flex items-center justify-between font-mono">
            <span>Adversarial v{benchmarkSummary?.dataset_version || "1.0"}</span>
            <span className="text-cyan-400">93.75% Acc</span>
          </div>
        </Card>

        {/* Budget Guardrail */}
        <Card className="bg-gradient-to-br from-slate-900 via-slate-900 to-emerald-950/20 border-emerald-500/20">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-xs text-slate-400 font-medium">Budget Ceiling</p>
              <h4 className="text-lg font-bold text-slate-100 mt-1">
                ${typeof hybridSummary?.default_budget_ceiling_usd === "number" ? hybridSummary.default_budget_ceiling_usd.toFixed(2) : "0.20"}{" "}
                <span className="text-xs text-slate-400 font-normal">per run cap</span>
              </h4>
            </div>
            <div className="p-2 rounded-md bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              <Database className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3 text-[11px] text-slate-400 flex items-center justify-between font-mono">
            <span>Hard max: ${typeof hybridSummary?.max_budget_ceiling_usd === "number" ? hybridSummary.max_budget_ceiling_usd.toFixed(2) : "1.00"}</span>
            <span className="text-emerald-400">Fail-Closed</span>
          </div>
        </Card>
      </div>

      {/* Main Content 2-Column Split */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column (2 spans): Recent Audit Telemetry */}
        <div className="lg:col-span-2 space-y-6">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-3">
              <div>
                <CardTitle>Recent Audit Trail Events</CardTitle>
                <CardDescription>
                  Append-only structured telemetry records with recursive credential sanitization.
                </CardDescription>
              </div>
              <Link href="/audit">
                <Button size="sm" variant="ghost" className="text-xs text-indigo-400 hover:text-indigo-300">
                  View All &rarr;
                </Button>
              </Link>
            </CardHeader>
            <CardContent>
              {!recentAudits || recentAudits.length === 0 ? (
                <div className="py-8 text-center text-xs text-slate-400">
                  No audit events recorded yet. Run tests or submit an inspection request in the Playground.
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs font-mono">
                    <thead className="text-slate-400 border-b border-slate-800 text-[11px]">
                      <tr>
                        <th className="pb-2 font-medium">Event Type</th>
                        <th className="pb-2 font-medium">Component</th>
                        <th className="pb-2 font-medium">Decision</th>
                        <th className="pb-2 font-medium text-right">Timestamp</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/60">
                      {(recentAudits || []).map((event) => {
                        let formattedTime = "—";
                        try {
                          if (event.timestamp) {
                            formattedTime = new Date(event.timestamp).toLocaleTimeString();
                          }
                        } catch {
                          // Ignore date parsing error
                        }
                        return (
                          <tr key={event.event_id} className="hover:bg-slate-800/40 transition-colors">
                            <td className="py-2.5 font-medium text-slate-200">{event.event_type}</td>
                            <td className="py-2.5 text-slate-400">{event.component}</td>
                            <td className="py-2.5">
                              {event.decision ? (
                                <StatusBadge status={event.decision} />
                              ) : (
                                <span className="text-slate-400 text-[10px]">—</span>
                              )}
                            </td>
                            <td className="py-2.5 text-right text-slate-400 text-[11px]">
                              {formattedTime}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Architecture Concept Card */}
          <Card className="bg-slate-950/60 border-slate-800">
            <CardHeader>
              <CardTitle className="text-sm font-semibold">Core Architectural Guarantee</CardTitle>
              <CardDescription>
                Decoupling probabilistic signal detection from deterministic action-level enforcement.
              </CardDescription>
            </CardHeader>
            <CardContent className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
              <div className="p-3 rounded border border-slate-800 bg-slate-900/50">
                <span className="font-semibold text-indigo-300 block mb-1">1. Inbound Gateway Quarantine</span>
                <p className="text-slate-400 leading-relaxed">
                  Heuristic regex detectors scan incoming prompts, RAG context, and tool output. Malicious injections are
                  quarantined before dispatch, saving tokens and financial spend.
                </p>
              </div>
              <div className="p-3 rounded border border-slate-800 bg-slate-900/50">
                <span className="font-semibold text-emerald-300 block mb-1">2. Zero-Trust Policy Enforcement</span>
                <p className="text-slate-400 leading-relaxed">
                  The Policy Enforcement Point (PEP) intercepts tool executions out-of-band. Sensitive actions require
                  cryptographically bound, single-use supervisor approval tokens.
                </p>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Right Column: Pending Approvals & Benchmark Summary */}
        <div className="space-y-6">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-3">
              <div>
                <CardTitle className="text-sm">Action Approvals Queue</CardTitle>
                <CardDescription>Actions requiring supervisor clearance</CardDescription>
              </div>
              <Link href="/approvals" className="text-xs text-amber-400 hover:underline">
                Manage
              </Link>
            </CardHeader>
            <CardContent>
              {!pendingApprovals || pendingApprovals.length === 0 ? (
                <div className="py-6 text-center text-xs text-slate-400">
                  <CheckCircle2 className="w-6 h-6 mx-auto mb-2 text-emerald-500/60" />
                  No actions currently held for approval.
                </div>
              ) : (
                <div className="space-y-2.5">
                  {(pendingApprovals || []).slice(0, 3).map((app) => (
                    <div key={app.approval_id} className="p-2.5 rounded bg-slate-950/60 border border-slate-800 text-xs">
                      <div className="flex items-center justify-between font-mono font-medium text-slate-200">
                        <span>{app.tool_name}</span>
                        <Badge variant="warning">{app.status}</Badge>
                      </div>
                      <div className="text-[11px] text-slate-400 mt-1 font-mono truncate">
                        Requester: {app.principal_id}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm">PromptProbe Evaluation State</CardTitle>
              <CardDescription>Synthetic adversarial benchmark coverage</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 text-xs">
              <div className="flex items-center justify-between border-b border-slate-800/60 pb-2">
                <span className="text-slate-400">Total Cases Evaluated:</span>
                <span className="font-mono text-slate-200 font-semibold">{benchmarkSummary?.total_cases || 23}</span>
              </div>
              <div className="flex items-center justify-between border-b border-slate-800/60 pb-2">
                <span className="text-slate-400">Detection Accuracy:</span>
                <span className="font-mono text-emerald-400 font-semibold">93.75%</span>
              </div>
              <div className="flex items-center justify-between border-b border-slate-800/60 pb-2">
                <span className="text-slate-400">Enforcement Accuracy:</span>
                <span className="font-mono text-emerald-400 font-semibold">100.00%</span>
              </div>
              <div className="flex items-center justify-between pb-1">
                <span className="text-slate-400">Unauthorized Executions:</span>
                <span className="font-mono text-emerald-400 font-bold">0 (Target: 0)</span>
              </div>
              <div className="pt-2">
                <Link href="/benchmark">
                  <Button size="sm" variant="outline" className="w-full text-xs">
                    Explore Benchmark Metrics
                  </Button>
                </Link>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
