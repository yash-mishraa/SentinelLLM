"use client";

import React, { useEffect } from "react";
import { AlertCircle, RotateCw } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function ErrorBoundary({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Client boundary caught error:", error);
  }, [error]);

  return (
    <div className="flex flex-col items-center justify-center min-h-[50vh] p-6 text-center space-y-4">
      <div className="w-10 h-10 rounded border border-rose-800/40 bg-rose-950/20 flex items-center justify-center text-rose-400">
        <AlertCircle className="w-5 h-5" />
      </div>
      <div className="space-y-1">
        <h2 className="text-base font-semibold text-slate-100 font-mono">Operation Error</h2>
        <p className="text-xs text-slate-400 max-w-md font-mono">
          {error.message || "An unexpected client-side rendering error occurred."}
        </p>
      </div>
      <Button size="sm" variant="outline" onClick={() => reset()} className="gap-1.5 text-xs font-mono">
        <RotateCw className="w-3.5 h-3.5" />
        Retry View
      </Button>
    </div>
  );
}
