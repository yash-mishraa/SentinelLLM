"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { getHealth, getSession, switchRole } from "@/lib/api-client";
import { SessionInfo, UserRole } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Dialog } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { KeyRound, ExternalLink, Menu, X, ArrowLeft, ArrowUpRight } from "lucide-react";
import { clsx } from "clsx";

const CONSOLE_NAV_ITEMS = [
  { href: "/console", label: "Overview" },
  { href: "/playground", label: "Playground" },
  { href: "/tools", label: "Policies & Tools" },
  { href: "/approvals", label: "Approvals" },
  { href: "/audit", label: "Audit" },
  { href: "/benchmark", label: "Benchmark" },
  { href: "/demo", label: "Guided Demo" },
];

const PUBLIC_NAV_ITEMS = [
  { href: "#overview", label: "Overview" },
  { href: "#pipeline", label: "Pipeline" },
  { href: "#architecture", label: "Architecture" },
  { href: "#evaluations", label: "Evaluations" },
  { href: "#limitations", label: "Limitations" },
];

export function Header() {
  const pathname = usePathname();
  const isPublicPage = pathname === "/";

  const [session, setSession] = useState<SessionInfo>({
    role: "guest",
    principalId: "guest_visitor",
    permissions: ["inspect:run"],
  });
  const [backendOnline, setBackendOnline] = useState<boolean | null>(null);
  const [isSwitching, setIsSwitching] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

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
    <header className="sticky top-0 z-40 w-full border-b border-[#1c2536] bg-[#080a0f]/95 backdrop-blur-md">
      {/* Primary Header Row */}
      <div className="w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-14 flex items-center justify-between gap-4">
        {/* Brand & Wordmark */}
        <div className="flex items-center gap-3 shrink-0">
          <Link href="/" className="flex items-center gap-2.5 group">
            <div className="w-7 h-7 rounded border border-[#232f45] bg-[#0f141f] flex items-center justify-center transition-colors group-hover:border-[#a3e635]/50">
              <svg className="w-4 h-4 text-[#a3e635]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M12 2L3 7v6c0 5.5 3.8 10.7 9 12 5.2-1.3 9-6.5 9-12V7l-9-5z" stroke="#a3e635" strokeWidth="1.8" />
                <path d="M12 8v8M8 12h8" stroke="#a3e635" strokeWidth="1.8" strokeLinecap="round" />
              </svg>
            </div>
            <span className="font-semibold text-sm tracking-tight text-slate-100 flex items-center gap-2">
              SentinelLLM
              <span className="text-[10px] font-mono text-slate-400 font-normal border border-[#1c2536] px-1.5 py-0.2 rounded bg-[#0b0e17]">
                v1.0.0-rc.1
              </span>
            </span>
          </Link>
        </div>

        {/* Center Navigation */}
        <nav className="hidden md:flex items-center gap-1 text-xs">
          {isPublicPage ? (
            PUBLIC_NAV_ITEMS.map((item) => (
              <a
                key={item.href}
                href={item.href}
                className="px-3 py-1.5 text-slate-400 hover:text-slate-100 rounded transition-colors"
              >
                {item.label}
              </a>
            ))
          ) : (
            <div className="flex items-center gap-1 bg-[#0b0e17] border border-[#1c2536] p-0.5 rounded-md">
              <Link
                href="/"
                className="px-2.5 py-1 text-[11px] text-slate-400 hover:text-slate-200 rounded flex items-center gap-1 transition-colors"
              >
                <ArrowLeft className="w-3 h-3" />
                <span>Site</span>
              </Link>
              <div className="w-px h-3.5 bg-[#1c2536]" />
              {CONSOLE_NAV_ITEMS.map((item) => {
                const isActive = pathname === item.href;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={clsx(
                      "px-2.5 py-1 text-[11px] font-medium rounded transition-colors",
                      isActive
                        ? "bg-[#141b29] text-[#a3e635] border border-[#232f45]"
                        : "text-slate-400 hover:text-slate-200"
                    )}
                  >
                    {item.label}
                  </Link>
                );
              })}
            </div>
          )}
        </nav>

        {/* Right Actions */}
        <div className="flex items-center gap-3 shrink-0">
          {/* Backend Status indicator */}
          <div className="hidden sm:flex items-center gap-1.5 px-2 py-0.5 rounded border border-[#1c2536] bg-[#0b0e17] text-[11px] font-mono">
            <span
              className={clsx(
                "w-1.5 h-1.5 rounded-full",
                backendOnline === true ? "bg-emerald-400" : "bg-rose-500"
              )}
            />
            <span className="text-slate-400 text-[10px]">
              {backendOnline === true ? "FASTAPI:OK" : backendOnline === false ? "FASTAPI:ERR" : "CONNECTING..."}
            </span>
          </div>

          {/* Role Badge / Switcher (active inside console, or available everywhere) */}
          <div className="flex items-center gap-1.5">
            <div className="relative group">
              <button
                type="button"
                className="flex items-center gap-1.5 px-2 py-1 rounded border border-[#1c2536] bg-[#0f141f] hover:bg-[#141b29] text-[11px] font-mono text-slate-300 transition-colors"
                title="Active Session Identity - Click to Elevate Role"
              >
                <KeyRound className="w-3 h-3 text-[#a3e635]" />
                <span className="uppercase">{session.role}</span>
              </button>
              {/* Dropdown for role elevation */}
              <div className="absolute right-0 mt-1 w-48 bg-[#0f141f] border border-[#1c2536] rounded-md shadow-xl py-1 hidden group-hover:block z-50">
                <div className="px-3 py-1.5 text-[10px] text-slate-400 font-mono border-b border-[#1c2536]">
                  SESSION: {session.principalId}
                </div>
                {(["guest", "analyst", "supervisor", "admin"] as UserRole[]).map((r) => (
                  <button
                    key={r}
                    onClick={() => handleRoleSelectChange(r)}
                    disabled={isSwitching}
                    className={clsx(
                      "w-full text-left px-3 py-1.5 text-xs font-mono flex items-center justify-between hover:bg-[#141b29] transition-colors",
                      r === session.role ? "text-[#a3e635] font-semibold" : "text-slate-300"
                    )}
                  >
                    <span className="uppercase">{r}</span>
                    {r === session.role && <span className="text-[10px]">ACTIVE</span>}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* GitHub Link */}
          <a
            href="https://github.com/yash-mishraa/SentinelLLM"
            target="_blank"
            rel="noopener noreferrer"
            className="hidden sm:flex items-center gap-1 text-xs text-slate-400 hover:text-slate-100 transition-colors p-1"
            title="GitHub Repository"
          >
            <svg className="w-4 h-4 fill-current" viewBox="0 0 24 24">
              <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z" />
            </svg>
          </a>

          {/* Primary Action Button */}
          {isPublicPage ? (
            <Link href="/console">
              <Button size="sm" variant="accent" className="gap-1 text-xs">
                <span>Open Console</span>
                <ArrowUpRight className="w-3.5 h-3.5" />
              </Button>
            </Link>
          ) : (
            <a
              href="https://github.com/yash-mishraa/SentinelLLM#readme"
              target="_blank"
              rel="noopener noreferrer"
            >
              <Button size="sm" variant="outline" className="gap-1 text-xs">
                <span>Docs</span>
                <ExternalLink className="w-3 h-3 text-slate-400" />
              </Button>
            </a>
          )}

          {/* Mobile Menu Button */}
          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="md:hidden p-1.5 text-slate-400 hover:text-slate-100 rounded border border-[#1c2536]"
          >
            {mobileMenuOpen ? <X className="w-4 h-4" /> : <Menu className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {/* Mobile Drawer */}
      {mobileMenuOpen && (
        <div className="md:hidden border-t border-[#1c2536] bg-[#0b0e17] px-4 py-3 space-y-1">
          <div className="text-[10px] uppercase font-mono text-slate-400 px-2 py-1">Navigation</div>
          {isPublicPage ? (
            PUBLIC_NAV_ITEMS.map((item) => (
              <a
                key={item.href}
                href={item.href}
                onClick={() => setMobileMenuOpen(false)}
                className="block px-2 py-1.5 text-xs text-slate-300 hover:text-white rounded"
              >
                {item.label}
              </a>
            ))
          ) : (
            <>
              <Link
                href="/"
                onClick={() => setMobileMenuOpen(false)}
                className="block px-2 py-1.5 text-xs text-slate-400 hover:text-white"
              >
                ← Back to Project Overview
              </Link>
              {CONSOLE_NAV_ITEMS.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={() => setMobileMenuOpen(false)}
                  className={clsx(
                    "block px-2 py-1.5 text-xs font-mono rounded",
                    pathname === item.href ? "text-[#a3e635] bg-[#141b29]" : "text-slate-300"
                  )}
                >
                  {item.label}
                </Link>
              ))}
            </>
          )}
        </div>
      )}

      {/* Role Elevation Modal */}
      <Dialog
        open={authDialogOpen}
        onClose={() => setAuthDialogOpen(false)}
        title={`Authenticate Role: ${targetRole?.toUpperCase()}`}
        description="Provide the secret API key configured for this role on the server."
      >
        <form onSubmit={handleAuthenticate} className="space-y-4">
          <div>
            <label className="block text-xs font-mono text-slate-300 mb-1.5">
              API Key for {targetRole?.toUpperCase()}
            </label>
            <input
              type="password"
              value={inputApiKey}
              onChange={(e) => setInputApiKey(e.target.value)}
              placeholder="sentinel-..."
              className="w-full bg-[#080a0f] border border-[#1c2536] rounded px-3 py-2 text-xs font-mono text-slate-100 placeholder:text-slate-600 focus:outline-none focus:border-[#a3e635]"
              autoFocus
              required
            />
          </div>

          {authError && (
            <div className="text-xs text-rose-400 bg-rose-950/20 border border-rose-800/40 p-2.5 rounded">
              {authError}
            </div>
          )}

          <div className="flex justify-end gap-2 pt-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setAuthDialogOpen(false)}
              disabled={isSwitching}
            >
              Cancel
            </Button>
            <Button type="submit" size="sm" variant="accent" isLoading={isSwitching}>
              Verify & Elevate
            </Button>
          </div>
        </form>
      </Dialog>
    </header>
  );
}
