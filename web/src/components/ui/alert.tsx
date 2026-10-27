import React from "react";
import { AlertCircle, CheckCircle2, Info, AlertTriangle, X } from "lucide-react";
import { clsx } from "clsx";

export type AlertVariant = "info" | "success" | "warning" | "error";

interface AlertProps {
  variant?: AlertVariant;
  title?: string;
  children: React.ReactNode;
  onDismiss?: () => void;
  className?: string;
}

const variantConfig: Record<AlertVariant, { icon: typeof Info; styles: string; iconColor: string }> = {
  info: {
    icon: Info,
    styles: "bg-[#0d1424] text-slate-200 border-[#1c2940]",
    iconColor: "text-slate-300",
  },
  success: {
    icon: CheckCircle2,
    styles: "bg-emerald-950/20 text-emerald-200 border-emerald-800/40",
    iconColor: "text-emerald-400",
  },
  warning: {
    icon: AlertTriangle,
    styles: "bg-amber-950/20 text-amber-200 border-amber-800/40",
    iconColor: "text-amber-400",
  },
  error: {
    icon: AlertCircle,
    styles: "bg-rose-950/20 text-rose-200 border-rose-800/40",
    iconColor: "text-rose-400",
  },
};

export function Alert({ variant = "info", title, children, onDismiss, className }: AlertProps) {
  const config = variantConfig[variant];
  const Icon = config.icon;

  return (
    <div
      role="alert"
      className={clsx(
        "flex items-start gap-3 p-3.5 rounded-md border text-xs leading-relaxed",
        config.styles,
        className
      )}
    >
      <Icon className={clsx("w-4 h-4 mt-0.5 shrink-0", config.iconColor)} />
      <div className="flex-1 min-w-0">
        {title && <h5 className="font-semibold mb-0.5 text-slate-100">{title}</h5>}
        <div className="opacity-90">{children}</div>
      </div>
      {onDismiss && (
        <button
          onClick={onDismiss}
          className="text-slate-400 hover:text-slate-200 p-0.5 rounded transition-colors shrink-0"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      )}
    </div>
  );
}
