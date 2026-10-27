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
    <div className="w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[#1c2536]">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-lg font-semibold tracking-tight text-slate-100">
              Human-in-the-Loop Approval Queue
            </h1>
            <Badge variant="accent" className="text-[10px]">TWO-MAN RULE</Badge>
          </div>
          <p className="text-xs text-slate-400 mt-0.5">
            Sensitive actions held out-of-band by the Policy Enforcement Point (PEP) requiring cryptographic clearance.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={loadApprovals}
            isLoading={isLoading}
            className="text-xs font-mono gap-1.5"
          >
            <RotateCw className="w-3.5 h-3.5" /> Refresh
          </Button>
          <Button
            size="sm"
            variant="accent"
            onClick={() => {
              setActionInput("Audit extraction of customer records");
              setModalAction("create");
            }}
            className="text-xs font-mono gap-1.5"
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
          Your current session role is <strong className="font-mono text-slate-100">{session?.role || "guest"}</strong>. Approving or rejecting requests requires
          the <strong className="text-slate-100">Supervisor</strong> or <strong className="text-slate-100">Administrator</strong> role (<code className="font-mono">approvals:manage</code>). You can switch roles in the top-right
          selector with the configured secret key.
        </Alert>
      )}

      {/* Filter Tabs */}
      <div className="flex items-center gap-1.5 border-b border-[#1c2536] pb-2">
        {["ALL", "PENDING", "APPROVED", "CONSUMED", "REJECTED", "EXPIRED"].map((status) => (
          <button
            key={status}
            onClick={() => setFilterStatus(status)}
            className={`px-3 py-1 rounded text-xs font-mono transition-colors ${
              filterStatus === status
                ? "bg-[#141b29] text-[#a3e635] font-semibold border border-[#232f45]"
                : "text-slate-400 hover:text-slate-200 hover:bg-[#0f141f]"
            }`}
          >
            {status}
          </button>
        ))}
      </div>

      {/* Approval List */}
      {(!approvals || approvals.length === 0) ? (
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
          {(approvals || []).map((app) => {
            const isSelf = session?.principalId === app.principal_id;
            const isPending = app.status === "PENDING";
            let createdDate = "—";
            let expiresTime = "—";
            let reviewedTime = "—";
            try {
              if (app.created_at) createdDate = new Date(app.created_at).toLocaleString();
              if (app.expires_at) expiresTime = new Date(app.expires_at).toLocaleTimeString();
              if (app.reviewed_at) reviewedTime = new Date(app.reviewed_at).toLocaleTimeString();
            } catch {
              // Ignore invalid dates
            }

            return (
              <div key={app.approval_id} className="p-4 rounded bg-[#0f141f] border border-[#1c2536] hover:border-[#232f45] transition-colors">
                <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
                  <div className="space-y-1.5 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-mono text-xs font-semibold text-slate-100">{app.tool_name}</span>
                      <StatusBadge status={app.status} />
                      <span className="text-[11px] text-slate-500 font-mono">
                        Action: {app.action_name}
                      </span>
                    </div>

                    <div className="flex items-center gap-3 text-xs text-slate-400 font-mono flex-wrap">
                      <span className="flex items-center gap-1">
                        <User className="w-3.5 h-3.5 text-[#a3e635]" />
                        Requester: <strong className="text-slate-300">{app.principal_id}</strong>
                      </span>
                      <span>•</span>
                      <span>Created: {createdDate}</span>
                      <span>•</span>
                      <span>Expires: {expiresTime}</span>
                    </div>

                    <div className="flex items-center gap-2 pt-1 text-[11px] font-mono text-slate-500">
                      <span>ID:</span>
                      <code className="text-slate-300 bg-[#080a0f] px-1.5 py-0.5 rounded border border-[#1c2536]">
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
                      <div className="text-[11px] text-slate-400 pt-0.5 font-mono">
                        Reviewed by: <span className="text-slate-200">{app.reviewed_by}</span> on{" "}
                        {reviewedTime}
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
                        className="text-xs font-mono"
                      >
                        <XCircle className="w-3.5 h-3.5 mr-1 text-rose-400" /> Reject
                      </Button>
                      <Button
                        variant="accent"
                        size="sm"
                        onClick={() => handleOpenApprove(app)}
                        disabled={!canApprove || isSelf}
                        className="text-xs font-mono"
                      >
                        <ShieldCheck className="w-3.5 h-3.5 mr-1" /> Approve
                      </Button>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Action Dialog */}
      <Dialog
        open={modalAction !== null}
        onClose={() => setModalAction(null)}
        title={
          modalAction === "approve"
            ? "Approve Sensitive Execution"
            : modalAction === "reject"
            ? "Reject Sensitive Execution"
            : "Create Approval Request"
        }
        description={
          modalAction === "create"
            ? "Register a new pending tool execution request for supervisor clearance."
            : `Provide an audit justification for this decision on ${selectedApproval?.tool_name}.`
        }
      >
        <div className="space-y-4">
          <div>
            <label className="text-[11px] font-mono text-slate-400 block mb-1.5">
              Audit Note / Justification
            </label>
            <textarea
              value={actionInput}
              onChange={(e) => setActionInput(e.target.value)}
              rows={3}
              className="w-full p-2.5 rounded bg-[#080a0f] border border-[#1c2536] text-xs font-mono text-slate-200 focus:outline-none focus:border-[#a3e635] resize-none"
              placeholder="Enter explanation for audit ledger..."
            />
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setModalAction(null)}
              disabled={isSubmitting}
              className="font-mono text-xs"
            >
              Cancel
            </Button>
            <Button
              variant={modalAction === "reject" ? "destructive" : "accent"}
              size="sm"
              onClick={handleConfirmAction}
              isLoading={isSubmitting}
              className="font-mono text-xs"
            >
              Confirm
            </Button>
          </div>
        </div>
      </Dialog>
    </div>
  );
}
