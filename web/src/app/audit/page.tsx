"use client";

import React, { useEffect, useState, useCallback } from "react";
import { StatusBadge } from "@/components/ui/badge";
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
    <div className="w-full max-w-5xl mx-auto px-6 py-8 space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-baseline justify-between gap-4 pb-4 border-b border-[#161719]">
        <div className="space-y-1">
          <h1 className="text-lg font-medium text-[#f2f2f0] tracking-tight">Audit Explorer</h1>
          <p className="text-xs text-[#9d9ea1]">
            Search verified, append-only security telemetry records stored in PostgreSQL.
          </p>
        </div>
        <Button
          size="sm"
          variant="outline"
          onClick={loadAuditEvents}
          isLoading={isLoading}
        >
          Refresh
        </Button>
      </div>

      {/* Permission Guidance Banner */}
      {(isGuest || isPermissionError) && (
        <Alert variant="info" title="Session Role Guidance">
          Your active session role is <strong>{session?.role || "guest"}</strong>. Querying the full PostgreSQL audit telemetry ledger requires <code className="font-mono text-zinc-300">audit:read</code> (granted to Analyst, Supervisor, or Admin roles). Elevate your session via the role selector in the top-right navigation.
        </Alert>
      )}

      {error && !isPermissionError && (
        <Alert variant="error" title="Notice" onDismiss={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Filter Toolbar (Clean row without boxed container) */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-4 text-xs">
        <div className="flex flex-wrap items-center gap-3">
          <select
            value={eventTypeFilter}
            onChange={(e) => {
              setEventTypeFilter(e.target.value);
              setPage(0);
            }}
            className="bg-[#0e0f11] border border-[#1e2023] rounded px-2.5 py-1 text-xs text-[#f2f2f0] focus:outline-none focus:border-zinc-500"
          >
            <option value="">All Event Types</option>
            <option value="POLICY_DECISION">POLICY_DECISION</option>
            <option value="DETECTOR_SCAN">DETECTOR_SCAN</option>
            <option value="TOOL_INVOCATION">TOOL_INVOCATION</option>
            <option value="APPROVAL_DECISION">APPROVAL_DECISION</option>
            <option value="APPROVAL_CONSUMPTION">APPROVAL_CONSUMPTION</option>
          </select>

          <input
            type="text"
            value={requestIdFilter}
            onChange={(e) => {
              setRequestIdFilter(e.target.value);
              setPage(0);
            }}
            placeholder="Search request_id..."
            className="bg-[#0e0f11] border border-[#1e2023] rounded px-3 py-1 text-xs font-mono text-[#f2f2f0] placeholder:text-zinc-600 focus:outline-none focus:border-zinc-500"
          />

          {(eventTypeFilter || requestIdFilter) && (
            <button
              onClick={() => {
                setEventTypeFilter("");
                setRequestIdFilter("");
                setPage(0);
              }}
              className="text-xs text-zinc-400 hover:text-white"
            >
              Clear
            </button>
          )}
        </div>

        <div className="text-xs text-zinc-500 font-mono">
          {totalCount} records
        </div>
      </div>

      {/* Audit Table */}
      {(!events || events.length === 0) ? (
        <EmptyState
          title="No Audit Records Found"
          description="No audit events matched the current filter parameters."
        />
      ) : (
        <div className="border border-[#161719] rounded overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-[#0b0c0d] border-b border-[#161719] text-[11px] text-zinc-500">
                <tr>
                  <th className="py-2.5 px-4 font-normal">Timestamp</th>
                  <th className="py-2.5 px-4 font-normal">Event Type</th>
                  <th className="py-2.5 px-4 font-normal">Component</th>
                  <th className="py-2.5 px-4 font-normal">Decision</th>
                  <th className="py-2.5 px-4 font-normal">Request ID</th>
                  <th className="py-2.5 px-4 font-normal text-right">Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#161719] text-[#9d9ea1]">
                {events.map((event) => (
                  <tr key={event.event_id} className="hover:bg-[#0d0e10] transition-colors">
                    <td className="py-2.5 px-4 text-zinc-500 whitespace-nowrap">
                      {event.timestamp ? new Date(event.timestamp).toLocaleTimeString() : "—"}
                    </td>
                    <td className="py-2.5 px-4 text-[#f2f2f0]">{event.event_type}</td>
                    <td className="py-2.5 px-4">{event.component}</td>
                    <td className="py-2.5 px-4">
                      {event.decision ? (
                        <StatusBadge status={event.decision} />
                      ) : (
                        <span className="text-zinc-600 text-[10px]">—</span>
                      )}
                    </td>
                    <td className="py-2.5 px-4 font-mono text-[11px] text-zinc-400">
                      <div className="flex items-center gap-1.5">
                        <span className="truncate max-w-[120px]">{event.request_id}</span>
                        <button
                          onClick={() => handleCopy(event.request_id)}
                          className="hover:text-white transition-colors"
                        >
                          {copiedId === event.request_id ? "✓" : "copy"}
                        </button>
                      </div>
                    </td>
                    <td className="py-2.5 px-4 text-right">
                      <button
                        onClick={() => setSelectedEvent(event)}
                        className="text-xs text-zinc-400 hover:text-white underline"
                      >
                        Inspect
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          <div className="p-3 bg-[#0b0c0d] border-t border-[#161719] flex items-center justify-between text-xs text-zinc-500 font-mono">
            <span>Page {page + 1} of {totalPages}</span>
            <div className="flex items-center gap-2">
              <Button
                size="sm"
                variant="outline"
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                disabled={page === 0 || isLoading}
              >
                Previous
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                disabled={page >= totalPages - 1 || isLoading}
              >
                Next
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* JSON Inspector Dialog */}
      <Dialog
        open={selectedEvent !== null}
        onClose={() => setSelectedEvent(null)}
        title="Audit Record Detail"
        description="Sanitized metadata and cryptographic event attributes."
      >
        {selectedEvent && (
          <div className="space-y-3 text-xs">
            <div className="grid grid-cols-2 gap-2 p-3 rounded bg-[#08090a] border border-[#1e2023] font-mono text-[11px]">
              <div>
                <span className="text-zinc-500">Event ID:</span>
                <div className="text-[#f2f2f0] truncate">{selectedEvent.event_id}</div>
              </div>
              <div>
                <span className="text-zinc-500">Request ID:</span>
                <div className="text-[#f2f2f0] truncate">{selectedEvent.request_id}</div>
              </div>
              <div>
                <span className="text-zinc-500">Component:</span>
                <div className="text-[#f2f2f0]">{selectedEvent.component}</div>
              </div>
              <div>
                <span className="text-zinc-500">Policy Version:</span>
                <div className="text-[#f2f2f0]">{selectedEvent.policy_version || "1.0.0"}</div>
              </div>
            </div>

            <div className="space-y-1">
              <span className="text-xs text-zinc-500 block">Event Metadata (Sanitized)</span>
              <pre className="p-3 rounded bg-[#08090a] border border-[#1e2023] text-[#f2f2f0] font-mono text-[11px] overflow-x-auto max-h-72">
                {JSON.stringify(selectedEvent.metadata || {}, null, 2)}
              </pre>
            </div>
          </div>
        )}
      </Dialog>
    </div>
  );
}
