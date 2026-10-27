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
  default: "bg-[#141b29] text-slate-200 border-[#232f45]",
  success: "bg-emerald-950/40 text-emerald-400 border-emerald-800/50",
  warning: "bg-amber-950/40 text-amber-400 border-amber-800/50",
  destructive: "bg-rose-950/40 text-rose-400 border-rose-800/50",
  accent: "bg-[#a3e635]/10 text-[#a3e635] border-[#a3e635]/30",
  secondary: "bg-[#111824] text-slate-300 border-[#1c2536]",
  outline: "bg-transparent text-slate-400 border-[#1c2536]",
};

export function Badge({ variant = "default", className, children, ...props }: BadgeProps) {
  return (
    <span
      className={clsx(
        "inline-flex items-center px-2 py-0.5 rounded text-[11px] font-mono font-medium border leading-none transition-colors",
        variantStyles[variant],
        className
      )}
      {...props}
    >
      {children}
    </span>
  );
}

export function StatusBadge({ status, className }: { status: string; className?: string }) {
  const upper = (status || "").toUpperCase();

  let variant: BadgeVariant = "secondary";
  if (["ALLOW", "EXECUTED", "APPROVED", "OK", "READY", "PASSED"].includes(upper)) {
    variant = "success";
  } else if (["BLOCK", "DENIED", "REJECTED", "CRITICAL", "HIGH", "FAILED"].includes(upper)) {
    variant = "destructive";
  } else if (["REVIEW", "PENDING", "PENDING_APPROVAL", "MEDIUM", "WARNING"].includes(upper)) {
    variant = "warning";
  }

  return (
    <Badge variant={variant} className={className}>
      {upper}
    </Badge>
  );
}
