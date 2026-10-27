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

const variantConfig: Record<AlertVariant, { icon: typeof Info; styles: string }> = {
  info: {
    icon: Info,
    styles: "bg-cyan-950/30 text-cyan-200 border-cyan-800/60",
  },
  success: {
    icon: CheckCircle2,
    styles: "bg-emerald-950/30 text-emerald-200 border-emerald-800/60",
  },
  warning: {
    icon: AlertTriangle,
    styles: "bg-amber-950/30 text-amber-200 border-amber-800/60",
  },
  error: {
    icon: AlertCircle,
    styles: "bg-rose-950/30 text-rose-200 border-rose-800/60",
  },
};

export function Alert({ variant = "info", title, children, onDismiss, className }: AlertProps) {
  const { icon: Icon, styles } = variantConfig[variant];

  return (
    <div
      role="alert"
      className={clsx(
        "flex items-start p-3.5 rounded-md border text-xs leading-relaxed relative",
        styles,
        className
      )}
    >
      <Icon className="w-4 h-4 mr-2.5 mt-0.5 shrink-0" />
      <div className="flex-1">
        {title && <h5 className="font-semibold mb-0.5">{title}</h5>}
        <div className="opacity-95">{children}</div>
      </div>
      {onDismiss && (
        <button
          onClick={onDismiss}
          className="ml-2 text-current opacity-70 hover:opacity-100 p-0.5 rounded transition-opacity"
          aria-label="Dismiss"
        >
          <X className="w-4 h-4" />
        </button>
      )}
    </div>
  );
}
