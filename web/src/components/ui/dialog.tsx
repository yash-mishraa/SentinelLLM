import React from "react";
import { X } from "lucide-react";
import { clsx } from "clsx";

interface DialogProps {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children: React.ReactNode;
  className?: string;
}

export function Dialog({ open, onClose, title, description, children, className }: DialogProps) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 animate-in fade-in duration-100">
      <div
        className={clsx(
          "w-full max-w-lg bg-[#0e0f11] border border-[#1e2023] rounded shadow-2xl overflow-hidden flex flex-col max-h-[90vh]",
          className
        )}
      >
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-[#1e2023] bg-[#0a0b0d]">
          <div>
            <h3 className="text-sm font-medium text-[#f2f2f0]">{title}</h3>
            {description && <p className="text-xs text-[#9d9ea1] mt-0.5">{description}</p>}
          </div>
          <button
            onClick={onClose}
            className="text-zinc-500 hover:text-zinc-300 p-1 rounded transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="p-5 overflow-y-auto">{children}</div>
      </div>
    </div>
  );
}
