"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { getSession, switchRole } from "@/lib/api-client";
import { SessionInfo, UserRole } from "@/lib/types";
import { Dialog } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Menu, X } from "lucide-react";
import { clsx } from "clsx";

const PUBLIC_NAV = [
  { href: "/demo", label: "Interactive Demo" },
  { href: "/architecture", label: "Architecture" },
  { href: "/evaluations", label: "Evaluations" },
  { href: "https://github.com/yash-mishraa/SentinelLLM#readme", label: "Documentation", external: true },
];

const CONSOLE_NAV = [
  { href: "/console", label: "Overview" },
  { href: "/demo", label: "Guided Tour" },
  { href: "/playground", label: "Playground" },
  { href: "/tools", label: "Policies" },
  { href: "/approvals", label: "Approvals" },
  { href: "/audit", label: "Audit" },
  { href: "/benchmark", label: "Benchmark" },
];

export function Header() {
  const pathname = usePathname();
  const isConsoleRoute =
    pathname.startsWith("/console") ||
    pathname.startsWith("/playground") ||
    pathname.startsWith("/tools") ||
    pathname.startsWith("/approvals") ||
    pathname.startsWith("/audit") ||
    pathname.startsWith("/benchmark") ||
    pathname.startsWith("/demo");

  const [session, setSession] = useState<SessionInfo>({
    role: "guest",
    principalId: "guest_visitor",
    permissions: ["inspect:run"],
  });
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
        // Fallback to default
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
    <header className="w-full bg-[#08090a] select-none">
      <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between gap-6">
        {/* Brand Wordmark */}
        <div className="flex items-center gap-6 shrink-0">
          <Link href="/" className="text-sm font-medium tracking-tight text-[#f2f2f0] hover:text-white transition-colors">
            SentinelLLM
          </Link>

          {/* Primary Nav Links */}
          <nav className="hidden md:flex items-center gap-5 text-xs text-[#9d9ea1]">
            {!isConsoleRoute ? (
              PUBLIC_NAV.map((item) =>
                item.external ? (
                  <a
                    key={item.href}
                    href={item.href}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="hover:text-[#f2f2f0] transition-colors"
                  >
                    {item.label}
                  </a>
                ) : (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={clsx(
                      "transition-colors",
                      pathname === item.href ? "text-[#f2f2f0] font-medium" : "hover:text-[#f2f2f0]"
                    )}
                  >
                    {item.label}
                  </Link>
                )
              )
            ) : (
              <div className="flex items-center gap-4 text-xs">
                <span className="text-zinc-600">/</span>
                {CONSOLE_NAV.map((item) => {
                  const isActive = pathname === item.href;
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      className={clsx(
                        "transition-colors",
                        isActive ? "text-[#f2f2f0] font-medium" : "text-[#9d9ea1] hover:text-[#f2f2f0]"
                      )}
                    >
                      {item.label}
                    </Link>
                  );
                })}
              </div>
            )}
          </nav>
        </div>

        {/* Right Actions */}
        <div className="flex items-center gap-5 text-xs">
          <a
            href="https://github.com/yash-mishraa/SentinelLLM"
            target="_blank"
            rel="noopener noreferrer"
            className="text-[#9d9ea1] hover:text-[#f2f2f0] transition-colors hidden sm:inline"
          >
            GitHub
          </a>

          {isConsoleRoute ? (
            <div className="flex items-center gap-3">
              {/* Role Indicator / Selector */}
              <div className="relative group">
                <button
                  type="button"
                  className="text-xs text-[#9d9ea1] hover:text-[#f2f2f0] transition-colors flex items-center gap-1.5"
                  title="Session Role — Click to Elevate"
                >
                  <span className="w-1.5 h-1.5 rounded-full bg-zinc-500" />
                  <span className="capitalize">{session.role}</span>
                </button>
                <div className="absolute right-0 mt-2 w-40 bg-[#0e0f11] border border-[#1e2023] rounded py-1 hidden group-hover:block z-50">
                  <div className="px-3 py-1 text-[10px] text-zinc-500 border-b border-[#1e2023]">
                    {session.principalId}
                  </div>
                  {(["guest", "analyst", "supervisor", "admin"] as UserRole[]).map((r) => (
                    <button
                      key={r}
                      onClick={() => handleRoleSelectChange(r)}
                      disabled={isSwitching}
                      className={clsx(
                        "w-full text-left px-3 py-1.5 text-xs flex items-center justify-between hover:bg-[#141518] transition-colors",
                        r === session.role ? "text-[#f2f2f0] font-medium" : "text-[#9d9ea1]"
                      )}
                    >
                      <span className="capitalize">{r}</span>
                      {r === session.role && <span className="text-[10px] text-zinc-500">Active</span>}
                    </button>
                  ))}
                </div>
              </div>

              <Link
                href="/"
                className="text-xs text-zinc-500 hover:text-[#f2f2f0] transition-colors"
              >
                Exit
              </Link>
            </div>
          ) : (
            <Link
              href="/console"
              className="text-xs text-[#f2f2f0] hover:text-white transition-colors"
            >
              Open Console &rarr;
            </Link>
          )}

          {/* Mobile menu toggle */}
          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="md:hidden text-[#9d9ea1] hover:text-white p-1"
          >
            {mobileMenuOpen ? <X className="w-4 h-4" /> : <Menu className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {/* Mobile Drawer */}
      {mobileMenuOpen && (
        <div className="md:hidden px-6 py-4 space-y-3 bg-[#08090a] border-t border-[#161719] text-xs text-[#9d9ea1]">
          {!isConsoleRoute ? (
            <>
              {PUBLIC_NAV.map((item) => (
                <a
                  key={item.href}
                  href={item.href}
                  onClick={() => setMobileMenuOpen(false)}
                  className="block hover:text-[#f2f2f0]"
                >
                  {item.label}
                </a>
              ))}
              <Link
                href="/console"
                onClick={() => setMobileMenuOpen(false)}
                className="block text-[#f2f2f0] pt-2 font-medium"
              >
                Open Console &rarr;
              </Link>
            </>
          ) : (
            <>
              <Link
                href="/"
                onClick={() => setMobileMenuOpen(false)}
                className="block text-zinc-500 hover:text-white mb-2"
              >
                &larr; Public Site
              </Link>
              {CONSOLE_NAV.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={() => setMobileMenuOpen(false)}
                  className={clsx(
                    "block",
                    pathname === item.href ? "text-[#f2f2f0] font-medium" : "text-[#9d9ea1]"
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
        description="Provide the secret API key configured for this role."
      >
        <form onSubmit={handleAuthenticate} className="space-y-4">
          <div>
            <label className="block text-xs text-[#9d9ea1] mb-1.5">
              API Key for {targetRole?.toUpperCase()}
            </label>
            <input
              type="password"
              value={inputApiKey}
              onChange={(e) => setInputApiKey(e.target.value)}
              placeholder="sentinel-..."
              className="w-full bg-[#08090a] border border-[#1e2023] rounded px-3 py-2 text-xs font-mono text-[#f2f2f0] placeholder:text-zinc-600 focus:outline-none focus:border-zinc-500"
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
            <Button type="submit" size="sm" variant="primary" isLoading={isSwitching}>
              Authenticate
            </Button>
          </div>
        </form>
      </Dialog>
    </header>
  );
}
