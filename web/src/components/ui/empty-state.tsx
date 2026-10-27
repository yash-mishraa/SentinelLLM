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
        "flex flex-col items-center justify-center p-8 text-center rounded border border-[#1e2023] bg-[#0b0c0d]",
        className
      )}
    >
      <div className="w-9 h-9 rounded border border-[#1e2023] bg-[#121316] flex items-center justify-center mb-3 text-zinc-400">
        <Icon className="w-4 h-4 text-zinc-400" />
      </div>
      <h4 className="text-xs font-medium text-[#f2f2f0] mb-1">{title}</h4>
      <p className="text-xs text-[#9d9ea1] max-w-sm mb-4 leading-relaxed">{description}</p>
      {action && <div>{action}</div>}
    </div>
  );
}
