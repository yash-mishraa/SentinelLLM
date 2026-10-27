"use client";

import React, { useEffect, useState } from "react";
import { getHealth, getSession, switchRole } from "@/lib/api-client";
import { SessionInfo, UserRole } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Dialog } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { User, Activity, AlertCircle, KeyRound, ShieldAlert } from "lucide-react";

export function Header() {
  const [session, setSession] = useState<SessionInfo>({
    role: "guest",
    principalId: "guest_visitor",
    permissions: ["inspect:run"],
  });
  const [backendOnline, setBackendOnline] = useState<boolean | null>(null);
  const [isSwitching, setIsSwitching] = useState(false);

  // Authentication Dialog state
  const [authDialogOpen, setAuthDialogOpen] = useState(false);
  const [targetRole, setTargetRole] = useState<UserRole | null>(null);
  const [inputApiKey, setInputApiKey] = useState("");
  const [authError, setAuthError] = useState<string | null>(null);

  useEffect(() => {
    async function init() {
      try {
        const s = await getSession();
        if (s && s.role) {
          setSession(s);
        }
      } catch {
        // Fallback to guest
      }

      try {
        const h = await getHealth();
        setBackendOnline(Boolean(h && h.status === "ok"));
      } catch {
        setBackendOnline(false);
      }
    }
    init();
  }, []);

  const handleRoleSelectChange = async (newRole: UserRole) => {
    if (newRole === session.role) return;

    if (newRole === "guest") {
      setIsSwitching(true);
      try {
        const updated = await switchRole("guest");
        setSession(updated);
        window.location.reload();
      } catch (e) {
        console.error("Failed to switch to guest:", e);
      } finally {
        setIsSwitching(false);
      }
      return;
    }

    // Role elevation requires entering the secret API key
    setTargetRole(newRole);
    setInputApiKey("");
    setAuthError(null);
    setAuthDialogOpen(true);
  };

  const handleAuthenticate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!targetRole) return;

    setIsSwitching(true);
    setAuthError(null);

    try {
      const updated = await switchRole(targetRole, inputApiKey.trim());
      setSession(updated);
      setAuthDialogOpen(false);
      window.location.reload();
    } catch (err: unknown) {
      const errorMsg =
        err instanceof Error ? err.message : "Authentication failed. Check API key.";
      setAuthError(errorMsg);
    } finally {
      setIsSwitching(false);
    }
  };

  return (
    <header className="h-16 px-6 border-b border-slate-800/80 bg-slate-950/80 backdrop-blur-sm flex items-center justify-between shrink-0 select-none">
      <div className="flex items-center gap-3">
        <h1 className="text-sm font-semibold text-slate-200">Security Operations Console</h1>
        <div className="flex items-center gap-1.5 ml-2">
          {backendOnline === true && (
            <Badge variant="success" className="gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              API ONLINE (FastAPI)
            </Badge>
          )}
          {backendOnline === false && (
            <Badge variant="destructive" className="gap-1.5">
              <AlertCircle className="w-3 h-3" />
              API OFFLINE
            </Badge>
          )}
          {backendOnline === null && (
            <Badge variant="outline" className="gap-1.5">
              <Activity className="w-3 h-3 animate-spin" />
              CONNECTING...
            </Badge>
          )}
        </div>
      </div>

      <div className="flex items-center gap-4">
        {/* Role & Principal Switcher (BFF Server-Session) */}
        <div className="flex items-center gap-2 bg-slate-900 border border-slate-800 px-3 py-1.5 rounded-md">
          <User className="w-3.5 h-3.5 text-indigo-400" />
          <div className="text-xs">
            <span className="text-slate-400 mr-1.5">Principal:</span>
            <span className="font-mono text-slate-200 font-medium">{session.principalId}</span>
          </div>

          <div className="h-4 w-px bg-slate-800 mx-1.5" />

          <label className="text-xs text-slate-400 sr-only" htmlFor="role-select">
            Select Active Role
          </label>
          <select
            id="role-select"
            value={session.role}
            disabled={isSwitching}
            onChange={(e) => handleRoleSelectChange(e.target.value as UserRole)}
            className="bg-slate-950 text-indigo-300 border border-slate-700/80 rounded px-2 py-0.5 text-xs font-mono focus:outline-none focus:ring-1 focus:ring-indigo-500 cursor-pointer"
          >
            <option value="guest">Guest (Read-Only Demo)</option>
            <option value="analyst">Analyst (Inspection & Safe Tools)</option>
            <option value="supervisor">Supervisor (Approval Gating)</option>
            <option value="admin">Administrator (Full & Benchmarks)</option>
          </select>
        </div>
      </div>

      {/* Role Elevation Authentication Dialog */}
      <Dialog
        open={authDialogOpen}
        onClose={() => setAuthDialogOpen(false)}
        title={`Authenticate Role: ${targetRole?.toUpperCase()}`}
        description="Elevated privileges require proving possession of the backend API key."
      >
        <form onSubmit={handleAuthenticate} className="space-y-4">
          <div className="bg-slate-950 border border-slate-800 rounded p-3 text-xs text-slate-300 space-y-1">
            <div className="flex items-center gap-1.5 text-indigo-400 font-semibold">
              <KeyRound className="w-3.5 h-3.5" />
              <span>Role-Based Credential Verification</span>
            </div>
            <p className="text-slate-400">
              In accordance with zero-trust invariants, visitors cannot assume privileged roles
              without supplying the server-configured API key for that role.
            </p>
            {process.env.NODE_ENV !== "production" && (
              <p className="text-[11px] text-slate-500 font-mono mt-1">
                Development default: sentinel-{targetRole}-key-secret
              </p>
            )}
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1" htmlFor="api-key-input">
              API Key for {targetRole}
            </label>
            <input
              id="api-key-input"
              type="password"
              value={inputApiKey}
              onChange={(e) => setInputApiKey(e.target.value)}
              placeholder={`Enter ${targetRole} API key...`}
              className="w-full bg-slate-950 border border-slate-700 rounded px-3 py-2 text-xs font-mono text-slate-200 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              required
              autoFocus
            />
          </div>

          {authError && (
            <div className="flex items-center gap-2 p-2.5 bg-rose-950/40 border border-rose-800/80 rounded text-xs text-rose-300">
              <ShieldAlert className="w-4 h-4 text-rose-400 shrink-0" />
              <span>{authError}</span>
            </div>
          )}

          <div className="flex items-center justify-end gap-2 pt-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setAuthDialogOpen(false)}
              disabled={isSwitching}
            >
              Cancel
            </Button>
            <Button type="submit" variant="primary" size="sm" disabled={isSwitching || !inputApiKey}>
              {isSwitching ? "Verifying..." : "Authenticate"}
            </Button>
          </div>
        </form>
      </Dialog>
    </header>
  );
}
