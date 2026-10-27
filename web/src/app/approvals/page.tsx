"use client";

import React, { useEffect, useState, useCallback } from "react";
import { StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Alert } from "@/components/ui/alert";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import {
  listApprovals,
  approveRequest,
  rejectRequest,
  createApproval,
  getSession,
} from "@/lib/api-client";
import { ApprovalRequest, SessionInfo } from "@/lib/types";

export default function ApprovalsPage() {
  const [approvals, setApprovals] = useState<ApprovalRequest[]>([]);
  const [filterStatus, setFilterStatus] = useState<string>("ALL");
  const [session, setSession] = useState<SessionInfo | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  // Modal states
  const [selectedApproval, setSelectedApproval] = useState<ApprovalRequest | null>(null);
  const [modalAction, setModalAction] = useState<"approve" | "reject" | "create" | null>(null);
  const [actionInput, setActionInput] = useState<string>("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const loadApprovals = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const statusParam = filterStatus === "ALL" ? undefined : filterStatus;
      const data = await listApprovals(statusParam);
      setApprovals(Array.isArray(data) ? data : []);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
      setApprovals([]);
    } finally {
      setIsLoading(false);
    }
  }, [filterStatus]);

  useEffect(() => {
    async function init() {
      try {
        const s = await getSession();
        setSession(s);
      } catch {
        // Fallback
      }
      loadApprovals();
    }
    init();
  }, [loadApprovals]);

  const handleCopy = (id: string) => {
    navigator.clipboard.writeText(id);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleOpenApprove = (app: ApprovalRequest) => {
    setSelectedApproval(app);
    setActionInput("Verified compliance and authorized single-use execution.");
    setModalAction("approve");
  };

  const handleOpenReject = (app: ApprovalRequest) => {
    setSelectedApproval(app);
    setActionInput("Denied: Insufficient justification.");
    setModalAction("reject");
  };

  const handleConfirmAction = async () => {
    if (!selectedApproval && modalAction !== "create") return;
    setIsSubmitting(true);
    setError(null);
    try {
      if (modalAction === "approve" && selectedApproval) {
        await approveRequest(selectedApproval.approval_id, actionInput);
      } else if (modalAction === "reject" && selectedApproval) {
        await rejectRequest(selectedApproval.approval_id, actionInput);
      } else if (modalAction === "create") {
        await createApproval({
          tool_name: "export_customer_records",
          action_name: "tools:execute:export_customer_records",
          target_resource: "customer_records",
          arguments: { format: "csv", destination: "synthetic_archive" },
          justification: actionInput || "Quarterly compliance review",
        });
      }
      setModalAction(null);
      await loadApprovals();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  const canApprove = session?.role === "supervisor" || session?.role === "admin";

  return (
    <div className="w-full max-w-5xl mx-auto px-6 py-8 space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-baseline justify-between gap-4 pb-4 border-b border-[#161719]">
        <div className="space-y-1">
          <h1 className="text-lg font-medium text-[#f2f2f0] tracking-tight">Human-in-the-Loop Approval Queue</h1>
          <p className="text-xs text-[#9d9ea1]">
            Sensitive actions held out-of-band by the Policy Enforcement Point (PEP) requiring cryptographic clearance.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={loadApprovals}
            isLoading={isLoading}
          >
            Refresh
          </Button>
          <Button
            size="sm"
            variant="secondary"
            onClick={() => {
              setActionInput("Audit extraction of customer records");
              setModalAction("create");
            }}
          >
            Request Hold
          </Button>
        </div>
      </div>

      {error && (
        <Alert variant="error" title="Notice" onDismiss={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Permission Boundary Guidance */}
      {!canApprove && (
        <Alert variant="info" title="Session Role Guidance">
          Your current session role is <strong>{session?.role || "guest"}</strong>. Approving or rejecting requests requires
          supervisor authorization (<code className="font-mono text-zinc-300">approvals:manage</code>). You can switch roles in the top-right
          navigation selector with an API key.
        </Alert>
      )}

      {/* Filter Tabs (Understated text filters) */}
      <div className="flex items-center gap-4 text-xs border-b border-[#161719] pb-3 text-zinc-500">
        {["ALL", "PENDING", "APPROVED", "CONSUMED", "REJECTED", "EXPIRED"].map((status) => (
          <button
            key={status}
            onClick={() => setFilterStatus(status)}
            className={`transition-colors ${
              filterStatus === status ? "text-[#f2f2f0] font-medium" : "hover:text-[#9d9ea1]"
            }`}
          >
            {status}
          </button>
        ))}
      </div>

      {/* Queue List (Clean list without nested bordered cards) */}
      {(!approvals || approvals.length === 0) ? (
        <EmptyState
          title="No Approval Requests"
          description={
            filterStatus === "ALL"
              ? "There are no approval requests currently registered in the database."
              : `No requests with status '${filterStatus}' were found.`
          }
        />
      ) : (
        <div className="divide-y divide-[#161719] border-y border-[#161719]">
          {approvals.map((app) => {
            const isSelf = session?.principalId === app.principal_id;
            const isPending = app.status === "PENDING";
            return (
              <div key={app.approval_id} className="py-4 space-y-2 text-xs">
                <div className="flex flex-col sm:flex-row sm:items-baseline justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-[#f2f2f0]">{app.tool_name}</span>
                    <StatusBadge status={app.status} />
                    <span className="text-zinc-500 font-mono text-[11px]">{app.action_name}</span>
                  </div>

                  {isPending && (
                    <div className="flex items-center gap-2">
                      {isSelf && canApprove && (
                        <span className="text-[11px] text-amber-400 font-mono mr-2">
                          Self-approval prohibited
                        </span>
                      )}
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleOpenReject(app)}
                        disabled={!canApprove || isSelf}
                      >
                        Reject
                      </Button>
                      <Button
                        variant="primary"
                        size="sm"
                        onClick={() => handleOpenApprove(app)}
                        disabled={!canApprove || isSelf}
                      >
                        Approve
                      </Button>
                    </div>
                  )}
                </div>

                <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-zinc-500">
                  <div>Requester: <span className="text-[#9d9ea1]">{app.principal_id}</span></div>
                  <div>Created: <span className="text-[#9d9ea1]">{app.created_at ? new Date(app.created_at).toLocaleString() : "—"}</span></div>
                  <div>Expires: <span className="text-[#9d9ea1]">{app.expires_at ? new Date(app.expires_at).toLocaleTimeString() : "—"}</span></div>
                  {app.reviewed_by && (
                    <div>Reviewed by: <span className="text-[#9d9ea1]">{app.reviewed_by}</span></div>
                  )}
                </div>

                <div className="flex items-center gap-3 text-[11px] font-mono text-zinc-500">
                  <span>ID: <code className="text-[#9d9ea1]">{app.approval_id}</code></span>
                  <button
                    onClick={() => handleCopy(app.approval_id)}
                    className="hover:text-white transition-colors"
                  >
                    {copiedId === app.approval_id ? "Copied" : "Copy"}
                  </button>
                  <span className="hidden sm:inline">Digest: <code className="text-zinc-500 truncate max-w-[140px] inline-block">{app.argument_hash}</code></span>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Decision Dialog */}
      <Dialog
        open={modalAction !== null}
        onClose={() => setModalAction(null)}
        title={
          modalAction === "approve"
            ? "Approve Action"
            : modalAction === "reject"
            ? "Reject Action"
            : "Request Hold Gate"
        }
        description={
          modalAction === "create"
            ? "Register a new pending tool execution request for supervisor clearance."
            : `Provide an audit note for this decision on ${selectedApproval?.tool_name}.`
        }
      >
        <div className="space-y-4">
          <div>
            <label className="text-xs text-[#9d9ea1] block mb-1.5">
              Audit Note / Justification
            </label>
            <textarea
              value={actionInput}
              onChange={(e) => setActionInput(e.target.value)}
              rows={3}
              className="w-full p-2.5 rounded bg-[#08090a] border border-[#1e2023] text-xs font-mono text-[#f2f2f0] focus:outline-none focus:border-zinc-500 resize-none"
              placeholder="Enter explanation for audit ledger..."
            />
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setModalAction(null)}
              disabled={isSubmitting}
            >
              Cancel
            </Button>
            <Button
              variant={modalAction === "reject" ? "destructive" : "primary"}
              size="sm"
              onClick={handleConfirmAction}
              isLoading={isSubmitting}
            >
              Confirm
            </Button>
          </div>
        </div>
      </Dialog>
    </div>
  );
}
