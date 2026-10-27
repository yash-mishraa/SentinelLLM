"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import {
  Wrench,
  ShieldCheck,
  ShieldAlert,
  Clock,
  Play,
  CheckCircle2,
  AlertTriangle,
  ArrowRight,
  Info,
} from "lucide-react";
import { Badge, StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Alert } from "@/components/ui/alert";
import { listTools, authorizeAction, executeTool } from "@/lib/api-client";
import { ToolSpec, AuthorizeResponse, ExecuteResponse } from "@/lib/types";

export default function ToolsPage() {
  const [tools, setTools] = useState<ToolSpec[]>([]);
  const [selectedTool, setSelectedTool] = useState<string>("read_customer_record");
  const [argsJson, setArgsJson] = useState<string>('{\n  "customer_id": "cust_001"\n}');
  const [approvalId, setApprovalId] = useState<string>("");

  const [isAuthorizing, setIsAuthorizing] = useState(false);
  const [isExecuting, setIsExecuting] = useState(false);

  const [authResponse, setAuthResponse] = useState<AuthorizeResponse | null>(null);
  const [execResponse, setExecResponse] = useState<ExecuteResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadTools() {
      try {
        const catalog = await listTools();
        const safeCatalog = Array.isArray(catalog) ? catalog : [];
        setTools(safeCatalog);
        if (safeCatalog.length > 0) {
          setSelectedTool(safeCatalog[0].tool_name);
          updateDefaultArgs(safeCatalog[0].tool_name);
        }
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : String(err));
        setTools([]);
      }
    }
    loadTools();
  }, []);

  const updateDefaultArgs = (toolName: string) => {
    if (toolName === "search_documents") {
      setArgsJson('{\n  "query": "security incident policy",\n  "limit": 5\n}');
    } else if (toolName === "read_customer_record") {
      setArgsJson('{\n  "customer_id": "cust_001"\n}');
    } else if (toolName === "export_customer_records") {
      setArgsJson('{\n  "format": "csv",\n  "destination": "synthetic_archive"\n}');
    } else {
      setArgsJson("{}");
    }
    setApprovalId("");
    setAuthResponse(null);
    setExecResponse(null);
  };

  const handleToolChange = (name: string) => {
    setSelectedTool(name);
    updateDefaultArgs(name);
  };

  const currentSpec = (tools || []).find((t) => t.tool_name === selectedTool);

  const handleAuthorize = async () => {
    if (!currentSpec) return;
    setIsAuthorizing(true);
    setError(null);
    try {
      let parsedArgs = {};
      try {
        parsedArgs = JSON.parse(argsJson);
      } catch {
        throw new Error("Invalid arguments JSON syntax. Please check formatting.");
      }

      const res = await authorizeAction({
        tool_name: currentSpec.tool_name,
        action_name: currentSpec.action_identifier,
        arguments: parsedArgs,
      });
      setAuthResponse(res);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setIsAuthorizing(false);
    }
  };

  const handleExecute = async () => {
    if (!currentSpec) return;
    setIsExecuting(true);
    setError(null);
    try {
      let parsedArgs = {};
      try {
        parsedArgs = JSON.parse(argsJson);
      } catch {
        throw new Error("Invalid arguments JSON syntax. Please check formatting.");
      }

      const res = await executeTool({
        tool_name: currentSpec.tool_name,
        action_name: currentSpec.action_identifier,
        arguments: parsedArgs,
        approval_id: approvalId.trim() || undefined,
      });
      setExecResponse(res);

      if (res.approval_id) {
        setApprovalId(res.approval_id);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setIsExecuting(false);
    }
  };

  return (
    <div className="w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[#1c2536]">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-lg font-semibold tracking-tight text-slate-100">
              Tool Policy Authorization & PEP Execution
            </h1>
            <Badge variant="accent" className="text-[10px]">EGRESS ENFORCEMENT</Badge>
          </div>
          <p className="text-xs text-slate-400 mt-0.5">
            Evaluate proposed tool actions against deterministic PDP rules and execute via Policy Enforcement Point proxy.
          </p>
        </div>
      </div>

      {error && (
        <Alert variant="error" title="Action Notice">
          {error}
        </Alert>
      )}

      {/* Tool Catalog Selection */}
      <div className="space-y-2">
        <label className="text-[11px] font-mono uppercase tracking-wider text-slate-400">
          Registered Tool Catalog ({(tools || []).length})
        </label>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {(tools || []).map((tool) => {
            const isSelected = selectedTool === tool.tool_name;
            return (
              <button
                key={tool.tool_name}
                onClick={() => handleToolChange(tool.tool_name)}
                className={`p-3.5 rounded text-left transition-colors border ${
                  isSelected
                    ? "bg-[#141b29] border-[#a3e635]/50 text-slate-100"
                    : "bg-[#0f141f] border-[#1c2536] text-slate-300 hover:bg-[#141b29]/60 hover:border-[#232f45]"
                }`}
              >
                <div className="flex items-center justify-between mb-1.5 font-mono text-xs">
                  <span className="font-semibold text-slate-200">{tool.tool_name}</span>
                  {tool.requires_approval ? (
                    <Badge variant="warning">APPROVAL REQUIRED</Badge>
                  ) : tool.is_sensitive ? (
                    <Badge variant="accent">SENSITIVE</Badge>
                  ) : (
                    <Badge variant="success">SAFE READ</Badge>
                  )}
                </div>
                <p className="text-[11px] text-slate-400 leading-relaxed mb-2">{tool.description}</p>
                <div className="text-[10px] text-slate-500 font-mono truncate">
                  Action: {tool.action_identifier}
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Interactive Action Workbench */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left: Argument Configuration */}
        <div className="bg-[#0f141f] border border-[#1c2536] rounded p-5 flex flex-col space-y-4">
          <div className="flex items-center justify-between border-b border-[#1c2536] pb-3">
            <h3 className="text-xs font-semibold text-slate-200">Proposed Tool Arguments</h3>
            <span className="text-[11px] font-mono text-[#a3e635]">
              {currentSpec?.action_identifier || "action"}
            </span>
          </div>

          <div>
            <label htmlFor="tool-args-textarea" className="text-[11px] text-slate-400 font-mono mb-1.5 block">
              Arguments Payload (JSON)
            </label>
            <textarea
              id="tool-args-textarea"
              value={argsJson}
              onChange={(e) => setArgsJson(e.target.value)}
              rows={6}
              className="w-full p-3 rounded bg-[#080a0f] border border-[#1c2536] text-xs font-mono text-slate-200 focus:outline-none focus:border-[#a3e635] resize-y"
            />
          </div>

          <div>
            <label htmlFor="approval-id-input" className="text-[11px] text-slate-400 font-mono mb-1.5 block">
              Approval Token ID (Optional / Required for approved sensitive execution)
            </label>
            <input
              id="approval-id-input"
              type="text"
              value={approvalId}
              onChange={(e) => setApprovalId(e.target.value)}
              placeholder="Paste approval_id from supervisor approval queue..."
              className="w-full px-3 py-2 rounded bg-[#080a0f] border border-[#1c2536] text-xs font-mono text-slate-200 focus:outline-none focus:border-[#a3e635]"
            />
          </div>

          <div className="flex items-center justify-between pt-3 border-t border-[#1c2536] mt-auto">
            <span className="text-[11px] text-slate-500 font-mono">
              Deterministic Verification
            </span>
            <div className="flex items-center gap-2">
              <Button
                variant="secondary"
                size="sm"
                onClick={handleAuthorize}
                isLoading={isAuthorizing}
                className="font-mono text-xs"
              >
                1. Authorize (PDP)
              </Button>
              <Button
                variant="accent"
                size="sm"
                onClick={handleExecute}
                isLoading={isExecuting}
                className="gap-1.5 font-mono text-xs"
              >
                <Play className="w-3 h-3" /> 2. Execute (PEP)
              </Button>
            </div>
          </div>
        </div>

        {/* Right: Enforcement Results */}
        <div className="bg-[#0f141f] border border-[#1c2536] rounded p-5 flex flex-col space-y-4">
          <div className="border-b border-[#1c2536] pb-3">
            <h3 className="text-xs font-semibold text-slate-200">Enforcement Verdict & Output</h3>
            <p className="text-[11px] text-slate-400 mt-0.5">
              Out-of-band decisions rendered by PDP and Policy Enforcement Point proxy.
            </p>
          </div>

          {/* Authorize Result */}
          {authResponse && (
            <div className="p-3.5 rounded border border-[#1c2536] bg-[#0b0e17] space-y-2 text-xs">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 font-semibold">
                  <span className="font-mono text-slate-300">PDP Decision:</span>
                  <StatusBadge status={authResponse.decision} />
                </div>
                <span className="text-[11px] font-mono text-slate-500">
                  Reason: {authResponse.reason_code}
                </span>
              </div>
              <p className="text-slate-300 font-sans">{authResponse.explanation}</p>
              {authResponse.requires_approval && (
                <div className="p-2.5 rounded bg-amber-950/20 border border-amber-800/40 text-amber-300 text-[11px] flex items-center justify-between">
                  <span>This sensitive action requires human supervisor review prior to dispatch.</span>
                  <Link href="/approvals" className="underline font-semibold ml-2">
                    Queue &rarr;
                  </Link>
                </div>
              )}
            </div>
          )}

          {/* Execute Result */}
          {execResponse ? (
            <div className="space-y-3">
              <div
                className={`p-3.5 rounded border flex items-center justify-between ${
                  execResponse.status === "EXECUTED"
                    ? "bg-emerald-950/20 border-emerald-800/40 text-emerald-200"
                    : execResponse.status === "PENDING_APPROVAL"
                    ? "bg-amber-950/20 border-amber-800/40 text-amber-200"
                    : "bg-rose-950/20 border-rose-800/40 text-rose-200"
                }`}
              >
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-mono font-semibold text-xs">PEP STATUS: {execResponse.status}</span>
                    <StatusBadge status={execResponse.status} />
                  </div>
                  <div className="text-[11px] font-mono text-slate-300 mt-0.5">
                    Reason: {execResponse.reason_code}
                  </div>
                </div>
                <div className="text-right text-[11px] font-mono text-slate-400">
                  {execResponse.execution_time_ms} ms
                </div>
              </div>

              {execResponse.status === "PENDING_APPROVAL" && execResponse.approval_id && (
                <div className="p-3 rounded bg-amber-950/20 border border-amber-800/40 text-xs space-y-2">
                  <p className="text-amber-200 font-medium">
                    Action held at PEP boundary. Approval request registered:
                  </p>
                  <div className="p-2 rounded bg-[#080a0f] font-mono text-[11px] text-amber-300 select-all break-all border border-[#1c2536]">
                    {execResponse.approval_id}
                  </div>
                  <div className="flex items-center justify-end">
                    <Link href="/approvals">
                      <Button size="sm" variant="secondary" className="text-xs font-mono gap-1">
                        Review in Approval Queue <ArrowRight className="w-3.5 h-3.5" />
                      </Button>
                    </Link>
                  </div>
                </div>
              )}

              {execResponse.result !== undefined && (
                <div>
                  <label className="text-[10px] font-mono uppercase tracking-wider text-slate-400 mb-1 block">
                    Synthetic Tool Output
                  </label>
                  <pre className="p-3 rounded bg-[#080a0f] border border-[#1c2536] text-[11px] font-mono text-slate-300 overflow-x-auto max-h-56">
                    {typeof execResponse.result === "string"
                      ? execResponse.result
                      : JSON.stringify(execResponse.result, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          ) : (
            !authResponse && (
              <div className="flex-1 flex flex-col items-center justify-center p-8 text-center text-slate-500 font-mono">
                <Wrench className="w-8 h-8 mb-2 text-slate-600" />
                <p className="text-xs text-slate-300">Ready for Gating</p>
                <p className="text-[11px] text-slate-500 mt-1 max-w-xs">
                  Choose a tool and click &quot;Authorize&quot; to inspect policy permissions, or &quot;Execute&quot; to run via PEP.
                </p>
              </div>
            )
          )}
        </div>
      </div>
    </div>
  );
}
