"use client";

import React, { useEffect, useState, useCallback } from "react";
import {
  CheckSquare,
  Clock,
  ShieldCheck,
  XCircle,
  AlertTriangle,
  RotateCw,
  Plus,
  User,
  Copy,
  Check,
} from "lucide-react";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Badge, StatusBadge } from "@/components/ui/badge";
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
import { ApprovalRequest, ApprovalStatus, SessionInfo } from "@/lib/types";

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
      setApprovals(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
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
    setActionInput("Denied: Insufficient audit justification.");
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
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-2 border-b border-slate-800">
        <div>
          <h2 className="text-xl font-bold text-slate-100 flex items-center gap-2">
            Human-in-the-Loop Approval Queue
            <Badge variant="accent">TWO-MAN RULE</Badge>
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Sensitive actions held out-of-band by the Policy Enforcement Point (PEP) requiring cryptographic clearance.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={loadApprovals}
            isLoading={isLoading}
            className="text-xs gap-1.5"
          >
            <RotateCw className="w-3.5 h-3.5" /> Refresh
          </Button>
          <Button
            size="sm"
            variant="primary"
            onClick={() => {
              setActionInput("Audit extraction of records");
              setModalAction("create");
            }}
            className="text-xs gap-1.5"
          >
            <Plus className="w-3.5 h-3.5" /> Request Approval
          </Button>
        </div>
      </div>

      {error && (
        <Alert variant="error" title="Approval Operation Error" onDismiss={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Role Notice */}
      {!canApprove && (
        <Alert variant="warning" title="Privilege Boundary Notice">
          Your current session role is <strong>{session?.role || "analyst"}</strong>. Approving or rejecting requests requires
          the <strong>Supervisor</strong> or <strong>Administrator</strong> role. You can switch roles in the top-right
          selector to simulate authorized supervisor clearance.
        </Alert>
      )}

      {/* Filter Tabs */}
      <div className="flex items-center gap-1.5 border-b border-slate-800 pb-2">
        {["ALL", "PENDING", "APPROVED", "CONSUMED", "REJECTED", "EXPIRED"].map((status) => (
          <button
            key={status}
            onClick={() => setFilterStatus(status)}
            className={`px-3 py-1 rounded text-xs font-mono transition-colors ${
              filterStatus === status
                ? "bg-indigo-600/20 text-indigo-300 font-semibold border border-indigo-500/40"
                : "text-slate-400 hover:text-slate-200 hover:bg-slate-900"
            }`}
          >
            {status}
          </button>
        ))}
      </div>

      {/* Approval List Cards */}
      {approvals.length === 0 ? (
        <EmptyState
          icon={CheckSquare}
          title="No Approval Requests Found"
          description={
            filterStatus === "ALL"
              ? "There are no approval requests currently registered in the database. Use 'Request Approval' above or trigger an action in the Tools page."
              : `No requests with status '${filterStatus}' were found.`
          }
        />
      ) : (
        <div className="space-y-3">
          {approvals.map((app) => {
            const isSelf = session?.principalId === app.principal_id;
            const isPending = app.status === "PENDING";

            return (
              <Card key={app.approval_id} className="p-4 hover:border-slate-700/80 transition-all">
                <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
                  <div className="space-y-1.5 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-mono text-sm font-bold text-slate-100">{app.tool_name}</span>
                      <StatusBadge status={app.status} />
                      <span className="text-[11px] text-slate-400 font-mono">
                        Action: {app.action_name}
                      </span>
                    </div>

                    <div className="flex items-center gap-3 text-xs text-slate-400 font-mono flex-wrap">
                      <span className="flex items-center gap-1">
                        <User className="w-3.5 h-3.5 text-indigo-400" />
                        Requester: <strong className="text-slate-300">{app.principal_id}</strong>
                      </span>
                      <span>•</span>
                      <span>Created: {new Date(app.created_at).toLocaleString()}</span>
                      <span>•</span>
                      <span>Expires: {new Date(app.expires_at).toLocaleTimeString()}</span>
                    </div>

                    <div className="flex items-center gap-2 pt-1 text-[11px] font-mono text-slate-400">
                      <span>ID:</span>
                      <code className="text-slate-300 bg-slate-950 px-1.5 py-0.5 rounded border border-slate-800">
                        {app.approval_id}
                      </code>
                      <button
                        onClick={() => handleCopy(app.approval_id)}
                        className="text-slate-400 hover:text-slate-200"
                        title="Copy Approval ID"
                      >
                        {copiedId === app.approval_id ? (
                          <Check className="w-3.5 h-3.5 text-emerald-400" />
                        ) : (
                          <Copy className="w-3.5 h-3.5" />
                        )}
                      </button>
                      <span className="ml-2">SHA-256 Digest:</span>
                      <code className="text-slate-400 truncate max-w-[140px]">{app.argument_hash}</code>
                    </div>

                    {app.reviewed_by && (
                      <div className="text-[11px] text-slate-400 pt-0.5">
                        Reviewed by: <span className="font-mono text-indigo-300">{app.reviewed_by}</span> on{" "}
                        {app.reviewed_at ? new Date(app.reviewed_at).toLocaleTimeString() : "—"}
                        {app.rejection_reason && (
                          <span className="text-rose-400 ml-2">({app.rejection_reason})</span>
                        )}
                      </div>
                    )}
                  </div>

                  {/* Actions */}
                  {isPending && (
                    <div className="flex items-center gap-2 shrink-0 self-start lg:self-center">
                      {isSelf && canApprove && (
                        <span className="text-[10px] text-amber-400 font-mono mr-2 max-w-[140px] text-right">
                          Self-approval prohibited
                        </span>
                      )}
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => handleOpenReject(app)}
                        disabled={!canApprove || isSelf}
                        className="text-xs"
                      >
                        <XCircle className="w-3.5 h-3.5 mr-1 text-rose-400" /> Reject
                      </Button>
                      <Button
                        variant="primary"
                        size="sm"
                        onClick={() => handleOpenApprove(app)}
                        disabled={!canApprove || isSelf}
                        className="text-xs"
                      >
                        <ShieldCheck className="w-3.5 h-3.5 mr-1" /> Approve
                      </Button>
                    </div>
                  )}
                </div>
              </Card>
            );
          })}
        </div>
      )}

      {/* Confirmation & Creation Dialog */}
      <Dialog
        open={modalAction !== null}
        onClose={() => setModalAction(null)}
        title={
          modalAction === "approve"
            ? "Supervisor Approval Confirmation"
            : modalAction === "reject"
            ? "Reject Action Request"
            : "Request Sensitive Action Approval"
        }
        description={
          modalAction === "approve"
            ? "Approving this action issues a single-use execution token cryptographically bound to the argument digest."
            : modalAction === "reject"
            ? "Rejecting this request terminates the pending execution and records the denial in the audit log."
            : "Submit a high-impact action request to the supervisor approval review queue."
        }
      >
        <div className="space-y-4 text-xs">
          {selectedApproval && modalAction !== "create" && (
            <div className="p-3 rounded bg-slate-950 border border-slate-800 font-mono space-y-1">
              <div>Tool: {selectedApproval.tool_name}</div>
              <div>Requester: {selectedApproval.principal_id}</div>
              <div>ID: {selectedApproval.approval_id}</div>
            </div>
          )}

          <div>
            <label className="text-xs font-semibold text-slate-300 block mb-1.5">
              {modalAction === "approve"
                ? "Approval Notes"
                : modalAction === "reject"
                ? "Rejection Reason"
                : "Business Justification"}
            </label>
            <textarea
              value={actionInput}
              onChange={(e) => setActionInput(e.target.value)}
              rows={3}
              className="w-full p-2.5 rounded bg-slate-950 border border-slate-800 text-slate-200 text-xs font-mono focus:outline-none focus:ring-2 focus:ring-indigo-500/80 resize-none"
            />
          </div>

          <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-800">
            <Button variant="ghost" size="sm" onClick={() => setModalAction(null)} disabled={isSubmitting}>
              Cancel
            </Button>
            <Button
              variant={modalAction === "reject" ? "destructive" : "primary"}
              size="sm"
              onClick={handleConfirmAction}
              isLoading={isSubmitting}
            >
              {modalAction === "approve" ? "Confirm Approval" : modalAction === "reject" ? "Confirm Rejection" : "Submit Request"}
            </Button>
          </div>
        </div>
      </Dialog>
    </div>
  );
}
