"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState, useEffect, useRef, useCallback } from "react";
import { cn } from "@/lib/utils";
import { supabase } from "@/lib/supabase";
import { useAuth } from "@/lib/useAuth";
import type { UserTier } from "@/lib/useAuth";
import {
  IconTerminal,
  IconSignal,
  IconIntel,
  IconPortfolio,
  IconAgents,
  IconBacktest,
  IconLogout,
  IconCrown,
  IconChevronDown,
  IconMenu,
  IconX,
  IconShield,
  IconCalendar,
  IconGrid,
} from "@/components/icons/GeoIcons";

const NAV_ITEMS = [
  { href: "/dashboard",    label: "DASHBOARD",    Icon: IconTerminal },
  { href: "/signals",      label: "SIGNALS",      Icon: IconSignal },
  { href: "/performance",  label: "PERFORMANCE",  Icon: IconSignal },
  { href: "/journal",      label: "JOURNAL",      Icon: IconPortfolio },
  { href: "/news",         label: "INTEL",        Icon: IconIntel },
  { href: "/portfolio",    label: "PORTFOLIO",    Icon: IconPortfolio },
  { href: "/agents",       label: "AGENTS",       Icon: IconAgents },
  { href: "/backtest",     label: "BACKTEST",     Icon: IconBacktest },
  { href: "/calendar",     label: "CALENDAR",     Icon: IconCalendar },
  { href: "/correlation",  label: "CORR MAP",     Icon: IconGrid },
  { href: "/memory",       label: "MEMORY",       Icon: IconShield },
  { href: "/guide",        label: "GUIDE",        Icon: IconShield },
];

const TIER_LABEL: Record<UserTier, string> = {
  visitor:    "VISITOR",
  free:       "FREE",
  retail:     "RETAIL",
  pro:        "PRO",
  enterprise: "ENTERPRISE",
  admin:      "ADMIN",
};

const TIER_COLOR: Record<UserTier, string> = {
  visitor:    "text-[hsl(var(--muted-foreground))] border-[hsl(var(--border-strong))]",
  free:       "text-[hsl(var(--muted-foreground))] border-[hsl(var(--border-strong))]",
  retail:     "text-[hsl(var(--primary))] border-[hsl(var(--primary)/0.4)]",
  pro:        "text-amber-400 border-amber-400/40",
  enterprise: "text-amber-400 border-amber-400/40",
  admin:      "text-red-400 border-red-400/40",
};

const TIER_QUOTA: Record<UserTier, number | null> = {
  visitor:    0,
  free:       2,
  retail:     50,
  pro:        200,
  enterprise: null,
  admin:      null,
};

function getInitials(email: string): string {
  return email.charAt(0).toUpperCase();
}

export function Navbar({ unreadAlerts = 0 }: { unreadAlerts?: number }) {
  const pathname  = usePathname();
  const router    = useRouter();
  const { user, tier, isLoggedIn, loading } = useAuth();

  const [mobileOpen,   setMobileOpen]   = useState(false);
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [signalsToday, setSignalsToday] = useState<number | null>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!dropdownOpen) return;
    function onClickOutside(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setDropdownOpen(false);
      }
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, [dropdownOpen]);

  const refreshSignalCount = useCallback(async () => {
    if (!isLoggedIn) return;
    try {
      const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const { data: { session } } = await supabase.auth.getSession();
      const token = session?.access_token ?? localStorage.getItem("token");
      if (!token) return;
      const res = await fetch(`${API}/api/v1/signals?limit=100`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) return;
      const signals: { timestamp: string; status?: string }[] = await res.json();
      const todayStart = new Date();
      todayStart.setUTCHours(0, 0, 0, 0);
      const todayActive = signals.filter(s =>
        new Date(s.timestamp) >= todayStart &&
        (!s.status || s.status === "ACTIVE" || s.status === "EXECUTED")
      );
      setSignalsToday(todayActive.length);
    } catch {}
  }, [isLoggedIn]);

  // Refresh when dropdown opens
  useEffect(() => {
    if (dropdownOpen) refreshSignalCount();
  }, [dropdownOpen, refreshSignalCount]);

  // Refresh when a signal is resolved anywhere in the app
  useEffect(() => {
    const handler = () => refreshSignalCount();
    window.addEventListener("signal-resolved", handler);
    return () => window.removeEventListener("signal-resolved", handler);
  }, [refreshSignalCount]);

  const handleLogout = async () => {
    setDropdownOpen(false);
    await supabase.auth.signOut();
    localStorage.removeItem("token");
    router.push("/login");
  };

  const quota     = TIER_QUOTA[tier];
  const usagePct  = quota && signalsToday !== null ? Math.min((signalsToday / quota) * 100, 100) : 0;
  const showUpgrade = tier === "free" || tier === "visitor";
  const isPremium   = tier === "pro" || tier === "enterprise" || tier === "admin";

  return (
    <header
      className="fixed top-0 left-0 right-0 z-50 border-b border-[hsl(var(--border))]"
      style={{
        background: "hsl(var(--surface-1))",
        /* Top-edge specular highlight — material surface quality */
        boxShadow: "inset 0 1px 0 hsl(0 0% 20% / 0.5), 0 1px 0 hsl(0 0% 0% / 0.6)",
      }}
    >
      <div className="px-3 h-10 flex items-center justify-between gap-4">

        {/* Logo — wordmark + geometric mark */}
        <Link href="/" className="flex items-center gap-2.5 shrink-0 group">
          {/* Geometric logo mark — rotating octahedron silhouette */}
          <div
            className="h-5 w-5 flex items-center justify-center shrink-0"
            style={{
              background: "hsl(var(--primary) / 0.12)",
              border: "1px solid hsl(var(--primary) / 0.35)",
              borderRadius: "2px",
            }}
          >
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="hsl(var(--primary))" strokeWidth="1.2" strokeLinecap="round">
              <polygon points="6,1 11,6 6,11 1,6" />
              <line x1="6" y1="1" x2="6" y2="11" strokeWidth="0.6" opacity="0.4" />
              <line x1="1" y1="6" x2="11" y2="6" strokeWidth="0.6" opacity="0.4" />
            </svg>
          </div>
          <span
            className="hidden sm:block text-[13px] font-bold tracking-[0.18em] uppercase"
            style={{ fontFamily: "'BerkeleyMono', 'IBM Plex Mono', monospace", color: "hsl(var(--foreground))" }}
          >
            QuantNeural
          </span>
          <span
            className="hidden lg:block text-[8px] font-medium tracking-[0.12em] uppercase px-1.5 py-0.5"
            style={{
              fontFamily: "'BerkeleyMono', 'IBM Plex Mono', monospace",
              color: "hsl(var(--muted-foreground))",
              border: "1px solid hsl(var(--border-strong))",
              borderRadius: "2px",
            }}
          >
            TERMINAL
          </span>
        </Link>

        {/* Mode toggle — RESEARCH | SESSION */}
        <div className="hidden md:flex items-center gap-0.5 mx-1 p-0.5 rounded border border-[hsl(var(--border-strong))] bg-[hsl(var(--surface-2)/0.3)]">
          <Link
            href="/dashboard"
            className={cn(
              "px-2 py-0.5 text-[8px] font-bold tracking-[0.1em] rounded transition-colors",
              !pathname?.startsWith("/session")
                ? "bg-[hsl(var(--primary)/0.12)] text-[hsl(var(--primary))]"
                : "text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))]"
            )}
            style={{ fontFamily: "'BerkeleyMono', 'IBM Plex Mono', monospace" }}
          >
            RESEARCH
          </Link>
          <Link
            href="/session"
            className={cn(
              "px-2 py-0.5 text-[8px] font-bold tracking-[0.1em] rounded transition-colors flex items-center gap-1",
              pathname?.startsWith("/session")
                ? "bg-[hsl(var(--primary)/0.12)] text-[hsl(var(--primary))]"
                : "text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))]"
            )}
            style={{ fontFamily: "'BerkeleyMono', 'IBM Plex Mono', monospace" }}
          >
            SESSION
            <span className="text-[6px] text-amber-400 border border-amber-400/30 rounded px-0.5 leading-tight">PRO</span>
          </Link>
        </div>

        {/* Desktop nav */}
        <nav className="hidden md:flex items-center h-full overflow-x-auto scrollbar-none">
          {NAV_ITEMS.map(({ href, label, Icon }) => {
            const active  = pathname === href || pathname.startsWith(href + "/");
            const isIntel = href === "/news";
            return (
              <Link
                key={href}
                href={href}
                className={cn(
                  "relative flex items-center gap-0.5 px-1.5 lg:px-2 h-10 transition-colors shrink-0",
                  "text-[10px] font-bold tracking-[0.06em] lg:tracking-[0.1em] uppercase",
                  "border-b-[1.5px]",
                )}
                style={{
                  fontFamily: "'BerkeleyMono', 'IBM Plex Mono', monospace",
                  color: active ? "hsl(var(--primary))" : "hsl(var(--muted-foreground))",
                  borderBottomColor: active ? "hsl(var(--primary))" : "transparent",
                  background: active ? "hsl(var(--primary) / 0.04)" : "transparent",
                }}
                onMouseEnter={e => {
                  if (!active) (e.currentTarget as HTMLElement).style.color = "hsl(var(--foreground))";
                }}
                onMouseLeave={e => {
                  if (!active) (e.currentTarget as HTMLElement).style.color = "hsl(var(--muted-foreground))";
                }}
              >
                <Icon size={11} color="currentColor" strokeWidth={active ? 2 : 1.5} />
                {label}
                {isIntel && unreadAlerts > 0 && (
                  <span
                    className="absolute top-2.5 right-1.5 h-1.5 w-1.5 rounded-full"
                    style={{ background: "hsl(var(--bear))", animation: "pulse-live 1.6s ease-in-out infinite" }}
                  />
                )}
              </Link>
            );
          })}
        </nav>

        {/* Right side */}
        <div className="flex items-center gap-2 shrink-0">

          {/* Live indicator */}
          <div className="hidden sm:flex items-center gap-1.5">
            <span className="live-dot" />
            <span
              className="text-[8px] font-bold tracking-[0.12em]"
              style={{ fontFamily: "'BerkeleyMono', 'IBM Plex Mono', monospace", color: "hsl(var(--bull))" }}
            >
              LIVE
            </span>
          </div>

          {/* Divider */}
          <div className="hidden sm:block h-5 w-px" style={{ background: "hsl(var(--border-strong))" }} />

          {/* Paper equity */}
          <div
            className="hidden lg:flex items-center gap-1.5 px-2 py-1"
            style={{
              border: "1px solid hsl(var(--border-strong))",
              borderRadius: "2px",
              background: "hsl(var(--surface-0))",
            }}
          >
            <span className="terminal-label">PAPER</span>
            <span
              className="text-[13px] font-bold"
              style={{ fontFamily: "'BerkeleyMono', 'IBM Plex Mono', monospace", color: "hsl(var(--primary))" }}
            >
              $100,000
            </span>
          </div>

          {/* Account area */}
          {!loading && (
            isLoggedIn && user ? (
              <div className="relative hidden sm:block" ref={dropdownRef}>

                {/* Trigger */}
                <button
                  type="button"
                  onClick={() => setDropdownOpen((v) => !v)}
                  className={cn(
                    "flex items-center gap-1.5 px-2 py-1 transition-colors",
                    "text-[13px] font-bold tracking-[0.08em]",
                  )}
                  style={{
                    fontFamily: "'BerkeleyMono', 'IBM Plex Mono', monospace",
                    border: "1px solid",
                    borderColor: dropdownOpen ? "hsl(var(--primary) / 0.5)" : "hsl(var(--border-strong))",
                    borderRadius: "2px",
                    background: dropdownOpen ? "hsl(var(--primary) / 0.06)" : "hsl(var(--surface-0))",
                    color: dropdownOpen ? "hsl(var(--primary))" : "hsl(var(--muted-foreground))",
                  }}
                >
                  {/* Avatar mark */}
                  <span
                    className="h-4 w-4 flex items-center justify-center text-[8px] font-bold shrink-0"
                    style={{
                      background: "hsl(var(--primary) / 0.15)",
                      border: "1px solid hsl(var(--primary) / 0.3)",
                      borderRadius: "2px",
                      color: "hsl(var(--primary))",
                      fontFamily: "'BerkeleyMono', 'IBM Plex Mono', monospace",
                    }}
                  >
                    {getInitials(user.email)}
                  </span>
                  <span className="max-w-[100px] truncate hidden md:inline">{user.email}</span>
                  <IconChevronDown
                    size={11}
                    color="currentColor"
                    className="shrink-0 transition-transform duration-150"
                    style={{ transform: dropdownOpen ? "rotate(180deg)" : "none" }}
                  />
                </button>

                {/* Dropdown */}
                {dropdownOpen && (
                  <div
                    className="absolute right-0 top-[calc(100%+4px)] w-64 z-[100]"
                    style={{
                      background: "hsl(var(--surface-3))",
                      border: "1px solid hsl(var(--border-strong))",
                      borderRadius: "2px",
                      /* Raised surface specular */
                      boxShadow: "inset 0 1px 0 hsl(0 0% 30% / 0.5), 0 8px 32px hsl(0 0% 0% / 0.6)",
                    }}
                  >
                    {/* Surface top highlight */}
                    <div
                      className="absolute top-0 left-0 right-0 h-px"
                      style={{
                        background: "linear-gradient(90deg, transparent, hsl(0 0% 35% / 0.8) 50%, transparent)",
                        zIndex: 1,
                      }}
                    />

                    {/* User header */}
                    <div
                      className="px-4 py-3"
                      style={{ borderBottom: "1px solid hsl(var(--border))" }}
                    >
                      <div className="flex items-center gap-2.5">
                        <div
                          className="h-7 w-7 flex items-center justify-center text-xs font-bold shrink-0"
                          style={{
                            background: "hsl(var(--primary) / 0.12)",
                            border: "1px solid hsl(var(--primary) / 0.25)",
                            borderRadius: "2px",
                            color: "hsl(var(--primary))",
                            fontFamily: "'BerkeleyMono', 'IBM Plex Mono', monospace",
                          }}
                        >
                          {getInitials(user.email)}
                        </div>
                        <div className="min-w-0 flex-1">
                          <div
                            className="text-[14px] truncate"
                            style={{ fontFamily: "'BerkeleyMono', 'IBM Plex Mono', monospace", color: "hsl(var(--foreground))" }}
                          >
                            {user.email}
                          </div>
                          <div
                            className={cn(
                              "inline-flex items-center gap-1 text-[8px] font-bold px-1.5 py-0.5 border mt-1",
                              TIER_COLOR[tier]
                            )}
                            style={{ borderRadius: "2px", fontFamily: "'BerkeleyMono', 'IBM Plex Mono', monospace" }}
                          >
                            {isPremium && <IconCrown size={9} color="currentColor" />}
                            {TIER_LABEL[tier]}
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Usage meter */}
                    {quota !== null && (
                      <div
                        className="px-4 py-2.5"
                        style={{ borderBottom: "1px solid hsl(var(--border))" }}
                      >
                        <div className="flex items-center justify-between mb-1.5">
                          <span className="terminal-label">SIGNALS TODAY</span>
                          <span
                            className="text-[13px] font-bold"
                            style={{ fontFamily: "'BerkeleyMono', 'IBM Plex Mono', monospace", color: "hsl(var(--foreground))" }}
                          >
                            {signalsToday ?? "—"} / {quota}
                          </span>
                        </div>
                        {/* Precise progress bar */}
                        <div
                          className="h-[3px] w-full overflow-hidden"
                          style={{ background: "hsl(var(--border-strong))", borderRadius: "1px" }}
                        >
                          <div
                            className="h-full transition-all duration-500"
                            style={{
                              width: `${usagePct}%`,
                              borderRadius: "1px",
                              background: usagePct >= 100
                                ? "hsl(var(--bear))"
                                : usagePct >= 80
                                ? "hsl(var(--warn))"
                                : "hsl(var(--primary))",
                            }}
                          />
                        </div>
                        {usagePct >= 100 && (
                          <p
                            className="text-[8px] mt-1"
                            style={{ fontFamily: "'BerkeleyMono', 'IBM Plex Mono', monospace", color: "hsl(var(--bear))" }}
                          >
                            Quota reached — resets at midnight UTC
                          </p>
                        )}
                      </div>
                    )}

                    {/* Upgrade CTA */}
                    {showUpgrade && (
                      <div className="px-3 py-2.5" style={{ borderBottom: "1px solid hsl(var(--border))" }}>
                        <Link
                          href="/pricing"
                          onClick={() => setDropdownOpen(false)}
                          className="flex items-center justify-between w-full px-3 py-2 group transition-colors"
                          style={{
                            border: "1px solid hsl(var(--primary) / 0.25)",
                            borderRadius: "2px",
                            background: "hsl(var(--primary) / 0.04)",
                          }}
                          onMouseEnter={e => { (e.currentTarget as HTMLElement).style.background = "hsl(var(--primary) / 0.08)"; }}
                          onMouseLeave={e => { (e.currentTarget as HTMLElement).style.background = "hsl(var(--primary) / 0.04)"; }}
                        >
                          <div>
                            <div
                              className="text-[13px] font-bold"
                              style={{ fontFamily: "'BerkeleyMono', 'IBM Plex Mono', monospace", color: "hsl(var(--primary))" }}
                            >
                              UPGRADE TO RETAIL
                            </div>
                            <div
                              className="text-[8px] mt-0.5"
                              style={{ fontFamily: "'BerkeleyMono', 'IBM Plex Mono', monospace", color: "hsl(var(--muted-foreground))" }}
                            >
                              Unlimited · All asset classes
                            </div>
                          </div>
                          <span
                            className="text-[13px] font-bold transition-transform group-hover:translate-x-0.5"
                            style={{ fontFamily: "'BerkeleyMono', 'IBM Plex Mono', monospace", color: "hsl(var(--primary))" }}
                          >
                            $49/mo
                          </span>
                        </Link>
                      </div>
                    )}

                    {/* Nav links */}
                    <div className="px-2 py-1.5" style={{ borderBottom: "1px solid hsl(var(--border))" }}>
                      {[
                        { href: "/portfolio", label: "Portfolio",       Icon: IconPortfolio },
                        { href: "/pricing",   label: "Pricing & Plans", Icon: IconShield },
                      ].map(({ href, label, Icon }) => (
                        <Link
                          key={href}
                          href={href}
                          onClick={() => setDropdownOpen(false)}
                          className="flex items-center gap-2 px-2 py-1.5 transition-colors"
                          style={{
                            borderRadius: "2px",
                            color: "hsl(var(--muted-foreground))",
                            fontSize: "10px",
                            fontFamily: "'BerkeleyMono', 'IBM Plex Mono', monospace",
                          }}
                          onMouseEnter={e => {
                            (e.currentTarget as HTMLElement).style.color = "hsl(var(--foreground))";
                            (e.currentTarget as HTMLElement).style.background = "hsl(var(--surface-4))";
                          }}
                          onMouseLeave={e => {
                            (e.currentTarget as HTMLElement).style.color = "hsl(var(--muted-foreground))";
                            (e.currentTarget as HTMLElement).style.background = "transparent";
                          }}
                        >
                          <Icon size={11} color="currentColor" />
                          {label}
                        </Link>
                      ))}
                    </div>

                    {/* Sign out */}
                    <div className="px-2 py-1.5">
                      <button
                        type="button"
                        onClick={handleLogout}
                        className="flex items-center gap-2 w-full px-2 py-1.5 transition-colors"
                        style={{
                          borderRadius: "2px",
                          color: "hsl(var(--muted-foreground))",
                          fontSize: "10px",
                          fontFamily: "'BerkeleyMono', 'IBM Plex Mono', monospace",
                          background: "none",
                          border: "none",
                          cursor: "pointer",
                        }}
                        onMouseEnter={e => {
                          (e.currentTarget as HTMLElement).style.color = "hsl(var(--bear))";
                          (e.currentTarget as HTMLElement).style.background = "hsl(var(--bear) / 0.05)";
                        }}
                        onMouseLeave={e => {
                          (e.currentTarget as HTMLElement).style.color = "hsl(var(--muted-foreground))";
                          (e.currentTarget as HTMLElement).style.background = "transparent";
                        }}
                      >
                        <IconLogout size={11} color="currentColor" />
                        Sign out
                      </button>
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <Link
                href="/login"
                className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 transition-colors"
                style={{
                  border: "1px solid hsl(var(--primary) / 0.3)",
                  borderRadius: "2px",
                  color: "hsl(var(--primary))",
                  fontSize: "9px",
                  fontFamily: "'BerkeleyMono', 'IBM Plex Mono', monospace",
                  fontWeight: 700,
                  letterSpacing: "0.08em",
                  background: "hsl(var(--primary) / 0.04)",
                }}
                onMouseEnter={e => { (e.currentTarget as HTMLElement).style.background = "hsl(var(--primary) / 0.10)"; }}
                onMouseLeave={e => { (e.currentTarget as HTMLElement).style.background = "hsl(var(--primary) / 0.04)"; }}
              >
                SIGN IN
              </Link>
            )
          )}

          {/* Mobile toggle */}
          <button
            type="button"
            className="md:hidden p-1.5 transition-colors"
            style={{ color: "hsl(var(--muted-foreground))", background: "none", border: "none", cursor: "pointer" }}
            onClick={() => setMobileOpen(!mobileOpen)}
          >
            {mobileOpen ? <IconX size={14} color="currentColor" /> : <IconMenu size={14} color="currentColor" />}
          </button>
        </div>
      </div>

      {/* Mobile menu */}
      {mobileOpen && (
        <div
          className="md:hidden border-t px-3 py-2 space-y-0.5"
          style={{ borderColor: "hsl(var(--border))", background: "hsl(var(--surface-2))" }}
        >
          {NAV_ITEMS.map(({ href, label, Icon }) => (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-2 px-3 py-2 transition-colors",
                "text-xs font-bold tracking-[0.1em]",
              )}
              style={{
                borderRadius: "2px",
                fontFamily: "'BerkeleyMono', 'IBM Plex Mono', monospace",
                color: pathname === href ? "hsl(var(--primary))" : "hsl(var(--muted-foreground))",
                background: pathname === href ? "hsl(var(--primary) / 0.06)" : "transparent",
              }}
              onClick={() => setMobileOpen(false)}
            >
              <Icon size={12} color="currentColor" />
              {label}
            </Link>
          ))}
          {isLoggedIn && user && (
            <div className="pt-2 mt-2 space-y-0.5" style={{ borderTop: "1px solid hsl(var(--border))" }}>
              <div
                className="px-3 py-1.5 text-[14px] truncate"
                style={{ fontFamily: "'BerkeleyMono', 'IBM Plex Mono', monospace", color: "hsl(var(--muted-foreground))" }}
              >
                {user.email}
              </div>
              <button
                type="button"
                onClick={handleLogout}
                className="flex items-center gap-2 w-full px-3 py-2 transition-colors"
                style={{
                  borderRadius: "2px",
                  color: "hsl(var(--muted-foreground))",
                  fontSize: "12px",
                  fontFamily: "'BerkeleyMono', 'IBM Plex Mono', monospace",
                  background: "none",
                  border: "none",
                  cursor: "pointer",
                }}
              >
                <IconLogout size={12} color="currentColor" />
                Sign out
              </button>
            </div>
          )}
        </div>
      )}
    </header>
  );
}
