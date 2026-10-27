import React from "react";
import { clsx } from "clsx";

export type BadgeVariant =
  | "default"
  | "success"
  | "warning"
  | "destructive"
  | "accent"
  | "outline"
  | "secondary";

interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant;
  children: React.ReactNode;
}

const variantStyles: Record<BadgeVariant, string> = {
  default: "bg-indigo-500/10 text-indigo-400 border-indigo-500/30",
  success: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
  warning: "bg-amber-500/10 text-amber-400 border-amber-500/30",
  destructive: "bg-rose-500/10 text-rose-400 border-rose-500/30",
  accent: "bg-cyan-500/10 text-cyan-400 border-cyan-500/30",
  secondary: "bg-slate-800 text-slate-300 border-slate-700",
  outline: "bg-transparent text-slate-400 border-slate-800",
};

export function Badge({ variant = "default", className, children, ...props }: BadgeProps) {
  return (
    <span
      className={clsx(
        "inline-flex items-center px-2 py-0.5 rounded text-xs font-medium border font-mono tracking-tight",
        variantStyles[variant],
        className
      )}
      {...props}
    >
      {children}
    </span>
  );
}

export function StatusBadge({ status }: { status: string }) {
  const upper = (status || "").toUpperCase();
  let variant: BadgeVariant = "secondary";

  if (["ALLOW", "EXECUTED", "APPROVED", "OK", "READY", "PASSED"].includes(upper)) {
    variant = "success";
  } else if (["BLOCK", "DENIED", "REJECTED", "CRITICAL", "HIGH", "FAILED"].includes(upper)) {
    variant = "destructive";
  } else if (["REVIEW", "PENDING", "PENDING_APPROVAL", "MEDIUM", "WARNING"].includes(upper)) {
    variant = "warning";
  } else if (["CONSUMED", "EXPIRED", "LOW", "REDACT"].includes(upper)) {
    variant = "secondary";
  }

  return <Badge variant={variant}>{upper}</Badge>;
}
