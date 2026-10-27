"use client";

import React, { useEffect, useState, useCallback } from "react";
import {
  FileText,
  Search,
  Filter,
  ChevronLeft,
  ChevronRight,
  RotateCw,
  Copy,
  Check,
  Eye,
  ShieldCheck,
  Info,
} from "lucide-react";
import { Badge, StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Alert } from "@/components/ui/alert";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { queryAudit, getSession } from "@/lib/api-client";
import { AuditEvent, SessionInfo } from "@/lib/types";

const PAGE_SIZE = 15;

export default function AuditPage() {
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [totalCount, setTotalCount] = useState<number>(0);
  const [page, setPage] = useState<number>(0);
  const [session, setSession] = useState<SessionInfo | null>(null);

  const [eventTypeFilter, setEventTypeFilter] = useState<string>("");
  const [requestIdFilter, setRequestIdFilter] = useState<string>("");
  const [selectedEvent, setSelectedEvent] = useState<AuditEvent | null>(null);

  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const loadAuditEvents = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const resp = await queryAudit({
        event_type: eventTypeFilter.trim() || undefined,
        request_id: requestIdFilter.trim() || undefined,
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
      });
      setEvents(Array.isArray(resp?.events) ? resp.events : []);
      setTotalCount(typeof resp?.count === "number" ? resp.count : 0);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg);
      setEvents([]);
      setTotalCount(0);
    } finally {
      setIsLoading(false);
    }
  }, [eventTypeFilter, requestIdFilter, page]);

  useEffect(() => {
    async function init() {
      try {
        const s = await getSession();
        setSession(s);
      } catch {
        // Fallback
      }
      loadAuditEvents();
    }
    init();
  }, [loadAuditEvents]);

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(text);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const totalPages = Math.max(1, Math.ceil(totalCount / PAGE_SIZE));
  const isGuest = session?.role === "guest";
  const isPermissionError = error && (
    error.toLowerCase().includes("permission") ||
    error.toLowerCase().includes("forbidden") ||
    error.toLowerCase().includes("403") ||
    error.toLowerCase().includes("audit:read")
  );

  return (
    <div className="w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[#1c2536]">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-lg font-semibold tracking-tight text-slate-100">
              Structured Audit & Telemetry Explorer
            </h1>
            <Badge variant="accent" className="text-[10px]">APPEND-ONLY LEDGER</Badge>
          </div>
          <p className="text-xs text-slate-400 mt-0.5">
            Browse verified, queryable security telemetry records with recursive credential sanitization.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={loadAuditEvents}
            isLoading={isLoading}
            className="text-xs font-mono gap-1.5"
          >
            <RotateCw className="w-3.5 h-3.5" /> Refresh
          </Button>
        </div>
      </div>

      {/* Permission Guidance Banner */}
      {(isGuest || isPermissionError) && (
        <Alert variant="info" title="Session Permission Guidance">
          Your active session role is <strong className="font-mono text-slate-100">{session?.role || "guest"}</strong>. The guest role has read-only access to basic inspection. Querying the full PostgreSQL audit telemetry ledger requires <code className="font-mono text-slate-100">audit:read</code> (granted to Analyst, Supervisor, or Admin roles). Click the role badge in the top right to elevate with your configured API key.
        </Alert>
      )}

      {error && !isPermissionError && (
        <Alert variant="error" title="Audit Query Notice" onDismiss={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Filter Toolbar */}
      <div className="p-3.5 bg-[#0f141f] border border-[#1c2536] rounded">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div>
            <label htmlFor="event-type-select" className="text-[11px] text-slate-400 font-mono mb-1 block">
              Filter by Event Type
            </label>
            <select
              id="event-type-select"
              value={eventTypeFilter}
              onChange={(e) => {
                setEventTypeFilter(e.target.value);
                setPage(0);
              }}
              className="w-full bg-[#080a0f] border border-[#1c2536] rounded px-2.5 py-1.5 text-xs font-mono text-slate-200 focus:outline-none focus:border-[#a3e635]"
            >
              <option value="">All Event Types</option>
              <option value="POLICY_DECISION">POLICY_DECISION</option>
              <option value="DETECTOR_SCAN">DETECTOR_SCAN</option>
              <option value="TOOL_INVOCATION">TOOL_INVOCATION</option>
              <option value="APPROVAL_DECISION">APPROVAL_DECISION</option>
              <option value="APPROVAL_CONSUMPTION">APPROVAL_CONSUMPTION</option>
            </select>
          </div>

          <div>
            <label htmlFor="request-id-search" className="text-[11px] text-slate-400 font-mono mb-1 block">
              Search by Request ID
            </label>
            <div className="relative">
              <Search className="w-3.5 h-3.5 text-slate-500 absolute left-2.5 top-2.5" />
              <input
                id="request-id-search"
                type="text"
                value={requestIdFilter}
                onChange={(e) => {
                  setRequestIdFilter(e.target.value);
                  setPage(0);
                }}
                placeholder="Paste request_id..."
                className="w-full bg-[#080a0f] border border-[#1c2536] rounded pl-8 pr-3 py-1.5 text-xs font-mono text-slate-200 focus:outline-none focus:border-[#a3e635]"
              />
            </div>
          </div>

          <div className="flex items-end justify-between">
            <span className="text-xs text-slate-400 font-mono">
              Records: <strong className="text-slate-200">{totalCount}</strong>
            </span>
            {(eventTypeFilter || requestIdFilter) && (
              <Button
                size="sm"
                variant="ghost"
                onClick={() => {
                  setEventTypeFilter("");
                  setRequestIdFilter("");
                  setPage(0);
                }}
                className="text-xs text-[#a3e635] font-mono"
              >
                Clear Filters
              </Button>
            )}
          </div>
        </div>
      </div>

      {/* Audit Table */}
      <div className="bg-[#0f141f] border border-[#1c2536] rounded overflow-hidden">
        {(!events || events.length === 0) ? (
          <div className="p-8">
            <EmptyState
              icon={FileText}
              title="No Audit Records Found"
              description="No audit events matched the current filter parameters. Telemetry is appended whenever actions, inspections, or approvals occur."
            />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead className="bg-[#080a0f] border-b border-[#1c2536] text-[10px] text-slate-500 uppercase tracking-wider">
                <tr>
                  <th className="py-2.5 px-4 font-semibold">Timestamp</th>
                  <th className="py-2.5 px-4 font-semibold">Event Type</th>
                  <th className="py-2.5 px-4 font-semibold">Component</th>
                  <th className="py-2.5 px-4 font-semibold">Decision</th>
                  <th className="py-2.5 px-4 font-semibold">Request ID</th>
                  <th className="py-2.5 px-4 font-semibold text-right">Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#1c2536] text-slate-300">
                {(events || []).map((event) => {
                  let formattedDate = "—";
                  try {
                    if (event.timestamp) formattedDate = new Date(event.timestamp).toLocaleString();
                  } catch {
                    // Ignore date format error
                  }
                  return (
                    <tr key={event.event_id} className="hover:bg-[#141b29] transition-colors">
                      <td className="py-2.5 px-4 text-slate-400 whitespace-nowrap">
                        {formattedDate}
                      </td>
                      <td className="py-2.5 px-4 font-semibold text-slate-200">
                        {event.event_type}
                      </td>
                      <td className="py-2.5 px-4 text-slate-300">
                        {event.component}
                      </td>
                      <td className="py-2.5 px-4">
                        {event.decision ? (
                          <StatusBadge status={event.decision} />
                        ) : (
                          <span className="text-slate-500 text-[10px]">—</span>
                        )}
                      </td>
                      <td className="py-2.5 px-4 text-slate-400">
                        <div className="flex items-center gap-1.5">
                          <span className="truncate max-w-[120px]">{event.request_id}</span>
                          <button
                            onClick={() => handleCopy(event.request_id)}
                            className="text-slate-400 hover:text-slate-200"
                            title="Copy Request ID"
                          >
                            {copiedId === event.request_id ? (
                              <Check className="w-3 h-3 text-emerald-400" />
                            ) : (
                              <Copy className="w-3 h-3" />
                            )}
                          </button>
                        </div>
                      </td>
                      <td className="py-2.5 px-4 text-right">
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => setSelectedEvent(event)}
                          className="text-xs text-[#a3e635] hover:text-[#bef264] gap-1 font-mono"
                        >
                          <Eye className="w-3 h-3" /> Inspect
                        </Button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination Controls */}
        <div className="p-3 bg-[#080a0f] border-t border-[#1c2536] flex items-center justify-between text-xs font-mono">
          <span className="text-slate-400">
            Page {page + 1} of {totalPages}
          </span>
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant="outline"
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={page === 0 || isLoading}
              className="text-xs font-mono"
            >
              <ChevronLeft className="w-3.5 h-3.5 mr-1" /> Previous
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
              disabled={page >= totalPages - 1 || isLoading}
              className="text-xs font-mono"
            >
              Next <ChevronRight className="w-3.5 h-3.5 ml-1" />
            </Button>
          </div>
        </div>
      </div>

      {/* JSON Payload Inspector Dialog */}
      <Dialog
        open={selectedEvent !== null}
        onClose={() => setSelectedEvent(null)}
        title="Audit Telemetry Event Record"
        description="Sanitized metadata and cryptographic event attributes."
      >
        {selectedEvent && (
          <div className="space-y-3 text-xs font-mono">
            <div className="grid grid-cols-2 gap-2 p-3 rounded bg-[#080a0f] border border-[#1c2536]">
              <div>
                <span className="text-slate-500">Event ID:</span>
                <div className="text-slate-200 truncate">{selectedEvent.event_id}</div>
              </div>
              <div>
                <span className="text-slate-500">Request ID:</span>
                <div className="text-slate-200 truncate">{selectedEvent.request_id}</div>
              </div>
              <div>
                <span className="text-slate-500">Component:</span>
                <div className="text-slate-200">{selectedEvent.component}</div>
              </div>
              <div>
                <span className="text-slate-500">Policy Version:</span>
                <div className="text-slate-200">{selectedEvent.policy_version || "1.0.0"}</div>
              </div>
            </div>

            <div>
              <span className="text-slate-400 block mb-1 font-semibold uppercase text-[10px]">
                Event Metadata (Sanitized)
              </span>
              <pre className="p-3 rounded bg-[#080a0f] border border-[#1c2536] text-slate-300 text-[11px] overflow-x-auto max-h-72">
                {JSON.stringify(selectedEvent.metadata || {}, null, 2)}
              </pre>
            </div>
          </div>
        )}
      </Dialog>
    </div>
  );
}
