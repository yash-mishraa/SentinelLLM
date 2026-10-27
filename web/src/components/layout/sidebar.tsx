"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  ShieldAlert,
  Terminal,
  Wrench,
  CheckSquare,
  FileText,
  BarChart3,
  PlayCircle,
  ShieldCheck,
} from "lucide-react";
import { clsx } from "clsx";

const NAV_ITEMS = [
  { href: "/", label: "Overview", icon: ShieldAlert, description: "System posture & metrics" },
  { href: "/playground", label: "Attack Playground", icon: Terminal, description: "Prompt injection scanner" },
  { href: "/tools", label: "Policy & Tools", icon: Wrench, description: "PEP action evaluation" },
  { href: "/approvals", label: "Approval Queue", icon: CheckSquare, description: "Human-in-the-loop review" },
  { href: "/audit", label: "Audit Explorer", icon: FileText, description: "Structured telemetry logs" },
  { href: "/benchmark", label: "Benchmark Explorer", icon: BarChart3, description: "PromptProbe evaluation" },
  { href: "/demo", label: "Guided Demo", icon: PlayCircle, description: "6-stage verified tour" },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-64 bg-slate-950 border-r border-slate-800/80 flex flex-col shrink-0 select-none">
      <div className="h-16 px-5 flex items-center gap-3 border-b border-slate-800/80 bg-slate-950/60">
        <div className="w-8 h-8 rounded-md bg-indigo-600/20 border border-indigo-500/40 flex items-center justify-center text-indigo-400">
          <ShieldCheck className="w-5 h-5" />
        </div>
        <div>
          <span className="font-bold text-sm text-slate-100 tracking-tight flex items-center gap-1.5">
            SentinelLLM
            <span className="text-[10px] font-mono font-medium px-1.5 py-0.2 bg-indigo-950/80 text-indigo-400 border border-indigo-800/50 rounded">
              v1.0.0-rc.1
            </span>
          </span>
          <p className="text-[11px] text-slate-400">AI Security Runtime & PEP</p>
        </div>
      </div>

      <nav className="p-3 space-y-1 flex-1 overflow-y-auto">
        <div className="px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-slate-400 font-mono">
          Security Console
        </div>
        {NAV_ITEMS.map((item) => {
          const isActive = pathname === item.href;
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={clsx(
                "flex items-start gap-3 px-3 py-2 rounded-md text-xs transition-all group",
                isActive
                  ? "bg-indigo-600/15 text-indigo-300 font-medium border border-indigo-500/30"
                  : "text-slate-400 hover:text-slate-200 hover:bg-slate-900/60 border border-transparent"
              )}
            >
              <Icon
                className={clsx(
                  "w-4 h-4 mt-0.5 shrink-0 transition-colors",
                  isActive ? "text-indigo-400" : "text-slate-400 group-hover:text-slate-300"
                )}
              />
              <div className="flex-1 min-w-0">
                <div className="truncate">{item.label}</div>
                <div className="text-[10px] text-slate-400 truncate opacity-80">{item.description}</div>
              </div>
            </Link>
          );
        })}
      </nav>

      <div className="p-3.5 border-t border-slate-800/80 bg-slate-950/40 text-[11px] text-slate-400 font-mono">
        <div className="flex items-center justify-between">
          <span>Engine:</span>
          <span className="text-emerald-400">Deterministic PDP</span>
        </div>
        <div className="flex items-center justify-between mt-1">
          <span>Gatekeeper:</span>
          <span className="text-cyan-400">Zero-Trust PEP</span>
        </div>
      </div>
    </aside>
  );
}
