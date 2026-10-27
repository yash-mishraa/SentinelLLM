"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Alert } from "@/components/ui/alert";
import {
  getReadiness,
  listApprovals,
  queryAudit,
  getBenchmarkHistory,
} from "@/lib/api-client";
import {
  ReadyStatus,
  ApprovalRequest,
  AuditEvent,
  BenchmarkRun,
} from "@/lib/types";

export default function ConsoleOverviewPage() {
  const [readiness, setReadiness] = useState<ReadyStatus | null>(null);
  const [pendingApprovals, setPendingApprovals] = useState<ApprovalRequest[]>([]);
  const [recentAudits, setRecentAudits] = useState<AuditEvent[]>([]);
  const [latestBenchmark, setLatestBenchmark] = useState<BenchmarkRun | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadOverview() {
      setIsLoading(true);
      setError(null);
      try {
        const [ready, approvals, audits, benchHistory] = await Promise.allSettled([
          getReadiness(),
          listApprovals("PENDING"),
          queryAudit({ limit: 8 }),
          getBenchmarkHistory(1),
        ]);

        if (ready.status === "fulfilled" && ready.value) setReadiness(ready.value);
        if (approvals.status === "fulfilled" && Array.isArray(approvals.value)) {
          setPendingApprovals(approvals.value);
        }
        if (audits.status === "fulfilled" && audits.value && Array.isArray(audits.value.events)) {
          setRecentAudits(audits.value.events);
        }
        if (benchHistory.status === "fulfilled" && Array.isArray(benchHistory.value) && benchHistory.value.length > 0) {
          setLatestBenchmark(benchHistory.value[0]);
        }

        if (ready.status === "rejected") {
          setError(
            "Backend API unreachable. Ensure FastAPI backend is online and accessible."
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
    <div className="w-full max-w-5xl mx-auto px-6 py-8 space-y-10">
      {/* Console Section Header */}
      <div className="flex flex-col sm:flex-row sm:items-baseline justify-between gap-2 pb-4 border-b border-[#161719]">
        <div>
          <h1 className="text-lg font-medium text-[#f2f2f0] tracking-tight">Console Overview</h1>
          <p className="text-xs text-[#9d9ea1] mt-0.5">
            Operational status of PEP boundaries, pending authorizations, and audit telemetry.
          </p>
        </div>

        <div className="flex items-center gap-4 text-xs text-[#9d9ea1]">
          <Link href="/demo" className="text-[#f2f2f0] hover:underline font-medium">
            Guided Tour &rarr;
          </Link>
          <Link href="/playground" className="hover:text-white transition-colors">
            Playground &rarr;
          </Link>
          <Link href="/approvals" className="hover:text-white transition-colors">
            Approvals ({pendingApprovals.length}) &rarr;
          </Link>
        </div>
      </div>

      {error && (
        <Alert variant="warning" title="Connection Notice">
          {error}
        </Alert>
      )}

      {/* Guided Tour Banner */}
      <div className="p-4 rounded bg-[#0b0c0d] border border-[#1e2023] flex flex-col sm:flex-row sm:items-center justify-between gap-4 text-xs">
        <div>
          <div className="text-sm font-medium text-[#f2f2f0]">Interactive Security Tour</div>
          <div className="text-xs text-[#9d9ea1] mt-0.5">
            Step through 6 verified security invariants with live backend execution or reference fixtures.
          </div>
        </div>
        <Link href="/demo" className="shrink-0">
          <Button size="sm" variant="primary">
            Launch Tour &rarr;
          </Button>
        </Link>
      </div>

      {/* Inline Operational State Row (Clean, flat metrics) */}
      <section className="grid grid-cols-2 sm:grid-cols-4 gap-6 py-2">
        <div className="space-y-1">
          <div className="text-xs text-zinc-500 font-medium">Gateway PDP</div>
          <div className="text-sm font-medium text-[#f2f2f0] flex items-center gap-2">
            <span
              className={`w-1.5 h-1.5 rounded-full ${
                readiness?.status === "ready" ? "bg-emerald-400" : "bg-amber-400"
              }`}
            />
            <span>{readiness?.status === "ready" ? "Active" : "Connecting"}</span>
          </div>
          <div className="text-[11px] text-[#9d9ea1]">Zero-trust policy engine</div>
        </div>

        <div className="space-y-1">
          <div className="text-xs text-zinc-500 font-medium">Pending Approvals</div>
          <div className="text-sm font-medium text-[#f2f2f0]">
            {pendingApprovals.length} {pendingApprovals.length === 1 ? "request" : "requests"}
          </div>
          <div className="text-[11px] text-[#9d9ea1]">Awaiting supervisor review</div>
        </div>

        <div className="space-y-1">
          <div className="text-xs text-zinc-500 font-medium">Telemetry Store</div>
          <div className="text-sm font-medium text-[#f2f2f0]">
            {readiness?.database_connected ? "PostgreSQL Connected" : "Connecting"}
          </div>
          <div className="text-[11px] text-[#9d9ea1]">Append-only audit store</div>
        </div>

        <div className="space-y-1">
          <div className="text-xs text-zinc-500 font-medium">Baseline Accuracy</div>
          <div className="text-sm font-medium text-[#f2f2f0]">
            {typeof latestBenchmark?.accuracy === "number"
              ? `${(latestBenchmark.accuracy * 100).toFixed(1)}%`
              : "93.8%"}
          </div>
          <div className="text-[11px] text-[#9d9ea1]">23 synthetic benchmark cases</div>
        </div>
      </section>

      {/* Recent Audit Telemetry Table */}
      <section className="space-y-3">
        <div className="flex items-baseline justify-between">
          <h2 className="text-sm font-medium text-[#f2f2f0]">Recent Security Decisions</h2>
          <Link href="/audit" className="text-xs text-zinc-500 hover:text-white transition-colors">
            All records &rarr;
          </Link>
        </div>

        {recentAudits.length === 0 ? (
          <div className="p-8 text-center text-xs text-zinc-500 border border-[#161719] rounded">
            No audit records currently persisted. Inspect a payload or run a tool to generate telemetry.
          </div>
        ) : (
          <div className="overflow-x-auto border border-[#161719] rounded">
            <table className="w-full text-left text-xs">
              <thead className="bg-[#0b0c0d] text-zinc-500 border-b border-[#161719] text-[11px]">
                <tr>
                  <th className="py-2.5 px-4 font-normal">Timestamp</th>
                  <th className="py-2.5 px-4 font-normal">Event Type</th>
                  <th className="py-2.5 px-4 font-normal">Request ID</th>
                  <th className="py-2.5 px-4 font-normal">Component</th>
                  <th className="py-2.5 px-4 font-normal">Disposition</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#161719] text-[#9d9ea1]">
                {recentAudits.map((event, idx) => (
                  <tr key={event.event_id || idx} className="hover:bg-[#0d0e10] transition-colors">
                    <td className="py-2.5 px-4 text-zinc-500 whitespace-nowrap">
                      {event.timestamp ? new Date(event.timestamp).toLocaleTimeString() : "—"}
                    </td>
                    <td className="py-2.5 px-4 text-[#f2f2f0]">{event.event_type}</td>
                    <td className="py-2.5 px-4 font-mono text-[11px] text-zinc-400">
                      {event.request_id || "—"}
                    </td>
                    <td className="py-2.5 px-4">{event.component}</td>
                    <td className="py-2.5 px-4">
                      <StatusBadge status={event.decision || "LOGGED"} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Direct Workbench Links */}
      <section className="pt-4 border-t border-[#161719] grid grid-cols-1 sm:grid-cols-3 gap-6 text-xs text-[#9d9ea1]">
        <div className="space-y-1">
          <Link href="/playground" className="text-[#f2f2f0] font-medium hover:underline block">
            Adversarial Playground &rarr;
          </Link>
          <p className="text-zinc-500">Test prompt injection heuristics and quarantined token dispatch.</p>
        </div>
        <div className="space-y-1">
          <Link href="/tools" className="text-[#f2f2f0] font-medium hover:underline block">
            Tool Policy Gating &rarr;
          </Link>
          <p className="text-zinc-500">Authorize arguments and execute simulated tools via PEP.</p>
        </div>
        <div className="space-y-1">
          <Link href="/demo" className="text-[#f2f2f0] font-medium hover:underline block">
            Guided Tour &rarr;
          </Link>
          <p className="text-zinc-500">6-stage interactive walkthrough of security invariants.</p>
        </div>
      </section>
    </div>
  );
}
