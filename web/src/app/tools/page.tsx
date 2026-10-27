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
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
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
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-2 border-b border-slate-800">
        <div>
          <h2 className="text-xl font-bold text-slate-100 flex items-center gap-2">
            Tool Policy Authorization & PEP Execution
            <Badge variant="accent">ZERO-TRUST PEP</Badge>
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Evaluate proposed tool actions against deterministic PDP rules and execute via Policy Enforcement Point proxy.
          </p>
        </div>
      </div>

      {error && (
        <Alert variant="error" title="Action Failed">
          {error}
        </Alert>
      )}

      {/* Tool Catalog Selection */}
      <div className="space-y-2">
        <label className="text-xs font-semibold uppercase tracking-wider text-slate-400 font-mono">
          Registered Tool Catalog ({(tools || []).length})
        </label>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {(tools || []).map((tool) => {
            const isSelected = selectedTool === tool.tool_name;
            return (
              <button
                key={tool.tool_name}
                onClick={() => handleToolChange(tool.tool_name)}
                className={`p-3.5 rounded-lg text-left transition-all border ${
                  isSelected
                    ? "bg-indigo-600/15 border-indigo-500/50 text-indigo-200"
                    : "bg-slate-900/60 border-slate-800 text-slate-300 hover:bg-slate-800/60 hover:border-slate-700"
                }`}
              >
                <div className="flex items-center justify-between mb-1.5 font-mono text-xs">
                  <span className="font-bold text-slate-100">{tool.tool_name}</span>
                  {tool.requires_approval ? (
                    <Badge variant="warning">APPROVAL REQUIRED</Badge>
                  ) : tool.is_sensitive ? (
                    <Badge variant="accent">SENSITIVE</Badge>
                  ) : (
                    <Badge variant="success">SAFE READ</Badge>
                  )}
                </div>
                <p className="text-[11px] text-slate-400 leading-relaxed mb-2">{tool.description}</p>
                <div className="text-[10px] text-slate-400 font-mono truncate">
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
        <Card className="flex flex-col">
          <CardHeader>
            <CardTitle className="text-sm flex items-center justify-between">
              <span>Proposed Tool Arguments</span>
              <span className="text-xs font-mono text-indigo-400 font-normal">
                {currentSpec?.action_identifier || "action"}
              </span>
            </CardTitle>
            <CardDescription>
              JSON payload passed to schema validator and Policy Enforcement Point.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex-1 flex flex-col space-y-4">
            <div>
              <label htmlFor="tool-args-textarea" className="text-xs text-slate-400 font-mono mb-1.5 block">Arguments JSON</label>
              <textarea
                id="tool-args-textarea"
                value={argsJson}
                onChange={(e) => setArgsJson(e.target.value)}
                rows={6}
                className="w-full p-3 rounded-md bg-slate-950 border border-slate-800 text-xs font-mono text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500/80 resize-y"
              />
            </div>

            <div>
              <label htmlFor="approval-id-input" className="text-xs text-slate-400 font-mono mb-1.5 block">
                Approval Token ID (Optional / Required for approved sensitive execution)
              </label>
              <input
                id="approval-id-input"
                type="text"
                value={approvalId}
                onChange={(e) => setApprovalId(e.target.value)}
                placeholder="Paste approval_id from supervisor approval..."
                className="w-full px-3 py-2 rounded-md bg-slate-950 border border-slate-800 text-xs font-mono text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500/80"
              />
            </div>

            <div className="flex items-center justify-between pt-3 border-t border-slate-800 mt-auto">
              <span className="text-[11px] text-slate-400">
                Out-of-band policy verification
              </span>
              <div className="flex items-center gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={handleAuthorize}
                  isLoading={isAuthorizing}
                >
                  1. Authorize (PDP)
                </Button>
                <Button
                  variant="primary"
                  size="sm"
                  onClick={handleExecute}
                  isLoading={isExecuting}
                  className="gap-1.5"
                >
                  <Play className="w-3.5 h-3.5" /> 2. Execute (PEP)
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Right: Enforcement Results */}
        <Card className="flex flex-col">
          <CardHeader>
            <CardTitle className="text-sm">Enforcement Verdict & Output</CardTitle>
            <CardDescription>
              Out-of-band decisions rendered by PDP and Policy Enforcement Point proxy.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex-1 flex flex-col space-y-4">
            {/* Authorize Result */}
            {authResponse && (
              <div className="p-3.5 rounded-lg border border-slate-800 bg-slate-950 space-y-2 text-xs">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 font-semibold">
                    <span>PDP Decision:</span>
                    <StatusBadge status={authResponse.decision} />
                  </div>
                  <span className="text-[11px] font-mono text-slate-400">
                    Reason: {authResponse.reason_code}
                  </span>
                </div>
                <p className="text-slate-300">{authResponse.explanation}</p>
                {authResponse.requires_approval && (
                  <div className="p-2 rounded bg-amber-500/10 border border-amber-500/20 text-amber-300 text-[11px] flex items-center justify-between">
                    <span>This action requires human supervisor review before execution.</span>
                    <Link href="/approvals" className="underline font-semibold">
                      Go to Approvals &rarr;
                    </Link>
                  </div>
                )}
              </div>
            )}

            {/* Execute Result */}
            {execResponse ? (
              <div className="space-y-3">
                <div
                  className={`p-3.5 rounded-lg border flex items-center justify-between ${
                    execResponse.status === "EXECUTED"
                      ? "bg-emerald-950/20 border-emerald-500/40 text-emerald-200"
                      : execResponse.status === "PENDING_APPROVAL"
                      ? "bg-amber-950/20 border-amber-500/40 text-amber-200"
                      : "bg-rose-950/20 border-rose-500/40 text-rose-200"
                  }`}
                >
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-sm">PEP STATUS: {execResponse.status}</span>
                      <StatusBadge status={execResponse.status} />
                    </div>
                    <div className="text-xs font-mono text-slate-300 mt-0.5">
                      Reason: {execResponse.reason_code}
                    </div>
                  </div>
                  <div className="text-right text-[11px] font-mono text-slate-400">
                    {execResponse.execution_time_ms} ms
                  </div>
                </div>

                {execResponse.status === "PENDING_APPROVAL" && execResponse.approval_id && (
                  <div className="p-3 rounded bg-amber-950/30 border border-amber-800/60 text-xs space-y-2">
                    <p className="text-amber-200 font-medium">
                      Action held in pending state. Approval request registered:
                    </p>
                    <div className="p-2 rounded bg-slate-950 font-mono text-[11px] text-amber-300 select-all break-all">
                      {execResponse.approval_id}
                    </div>
                    <div className="flex items-center justify-end">
                      <Link href="/approvals">
                        <Button size="sm" variant="secondary" className="text-xs gap-1">
                          Review in Approval Queue <ArrowRight className="w-3.5 h-3.5" />
                        </Button>
                      </Link>
                    </div>
                  </div>
                )}

                {execResponse.result !== undefined && (
                  <div>
                    <label className="text-xs font-semibold uppercase tracking-wider text-slate-400 font-mono mb-1 block">
                      Synthetic Tool Output
                    </label>
                    <pre className="p-3 rounded bg-slate-950 border border-slate-800 text-[11px] font-mono text-slate-300 overflow-x-auto max-h-56">
                      {typeof execResponse.result === "string"
                        ? execResponse.result
                        : JSON.stringify(execResponse.result, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            ) : (
              !authResponse && (
                <div className="flex-1 flex flex-col items-center justify-center p-8 text-center text-slate-400">
                  <Wrench className="w-8 h-8 mb-2 text-slate-400" />
                  <p className="text-xs font-medium text-slate-300">Ready for Gating</p>
                  <p className="text-[11px] text-slate-400 mt-1 max-w-xs">
                    Choose a tool and click &quot;Authorize&quot; to inspect policy permissions, or &quot;Execute&quot; to run via PEP.
                  </p>
                </div>
              )
            )}

            {/* Note */}
            <div className="p-2.5 rounded bg-slate-950/40 border border-slate-800/60 text-[11px] text-slate-400 leading-relaxed mt-auto flex items-start gap-2">
              <Info className="w-3.5 h-3.5 mt-0.5 text-indigo-400 shrink-0" />
              <span>
                <strong>Zero-Side-Effect Guarantee:</strong> Tools in this demo environment interact strictly with isolated
                synthetic in-memory datasets. Real destructive operations are never performed.
              </span>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
