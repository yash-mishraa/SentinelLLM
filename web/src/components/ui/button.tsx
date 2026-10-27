import React from "react";
import { clsx } from "clsx";
import { Loader2 } from "lucide-react";

export type ButtonVariant = "primary" | "secondary" | "destructive" | "ghost" | "outline" | "accent";
export type ButtonSize = "sm" | "md" | "lg";

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  isLoading?: boolean;
}

const variantStyles: Record<ButtonVariant, string> = {
  primary: "bg-slate-100 text-slate-950 hover:bg-white border border-slate-200 font-medium",
  secondary: "bg-[#141b29] text-slate-200 border border-[#1c2536] hover:bg-[#1a2336] hover:text-white",
  destructive: "bg-rose-950/40 text-rose-300 border border-rose-800/60 hover:bg-rose-900/50",
  ghost: "bg-transparent hover:bg-[#141b29] text-slate-300 hover:text-white",
  outline: "bg-transparent hover:bg-[#141b29] text-slate-300 border border-[#1c2536]",
  accent: "bg-[#a3e635] text-slate-950 font-medium hover:bg-[#bef264] border border-[#a3e635]",
};

const sizeStyles: Record<ButtonSize, string> = {
  sm: "px-2.5 py-1 text-xs rounded",
  md: "px-3.5 py-1.5 text-xs rounded-md",
  lg: "px-4.5 py-2 text-sm rounded-md",
};

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = "primary", size = "md", isLoading = false, className, disabled, children, ...props }, ref) => {
    return (
      <button
        ref={ref}
        disabled={disabled || isLoading}
        className={clsx(
          "inline-flex items-center justify-center font-sans tracking-tight transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[#a3e635] disabled:opacity-50 disabled:pointer-events-none select-none",
          variantStyles[variant],
          sizeStyles[size],
          className
        )}
        {...props}
      >
        {isLoading && <Loader2 className="w-3.5 h-3.5 mr-2 animate-spin shrink-0" />}
        {children}
      </button>
    );
  }
);
Button.displayName = "Button";
