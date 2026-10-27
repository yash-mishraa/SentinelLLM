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
  primary: "bg-[#f2f2f0] text-[#08090a] hover:bg-white font-medium",
  secondary: "bg-[#141518] text-[#f2f2f0] border border-[#1e2023] hover:bg-[#1b1c20]",
  destructive: "bg-rose-950/30 text-rose-300 border border-rose-800/40 hover:bg-rose-900/40",
  ghost: "bg-transparent text-[#9d9ea1] hover:text-[#f2f2f0] hover:bg-[#141518]",
  outline: "bg-transparent text-[#9d9ea1] border border-[#1e2023] hover:text-[#f2f2f0] hover:bg-[#141518]",
  accent: "bg-[#f2f2f0] text-[#08090a] hover:bg-white font-medium",
};

const sizeStyles: Record<ButtonSize, string> = {
  sm: "px-2.5 py-1 text-xs rounded",
  md: "px-3.5 py-1.5 text-xs rounded",
  lg: "px-4 py-2 text-sm rounded",
};

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = "primary", size = "md", isLoading = false, className, disabled, children, ...props }, ref) => {
    return (
      <button
        ref={ref}
        disabled={disabled || isLoading}
        className={clsx(
          "inline-flex items-center justify-center font-sans tracking-normal transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-zinc-500 disabled:opacity-40 disabled:pointer-events-none select-none",
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
