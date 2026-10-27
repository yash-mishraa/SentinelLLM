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
} from "lucide-react";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Badge, StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Alert } from "@/components/ui/alert";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { queryAudit } from "@/lib/api-client";
import { AuditEvent } from "@/lib/types";

const PAGE_SIZE = 15;

export default function AuditPage() {
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [totalCount, setTotalCount] = useState<number>(0);
  const [page, setPage] = useState<number>(0);

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
      setEvents(resp.events);
      setTotalCount(resp.count);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setIsLoading(false);
    }
  }, [eventTypeFilter, requestIdFilter, page]);

  useEffect(() => {
    loadAuditEvents();
  }, [loadAuditEvents]);

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(text);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const totalPages = Math.max(1, Math.ceil(totalCount / PAGE_SIZE));

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-2 border-b border-slate-800">
        <div>
          <h2 className="text-xl font-bold text-slate-100 flex items-center gap-2">
            Structured Audit & Telemetry Explorer
            <Badge variant="accent">APPEND-ONLY REPOSITORY</Badge>
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Browse verified, queryable security telemetry records with recursive credential sanitization.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={loadAuditEvents}
            isLoading={isLoading}
            className="text-xs gap-1.5"
          >
            <RotateCw className="w-3.5 h-3.5" /> Refresh
          </Button>
        </div>
      </div>

      {error && (
        <Alert variant="error" title="Audit Query Error" onDismiss={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Filter Toolbar */}
      <Card className="p-3.5 bg-slate-950/80 border-slate-800">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div>
            <label htmlFor="event-type-select" className="text-[11px] text-slate-400 font-mono mb-1 block">Filter by Event Type</label>
            <select
              id="event-type-select"
              value={eventTypeFilter}
              onChange={(e) => {
                setEventTypeFilter(e.target.value);
                setPage(0);
              }}
              className="w-full bg-slate-900 border border-slate-800 rounded px-2.5 py-1.5 text-xs font-mono text-slate-200 focus:outline-none focus:ring-1 focus:ring-indigo-500"
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
            <label htmlFor="request-id-search" className="text-[11px] text-slate-400 font-mono mb-1 block">Search by Request ID</label>
            <div className="relative">
              <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-2.5" />
              <input
                id="request-id-search"
                type="text"
                value={requestIdFilter}
                onChange={(e) => {
                  setRequestIdFilter(e.target.value);
                  setPage(0);
                }}
                placeholder="Paste request_id..."
                className="w-full bg-slate-900 border border-slate-800 rounded pl-8 pr-3 py-1.5 text-xs font-mono text-slate-200 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              />
            </div>
          </div>

          <div className="flex items-end justify-between">
            <span className="text-xs text-slate-400 font-mono">
              Found: <strong className="text-slate-200">{totalCount}</strong> records
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
                className="text-xs text-indigo-400"
              >
                Clear Filters
              </Button>
            )}
          </div>
        </div>
      </Card>

      {/* Audit Table */}
      <Card className="p-0 overflow-hidden">
        {events.length === 0 ? (
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
              <thead className="bg-slate-950 border-b border-slate-800 text-[11px] text-slate-400 uppercase tracking-wider">
                <tr>
                  <th className="py-3 px-4 font-semibold">Timestamp</th>
                  <th className="py-3 px-4 font-semibold">Event Type</th>
                  <th className="py-3 px-4 font-semibold">Component</th>
                  <th className="py-3 px-4 font-semibold">Decision</th>
                  <th className="py-3 px-4 font-semibold">Request ID</th>
                  <th className="py-3 px-4 font-semibold text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 bg-slate-900/40">
                {events.map((event) => (
                  <tr key={event.event_id} className="hover:bg-slate-800/40 transition-colors">
                    <td className="py-3 px-4 text-slate-400 whitespace-nowrap">
                      {new Date(event.timestamp).toLocaleString()}
                    </td>
                    <td className="py-3 px-4 font-semibold text-slate-200">
                      {event.event_type}
                    </td>
                    <td className="py-3 px-4 text-indigo-300">
                      {event.component}
                    </td>
                    <td className="py-3 px-4">
                      {event.decision ? (
                        <StatusBadge status={event.decision} />
                      ) : (
                        <span className="text-slate-400 text-[10px]">—</span>
                      )}
                    </td>
                    <td className="py-3 px-4 text-slate-400">
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
                    <td className="py-3 px-4 text-right">
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => setSelectedEvent(event)}
                        className="text-xs text-indigo-400 hover:text-indigo-300 gap-1"
                      >
                        <Eye className="w-3.5 h-3.5" /> Inspect
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination Controls */}
        <div className="p-3 bg-slate-950 border-t border-slate-800 flex items-center justify-between text-xs font-mono">
          <span className="text-slate-400">
            Page {page + 1} of {totalPages}
          </span>
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant="outline"
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={page === 0 || isLoading}
            >
              <ChevronLeft className="w-3.5 h-3.5 mr-1" /> Previous
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
              disabled={page >= totalPages - 1 || isLoading}
            >
              Next <ChevronRight className="w-3.5 h-3.5 ml-1" />
            </Button>
          </div>
        </div>
      </Card>

      {/* JSON Payload Inspector Dialog */}
      <Dialog
        open={selectedEvent !== null}
        onClose={() => setSelectedEvent(null)}
        title="Audit Telemetry Event Record"
        description="Sanitized metadata and cryptographic event attributes."
      >
        {selectedEvent && (
          <div className="space-y-3 text-xs font-mono">
            <div className="grid grid-cols-2 gap-2 p-3 rounded bg-slate-950 border border-slate-800">
              <div>
                <span className="text-slate-400">Event ID:</span>
                <div className="text-slate-200 truncate">{selectedEvent.event_id}</div>
              </div>
              <div>
                <span className="text-slate-400">Request ID:</span>
                <div className="text-slate-200 truncate">{selectedEvent.request_id}</div>
              </div>
              <div>
                <span className="text-slate-400">Component:</span>
                <div className="text-indigo-300">{selectedEvent.component}</div>
              </div>
              <div>
                <span className="text-slate-400">Policy Version:</span>
                <div className="text-slate-200">{selectedEvent.policy_version || "1.0.0"}</div>
              </div>
            </div>

            <div>
              <span className="text-slate-400 block mb-1 font-semibold uppercase text-[10px]">
                Event Metadata (Sanitized)
              </span>
              <pre className="p-3 rounded bg-slate-950 border border-slate-800 text-slate-300 text-[11px] overflow-x-auto max-h-72">
                {JSON.stringify(selectedEvent.metadata || {}, null, 2)}
              </pre>
            </div>
          </div>
        )}
      </Dialog>
    </div>
  );
}
