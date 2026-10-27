import React from "react";
import { LucideIcon, Inbox } from "lucide-react";
import { clsx } from "clsx";

interface EmptyStateProps {
  icon?: LucideIcon;
  title: string;
  description: string;
  action?: React.ReactNode;
  className?: string;
}

export function EmptyState({ icon: Icon = Inbox, title, description, action, className }: EmptyStateProps) {
  return (
    <div
      className={clsx(
        "flex flex-col items-center justify-center p-8 text-center rounded-md border border-[#1c2536] bg-[#0b0e17]/60",
        className
      )}
    >
      <div className="w-10 h-10 rounded border border-[#1c2536] bg-[#0f141f] flex items-center justify-center mb-3 text-slate-400">
        <Icon className="w-5 h-5 text-slate-400" />
      </div>
      <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-200 mb-1 font-mono">{title}</h4>
      <p className="text-xs text-slate-400 max-w-sm mb-4 leading-relaxed">{description}</p>
      {action && <div>{action}</div>}
    </div>
  );
}
