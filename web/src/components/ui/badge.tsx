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
  default: "bg-[#141518] text-[#9d9ea1] border-[#1e2023]",
  success: "bg-emerald-950/30 text-emerald-400 border-emerald-800/30",
  warning: "bg-amber-950/30 text-amber-400 border-amber-800/30",
  destructive: "bg-rose-950/30 text-rose-400 border-rose-800/30",
  accent: "bg-[#161719] text-[#f2f2f0] border-[#272a2e]",
  secondary: "bg-[#101113] text-[#9d9ea1] border-[#1e2023]",
  outline: "bg-transparent text-[#9d9ea1] border-[#1e2023]",
};

export function Badge({ variant = "default", className, children, ...props }: BadgeProps) {
  return (
    <span
      className={clsx(
        "inline-flex items-center px-1.5 py-0.5 rounded text-[11px] font-sans font-medium border leading-none tracking-normal transition-colors",
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
