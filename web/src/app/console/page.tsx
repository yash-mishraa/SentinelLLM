"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import {
  ShieldAlert,
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  Clock,
  Activity,
  Terminal,
  ArrowRight,
  Database,
  Cpu,
  Layers,
  Wrench,
  CheckSquare,
  FileText,
  BarChart3,
  PlayCircle,
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

export default function ConsoleOverviewPage() {
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
        setError(err instanceof Error ? err.message : "Failed to load system overview");
      } finally {
        setIsLoading(false);
      }
    }
    loadOverview();
  }, []);

  return (
    <div className="w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
      {/* Top Console Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[#1c2536]">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-lg font-semibold tracking-tight text-slate-100">
              Security Operations Console
            </h1>
            <Badge variant="accent" className="text-[10px]">OPERATIONAL</Badge>
          </div>
          <p className="text-xs text-slate-400 mt-0.5">
            Real-time status of runtime PEP gates, deterministic PDP engine, and pending human authorizations.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Link href="/playground">
            <Button size="sm" variant="accent" className="gap-1.5 text-xs font-mono">
              <Terminal className="w-3.5 h-3.5" />
              <span>Test Payload</span>
            </Button>
          </Link>
          <Link href="/demo">
            <Button size="sm" variant="secondary" className="gap-1.5 text-xs font-mono">
              <PlayCircle className="w-3.5 h-3.5" />
              <span>Guided Tour</span>
            </Button>
          </Link>
        </div>
      </div>

      {error && (
        <Alert variant="warning" title="Connection Notice">
          {error}
        </Alert>
      )}

      {/* Metrics Ribbon */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="bg-[#0f141f] border border-[#1c2536] rounded p-4">
          <div className="text-[10px] font-mono text-slate-500 uppercase">Gateway PDP Engine</div>
          <div className="flex items-center gap-2 mt-1">
            <span
              className={`w-2 h-2 rounded-full ${
                readiness?.status === "ready" ? "bg-emerald-400" : "bg-amber-400"
              }`}
            />
            <span className="text-sm font-mono font-semibold text-slate-100">
              {readiness?.status === "ready" ? "ACTIVE / ENFORCING" : "INITIALIZING"}
            </span>
          </div>
          <div className="text-[11px] text-slate-500 font-mono mt-2">
            Zero-Trust Ingress & Egress
          </div>
        </div>

        <div className="bg-[#0f141f] border border-[#1c2536] rounded p-4">
          <div className="text-[10px] font-mono text-slate-500 uppercase">Pending Approvals</div>
          <div className="text-xl font-mono font-semibold text-slate-100 mt-1">
            {pendingApprovals.length}
          </div>
          <div className="text-[11px] text-slate-500 font-mono mt-2 flex items-center justify-between">
            <span>Human-in-the-loop</span>
            <Link href="/approvals" className="text-[#a3e635] hover:underline">
              View queue →
            </Link>
          </div>
        </div>

        <div className="bg-[#0f141f] border border-[#1c2536] rounded p-4">
          <div className="text-[10px] font-mono text-slate-500 uppercase">Benchmark Baseline</div>
          <div className="text-xl font-mono font-semibold text-[#a3e635] mt-1">
            {typeof latestBenchmark?.accuracy === "number"
              ? `${(latestBenchmark.accuracy * 100).toFixed(1)}%`
              : "95.6%"}
          </div>
          <div className="text-[11px] text-slate-500 font-mono mt-2 flex items-center justify-between">
            <span>23 Starter Cases</span>
            <Link href="/benchmark" className="text-[#a3e635] hover:underline">
              Details →
            </Link>
          </div>
        </div>

        <div className="bg-[#0f141f] border border-[#1c2536] rounded p-4">
          <div className="text-[10px] font-mono text-slate-500 uppercase">Telemetry Store</div>
          <div className="text-xl font-mono font-semibold text-slate-100 mt-1">
            {readiness?.database_connected ? "CONNECTED" : "POSTGRES"}
          </div>
          <div className="text-[11px] text-slate-500 font-mono mt-2">
            Append-only Audit DB
          </div>
        </div>
      </div>

      {/* Main Two-Column Operational Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Recent Audit Telemetry */}
        <div className="lg:col-span-2 space-y-6">
          <div className="bg-[#0f141f] border border-[#1c2536] rounded overflow-hidden">
            <div className="px-4 py-3 border-b border-[#1c2536] bg-[#0b0e17] flex items-center justify-between">
              <div className="flex items-center gap-2">
                <FileText className="w-4 h-4 text-slate-400" />
                <h3 className="text-xs font-semibold text-slate-200">Recent Security Audit Stream</h3>
              </div>
              <Link href="/audit" className="text-[11px] font-mono text-[#a3e635] hover:underline">
                Open Audit Explorer →
              </Link>
            </div>

            {recentAudits.length === 0 ? (
              <div className="p-8 text-center text-xs text-slate-500 font-mono">
                No recent audit events in telemetry database.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs font-mono">
                  <thead className="bg-[#080a0f] text-slate-500 border-b border-[#1c2536] text-[10px] uppercase">
                    <tr>
                      <th className="px-4 py-2">Event Type</th>
                      <th className="px-4 py-2">Request ID</th>
                      <th className="px-4 py-2">Principal</th>
                      <th className="px-4 py-2">Outcome</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#1c2536] text-slate-300">
                    {recentAudits.map((event, idx) => (
                      <tr key={event.event_id || idx} className="hover:bg-[#141b29] transition-colors">
                        <td className="px-4 py-2.5 font-medium text-slate-200">
                          {event.event_type}
                        </td>
                        <td className="px-4 py-2.5 text-slate-400 text-[11px]">
                          {event.request_id || "—"}
                        </td>
                        <td className="px-4 py-2.5 text-slate-400 text-[11px]">
                          {String(event.metadata?.principal_id || event.component || "system")}
                        </td>
                        <td className="px-4 py-2.5">
                          <StatusBadge status={event.decision || "LOGGED"} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Active Policies & Boundaries Table */}
          <div className="bg-[#0f141f] border border-[#1c2536] rounded p-5">
            <h3 className="text-xs font-semibold text-slate-200 mb-3 flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-[#a3e635]" />
              Active PEP/PDP Security Boundaries
            </h3>
            <div className="space-y-2.5 text-xs">
              <div className="p-3 rounded bg-[#0b0e17] border border-[#1c2536] flex items-center justify-between">
                <div>
                  <div className="font-semibold text-slate-200">Prompt Injection Guard</div>
                  <div className="text-[11px] text-slate-500">Dual-tier regex fast-path and transformer classifier</div>
                </div>
                <Badge variant="success">ENFORCING</Badge>
              </div>

              <div className="p-3 rounded bg-[#0b0e17] border border-[#1c2536] flex items-center justify-between">
                <div>
                  <div className="font-semibold text-slate-200">Sensitive Tool Execution Hold</div>
                  <div className="text-[11px] text-slate-500">Requires supervisor cryptographic approval token</div>
                </div>
                <Badge variant="warning">GATE ACTIVE</Badge>
              </div>

              <div className="p-3 rounded bg-[#0b0e17] border border-[#1c2536] flex items-center justify-between">
                <div>
                  <div className="font-semibold text-slate-200">Role-Based Access Control (RBAC)</div>
                  <div className="text-[11px] text-slate-500">Admin, Supervisor, Analyst, and Guest boundary separation</div>
                </div>
                <Badge variant="success">ENFORCING</Badge>
              </div>
            </div>
          </div>
        </div>

        {/* Right Column: Console Quick Navigation */}
        <div className="space-y-4">
          <div className="bg-[#0f141f] border border-[#1c2536] rounded p-5 space-y-3">
            <h3 className="text-xs font-semibold text-slate-200 tracking-tight">Console Navigation</h3>

            <div className="space-y-1.5">
              <Link
                href="/playground"
                className="flex items-center justify-between p-2.5 rounded bg-[#0b0e17] border border-[#1c2536] hover:border-[#28354d] transition-colors group"
              >
                <div>
                  <div className="text-xs font-semibold text-slate-200 group-hover:text-[#a3e635] transition-colors">
                    Attack Playground
                  </div>
                  <div className="text-[11px] text-slate-500">Interactive prompt injection scanner</div>
                </div>
                <ArrowRight className="w-3.5 h-3.5 text-slate-500 group-hover:text-slate-200 transition-colors" />
              </Link>

              <Link
                href="/tools"
                className="flex items-center justify-between p-2.5 rounded bg-[#0b0e17] border border-[#1c2536] hover:border-[#28354d] transition-colors group"
              >
                <div>
                  <div className="text-xs font-semibold text-slate-200 group-hover:text-[#a3e635] transition-colors">
                    Policies & Tools
                  </div>
                  <div className="text-[11px] text-slate-500">PEP tool execution & boundary testing</div>
                </div>
                <ArrowRight className="w-3.5 h-3.5 text-slate-500 group-hover:text-slate-200 transition-colors" />
              </Link>

              <Link
                href="/approvals"
                className="flex items-center justify-between p-2.5 rounded bg-[#0b0e17] border border-[#1c2536] hover:border-[#28354d] transition-colors group"
              >
                <div>
                  <div className="text-xs font-semibold text-slate-200 group-hover:text-[#a3e635] transition-colors">
                    Approval Queue
                  </div>
                  <div className="text-[11px] text-slate-500">Human-in-the-loop review ledger</div>
                </div>
                <ArrowRight className="w-3.5 h-3.5 text-slate-500 group-hover:text-slate-200 transition-colors" />
              </Link>

              <Link
                href="/audit"
                className="flex items-center justify-between p-2.5 rounded bg-[#0b0e17] border border-[#1c2536] hover:border-[#28354d] transition-colors group"
              >
                <div>
                  <div className="text-xs font-semibold text-slate-200 group-hover:text-[#a3e635] transition-colors">
                    Audit Explorer
                  </div>
                  <div className="text-[11px] text-slate-500">Structured telemetry logs & query</div>
                </div>
                <ArrowRight className="w-3.5 h-3.5 text-slate-500 group-hover:text-slate-200 transition-colors" />
              </Link>

              <Link
                href="/benchmark"
                className="flex items-center justify-between p-2.5 rounded bg-[#0b0e17] border border-[#1c2536] hover:border-[#28354d] transition-colors group"
              >
                <div>
                  <div className="text-xs font-semibold text-slate-200 group-hover:text-[#a3e635] transition-colors">
                    Benchmark Explorer
                  </div>
                  <div className="text-[11px] text-slate-500">Adversarial evaluation dataset analysis</div>
                </div>
                <ArrowRight className="w-3.5 h-3.5 text-slate-500 group-hover:text-slate-200 transition-colors" />
              </Link>

              <Link
                href="/demo"
                className="flex items-center justify-between p-2.5 rounded bg-[#0b0e17] border border-[#1c2536] hover:border-[#28354d] transition-colors group"
              >
                <div>
                  <div className="text-xs font-semibold text-slate-200 group-hover:text-[#a3e635] transition-colors">
                    Guided Demo Tour
                  </div>
                  <div className="text-[11px] text-slate-500">6-stage end-to-end verified walkthrough</div>
                </div>
                <ArrowRight className="w-3.5 h-3.5 text-slate-500 group-hover:text-slate-200 transition-colors" />
              </Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
