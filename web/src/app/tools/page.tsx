"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { StatusBadge, Badge } from "@/components/ui/badge";
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
        const safe = Array.isArray(catalog) ? catalog : [];
        setTools(safe);
        if (safe.length > 0) {
          setSelectedTool(safe[0].tool_name);
          updateDefaultArgs(safe[0].tool_name);
        }
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : String(err));
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

  const handleToolSelect = (name: string) => {
    setSelectedTool(name);
    updateDefaultArgs(name);
  };

  const currentSpec = tools.find((t) => t.tool_name === selectedTool);

  const handleAuthorize = async () => {
    if (!currentSpec) return;
    setIsAuthorizing(true);
    setError(null);
    try {
      const parsedArgs = JSON.parse(argsJson);
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
      const parsedArgs = JSON.parse(argsJson);
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
    <div className="w-full max-w-5xl mx-auto px-6 py-8 space-y-8">
      {/* Header */}
      <div className="pb-4 border-b border-[#161719] space-y-1">
        <h1 className="text-lg font-medium text-[#f2f2f0] tracking-tight">Tool Policy & PEP Gating</h1>
        <p className="text-xs text-[#9d9ea1]">
          Evaluate proposed tool actions against deterministic PDP rules and execute via Policy Enforcement Point proxy.
        </p>
      </div>

      {error && (
        <Alert variant="error" title="Notice">
          {error}
        </Alert>
      )}

      {/* Tool Catalog Selection (Compact horizontal buttons, NOT repetitive cards) */}
      <div className="space-y-2">
        <div className="text-xs text-zinc-500 font-medium">Registered Tools ({tools.length})</div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {tools.map((t) => {
            const isSelected = selectedTool === t.tool_name;
            return (
              <button
                key={t.tool_name}
                onClick={() => handleToolSelect(t.tool_name)}
                className={`p-3 rounded text-left text-xs transition-colors border ${
                  isSelected
                    ? "bg-[#141518] border-zinc-600 text-[#f2f2f0]"
                    : "bg-[#0b0c0d] border-[#1e2023] text-[#9d9ea1] hover:text-[#f2f2f0]"
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="font-medium text-[#f2f2f0]">{t.tool_name}</span>
                  {t.requires_approval ? (
                    <Badge variant="warning">Hold Gate</Badge>
                  ) : t.is_sensitive ? (
                    <Badge variant="accent">Sensitive</Badge>
                  ) : (
                    <Badge variant="success">Safe Read</Badge>
                  )}
                </div>
                <p className="text-xs text-zinc-500 leading-snug line-clamp-2">{t.description}</p>
              </button>
            );
          })}
        </div>
      </div>

      {/* Two-Column Workbench */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Left: Arguments & Action Dispatch */}
        <div className="space-y-4">
          <div className="space-y-1">
            <div className="flex items-baseline justify-between text-xs text-[#9d9ea1]">
              <span>Argument Payload</span>
              <span className="font-mono text-zinc-500">{currentSpec?.action_identifier}</span>
            </div>
            <textarea
              value={argsJson}
              onChange={(e) => setArgsJson(e.target.value)}
              rows={6}
              className="w-full p-3 rounded bg-[#0b0c0d] border border-[#1e2023] text-xs font-mono text-[#f2f2f0] focus:outline-none focus:border-zinc-500 resize-y"
            />
          </div>

          <div className="space-y-1">
            <label className="text-xs text-[#9d9ea1] block">
              Approval Token ID (Optional / required for approved sensitive actions)
            </label>
            <input
              type="text"
              value={approvalId}
              onChange={(e) => setApprovalId(e.target.value)}
              placeholder="Paste approval_id from supervisor review..."
              className="w-full px-3 py-1.5 rounded bg-[#0b0c0d] border border-[#1e2023] text-xs font-mono text-[#f2f2f0] placeholder:text-zinc-600 focus:outline-none focus:border-zinc-500"
            />
          </div>

          <div className="flex items-center gap-3 pt-2">
            <Button
              variant="secondary"
              size="sm"
              onClick={handleAuthorize}
              isLoading={isAuthorizing}
            >
              1. Authorize (PDP Dry-Run)
            </Button>
            <Button
              variant="primary"
              size="sm"
              onClick={handleExecute}
              isLoading={isExecuting}
            >
              2. Execute (PEP Dispatch)
            </Button>
          </div>
        </div>

        {/* Right: Enforcement Output */}
        <div className="space-y-4">
          <div className="text-xs text-[#9d9ea1]">Enforcement Decisions & Output</div>

          {authResponse && (
            <div className="p-4 rounded bg-[#0b0c0d] border border-[#1e2023] space-y-2 text-xs">
              <div className="flex items-baseline justify-between border-b border-[#161719] pb-2">
                <span className="text-zinc-500">PDP POLICY DECISION:</span>
                <StatusBadge status={authResponse.decision} />
              </div>
              <div className="text-[#f2f2f0]">{authResponse.explanation}</div>
              {authResponse.requires_approval && (
                <div className="p-2.5 rounded bg-amber-950/20 border border-amber-800/30 text-amber-300 text-xs flex items-center justify-between">
                  <span>Action requires human supervisor authorization.</span>
                  <Link href="/approvals" className="underline font-medium">
                    Queue &rarr;
                  </Link>
                </div>
              )}
            </div>
          )}

          {execResponse ? (
            <div className="p-4 rounded bg-[#0b0c0d] border border-[#1e2023] space-y-3 text-xs">
              <div className="flex items-baseline justify-between border-b border-[#161719] pb-2">
                <span className="text-zinc-500">PEP ENFORCEMENT STATUS:</span>
                <div className="flex items-center gap-2">
                  <StatusBadge status={execResponse.status} />
                  <span className="text-zinc-500 font-mono text-[11px]">{execResponse.execution_time_ms}ms</span>
                </div>
              </div>

              {execResponse.status === "PENDING_APPROVAL" && execResponse.approval_id && (
                <div className="space-y-2 text-xs">
                  <div className="text-amber-300">Execution held at boundary. Registered approval request:</div>
                  <div className="p-2 rounded bg-[#101113] border border-[#161719] font-mono text-[11px] text-[#f2f2f0] select-all">
                    {execResponse.approval_id}
                  </div>
                  <Link href="/approvals" className="text-zinc-400 hover:text-white underline inline-block">
                    Review in Approval Queue &rarr;
                  </Link>
                </div>
              )}

              {execResponse.result !== undefined && (
                <div className="space-y-1">
                  <div className="text-zinc-500">Tool Result:</div>
                  <pre className="p-2.5 rounded bg-[#101113] border border-[#161719] font-mono text-[11px] text-[#f2f2f0] overflow-x-auto max-h-48">
                    {typeof execResponse.result === "string"
                      ? execResponse.result
                      : JSON.stringify(execResponse.result, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          ) : (
            !authResponse && (
              <div className="h-[200px] flex items-center justify-center p-6 text-center text-xs text-zinc-500 border border-dashed border-[#1e2023] rounded">
                Select a tool, adjust arguments, and click Authorize or Execute to observe PEP gating.
              </div>
            )
          )}
        </div>
      </div>
    </div>
  );
}
