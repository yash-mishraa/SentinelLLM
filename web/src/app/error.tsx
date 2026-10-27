"use client";

import React, { useEffect } from "react";
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
      <div className="space-y-1">
        <h2 className="text-base font-medium text-[#f2f2f0]">Application Notice</h2>
        <p className="text-xs text-[#9d9ea1] max-w-md">
          {error.message || "An unexpected client-side error occurred."}
        </p>
      </div>
      <Button size="sm" variant="outline" onClick={() => reset()}>
        Retry View
      </Button>
    </div>
  );
}
