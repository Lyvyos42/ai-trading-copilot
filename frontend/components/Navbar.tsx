"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Activity, BarChart2, Briefcase, LayoutDashboard, Menu, Newspaper, X, Zap } from "lucide-react";
import { useState } from "react";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/dashboard",  label: "TERMINAL",  icon: LayoutDashboard },
  { href: "/signals",    label: "SIGNALS",   icon: Zap },
  { href: "/news",       label: "INTEL",     icon: Newspaper },
  { href: "/portfolio",  label: "PORTFOLIO", icon: Briefcase },
  { href: "/agents",     label: "AGENTS",    icon: Activity },
  { href: "/backtest",   label: "BACKTEST",  icon: BarChart2 },
];

export function Navbar() {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <header className="fixed top-0 left-0 right-0 z-50 border-b border-border bg-[hsl(0_0%_2%)]">
      <div className="px-3 h-10 flex items-center justify-between gap-4">
        {/* Logo / Wordmark */}
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

        {/* Desktop nav — Bloomberg-style tab bar */}
        <nav className="hidden md:flex items-center h-full">
          {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
            const active = pathname === href || pathname.startsWith(href + "/");
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

          {/* Session info */}
          <div className="hidden lg:flex items-center gap-1 border border-border/50 rounded px-2 py-0.5">
            <span className="text-[9px] font-mono text-muted-foreground">PAPER</span>
            <span className="text-[9px] font-mono font-bold text-primary">$100,000</span>
          </div>

          <Link
            href="/login"
            className="text-[10px] font-mono font-semibold px-2.5 py-1 rounded border border-primary/30 text-primary hover:bg-primary/10 transition-colors hidden sm:block"
          >
            SIGN IN
          </Link>

          {/* Mobile toggle */}
          <button
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
                pathname === href ? "bg-primary/10 text-primary" : "text-muted-foreground hover:text-foreground hover:bg-accent"
              )}
              onClick={() => setMobileOpen(false)}
            >
              <Icon className="h-3.5 w-3.5" />
              {label}
            </Link>
          ))}
        </div>
      )}
    </header>
  );
}
