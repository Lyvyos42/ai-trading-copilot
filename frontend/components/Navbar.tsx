"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Activity, BarChart2, Briefcase, ChevronDown, Crown, LayoutDashboard, LogOut, Menu, Newspaper, Shield, X, Zap, BellRing } from "lucide-react";
import { useState, useEffect, useRef } from "react";
import { cn } from "@/lib/utils";
import { supabase } from "@/lib/supabase";
import { useAuth } from "@/lib/useAuth";
import type { UserTier } from "@/lib/useAuth";

const NAV_ITEMS = [
  { href: "/dashboard",  label: "TERMINAL",  icon: LayoutDashboard },
  { href: "/signals",    label: "SIGNALS",   icon: Zap },
  { href: "/news",       label: "INTEL",     icon: Newspaper },
  { href: "/portfolio",  label: "PORTFOLIO", icon: Briefcase },
  { href: "/agents",     label: "AGENTS",    icon: Activity },
  { href: "/backtest",   label: "BACKTEST",  icon: BarChart2 },
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
  visitor:    "text-muted-foreground border-border/50",
  free:       "text-muted-foreground border-border/50",
  retail:     "text-primary border-primary/40",
  pro:        "text-yellow-400 border-yellow-400/40",
  enterprise: "text-yellow-400 border-yellow-400/40",
  admin:      "text-red-400 border-red-400/40",
};

const TIER_QUOTA: Record<UserTier, number | null> = {
  visitor:    0,
  free:       5,
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

  // Close on outside click
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

  // Fetch today's signal count when dropdown opens
  useEffect(() => {
    if (!dropdownOpen || !isLoggedIn) return;
    (async () => {
      try {
        const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
        const { data: { session } } = await supabase.auth.getSession();
        const token = session?.access_token ?? localStorage.getItem("token");
        if (!token) return;
        const res = await fetch(`${API}/api/v1/signals?limit=100`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!res.ok) return;
        const signals: { timestamp: string }[] = await res.json();
        const todayStart = new Date();
        todayStart.setUTCHours(0, 0, 0, 0);
        setSignalsToday(signals.filter(s => new Date(s.timestamp) >= todayStart).length);
      } catch {}
    })();
  }, [dropdownOpen, isLoggedIn]);

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
    <header className="fixed top-0 left-0 right-0 z-50 border-b border-border bg-[hsl(0_0%_2%)]">
      <div className="px-3 h-10 flex items-center justify-between gap-4">

        {/* Logo */}
        <Link href="/" className="flex items-center gap-2 shrink-0">
          <div className="h-5 w-5 rounded-sm bg-primary/20 border border-primary/40 flex items-center justify-center">
            <Zap className="h-3 w-3 text-primary" />
          </div>
          <span className="hidden sm:block font-mono text-xs font-bold tracking-widest text-primary uppercase">
            QuantNeural
          </span>
          <span className="hidden lg:block font-mono text-[9px] font-medium tracking-wider text-muted-foreground border border-border px-1 rounded">
            TERMINAL
          </span>
        </Link>

        {/* Desktop nav */}
        <nav className="hidden md:flex items-center h-full">
          {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
            const active  = pathname === href || pathname.startsWith(href + "/");
            const isIntel = href === "/news";
            return (
              <Link
                key={href}
                href={href}
                className={cn(
                  "flex items-center gap-1.5 px-3 h-10 text-[10px] font-mono font-bold tracking-widest transition-colors border-b-2",
                  active
                    ? "text-primary border-primary bg-primary/5"
                    : "text-muted-foreground hover:text-foreground border-transparent hover:border-border hover:bg-white/[0.02]"
                )}
              >
                <Icon className="h-3 w-3" />
                {label}
                {isIntel && unreadAlerts > 0 && (
                  <span className="h-1.5 w-1.5 rounded-full bg-bear animate-pulse" />
                )}
              </Link>
            );
          })}
        </nav>

        {/* Right side */}
        <div className="flex items-center gap-2 shrink-0">

          {/* Live indicator */}
          <div className="hidden sm:flex items-center gap-1.5 text-[9px] font-mono text-muted-foreground">
            <span className="live-dot" />
            <span className="text-bull font-semibold">LIVE</span>
          </div>

          {/* Paper equity */}
          <div className="hidden lg:flex items-center gap-1 border border-border/50 rounded px-2 py-0.5">
            <span className="text-[9px] font-mono text-muted-foreground">PAPER</span>
            <span className="text-[9px] font-mono font-bold text-primary">$100,000</span>
          </div>

          {/* Account area */}
          {!loading && (
            isLoggedIn && user ? (
              <div className="relative hidden sm:block" ref={dropdownRef}>

                {/* Trigger button */}
                <button
                  type="button"
                  onClick={() => setDropdownOpen((v) => !v)}
                  className={cn(
                    "flex items-center gap-1.5 px-2 py-1 border transition-colors text-[9px] font-mono rounded",
                    dropdownOpen
                      ? "border-primary/60 bg-primary/10 text-primary"
                      : "border-border/50 text-muted-foreground hover:border-primary/30 hover:text-foreground"
                  )}
                >
                  <span className="h-4 w-4 rounded-sm bg-primary/20 border border-primary/30 flex items-center justify-center text-[8px] font-bold text-primary shrink-0">
                    {getInitials(user.email)}
                  </span>
                  <span className="max-w-[110px] truncate">{user.email}</span>
                  <ChevronDown className={cn("h-2.5 w-2.5 shrink-0 transition-transform duration-150", dropdownOpen && "rotate-180")} />
                </button>

                {/* Dropdown panel */}
                {dropdownOpen && (
                  <div className="absolute right-0 top-[calc(100%+4px)] w-64 border border-border bg-[hsl(0_0%_3%)] shadow-2xl rounded-sm z-[100]">

                    {/* User header */}
                    <div className="px-4 py-3 border-b border-border/50">
                      <div className="flex items-center gap-2.5">
                        <div className="h-7 w-7 rounded-sm bg-primary/15 border border-primary/25 flex items-center justify-center text-xs font-bold text-primary shrink-0">
                          {getInitials(user.email)}
                        </div>
                        <div className="min-w-0 flex-1">
                          <div className="text-[10px] font-mono text-foreground truncate">{user.email}</div>
                          <div className={cn(
                            "inline-flex items-center gap-1 text-[8px] font-mono font-bold px-1.5 py-0.5 border rounded mt-1",
                            TIER_COLOR[tier]
                          )}>
                            {isPremium && <Crown className="h-2 w-2" />}
                            {TIER_LABEL[tier]}
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Signals usage meter */}
                    {quota !== null && (
                      <div className="px-4 py-2.5 border-b border-border/40">
                        <div className="flex items-center justify-between mb-1.5">
                          <span className="text-[9px] font-mono text-muted-foreground">SIGNALS TODAY</span>
                          <span className="text-[9px] font-mono font-bold text-foreground">
                            {signalsToday ?? "—"} / {quota}
                          </span>
                        </div>
                        <div className="h-1 w-full bg-border/50 rounded-full overflow-hidden">
                          <div
                            className={cn(
                              "h-full rounded-full transition-all duration-500",
                              usagePct >= 100 ? "bg-bear" : usagePct >= 80 ? "bg-yellow-400" : "bg-primary"
                            )}
                            style={{ width: `${usagePct}%` }}
                          />
                        </div>
                        {usagePct >= 100 && (
                          <p className="text-[8px] font-mono text-bear mt-1">Quota reached — resets at midnight UTC</p>
                        )}
                      </div>
                    )}

                    {/* Upgrade CTA */}
                    {showUpgrade && (
                      <div className="px-3 py-2.5 border-b border-border/40">
                        <Link
                          href="/pricing"
                          onClick={() => setDropdownOpen(false)}
                          className="flex items-center justify-between w-full px-3 py-2 border border-primary/30 bg-primary/5 hover:bg-primary/10 transition-colors rounded-sm group"
                        >
                          <div>
                            <div className="text-[9px] font-mono font-bold text-primary">UPGRADE TO RETAIL</div>
                            <div className="text-[8px] font-mono text-muted-foreground">Unlimited · All asset classes</div>
                          </div>
                          <span className="text-[10px] font-mono font-bold text-primary group-hover:translate-x-0.5 transition-transform">
                            $49/mo →
                          </span>
                        </Link>
                      </div>
                    )}

                    {/* Nav links */}
                    <div className="px-2 py-1.5 border-b border-border/40">
                      {[
                        { href: "/portfolio", label: "Portfolio",       icon: Briefcase },
                        { href: "/pricing",   label: "Pricing & Plans", icon: Shield    },
                      ].map(({ href, label, icon: Icon }) => (
                        <Link
                          key={href}
                          href={href}
                          onClick={() => setDropdownOpen(false)}
                          className="flex items-center gap-2 px-2 py-1.5 rounded-sm text-[10px] font-mono text-muted-foreground hover:text-foreground hover:bg-white/[0.04] transition-colors"
                        >
                          <Icon className="h-3 w-3" />
                          {label}
                        </Link>
                      ))}
                    </div>

                    {/* Sign out */}
                    <div className="px-2 py-1.5">
                      <button
                        type="button"
                        onClick={handleLogout}
                        className="flex items-center gap-2 w-full px-2 py-1.5 rounded-sm text-[10px] font-mono text-muted-foreground hover:text-bear hover:bg-bear/5 transition-colors"
                      >
                        <LogOut className="h-3 w-3" />
                        Sign out
                      </button>
                    </div>

                  </div>
                )}
              </div>
            ) : (
              <Link
                href="/login"
                className="text-[10px] font-mono font-semibold px-2.5 py-1 rounded border border-primary/30 text-primary hover:bg-primary/10 transition-colors hidden sm:block"
              >
                SIGN IN
              </Link>
            )
          )}

          {/* Mobile toggle */}
          <button
            type="button"
            className="md:hidden p-1.5 rounded hover:bg-accent"
            onClick={() => setMobileOpen(!mobileOpen)}
          >
            {mobileOpen ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
          </button>
        </div>
      </div>

      {/* Mobile menu */}
      {mobileOpen && (
        <div className="md:hidden border-t border-border bg-[hsl(0_0%_3%)] px-3 py-2 space-y-0.5">
          {NAV_ITEMS.map(({ href, label, icon: Icon }) => (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-2 px-3 py-2 rounded text-xs font-mono font-bold tracking-widest transition-colors",
                pathname === href
                  ? "bg-primary/10 text-primary"
                  : "text-muted-foreground hover:text-foreground hover:bg-accent"
              )}
              onClick={() => setMobileOpen(false)}
            >
              <Icon className="h-3.5 w-3.5" />
              {label}
            </Link>
          ))}
          {isLoggedIn && user && (
            <div className="pt-2 mt-2 border-t border-border/50 space-y-0.5">
              <div className="px-3 py-1.5 text-[10px] font-mono text-muted-foreground truncate">{user.email}</div>
              <button
                type="button"
                onClick={handleLogout}
                className="flex items-center gap-2 w-full px-3 py-2 rounded text-xs font-mono text-muted-foreground hover:text-bear hover:bg-bear/5 transition-colors"
              >
                <LogOut className="h-3.5 w-3.5" />
                Sign out
              </button>
            </div>
          )}
        </div>
      )}
    </header>
  );
}
