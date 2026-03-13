"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Activity, BarChart2, Briefcase, Home, Menu, X, Zap } from "lucide-react";
import { useState } from "react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

const NAV_ITEMS = [
  { href: "/dashboard", label: "Dashboard", icon: Home },
  { href: "/signals", label: "Signals", icon: Zap },
  { href: "/portfolio", label: "Portfolio", icon: Briefcase },
  { href: "/agents", label: "Agents", icon: Activity },
  { href: "/backtest", label: "Backtest", icon: BarChart2 },
];

export function Navbar() {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <header className="fixed top-0 left-0 right-0 z-50 border-b border-border/50 bg-background/80 backdrop-blur-md">
      <div className="max-w-7xl mx-auto px-4 h-14 flex items-center justify-between">
        {/* Logo */}
        <Link href="/" className="flex items-center gap-2 font-bold text-foreground">
          <div className="h-6 w-6 rounded bg-primary/20 border border-primary/30 flex items-center justify-center">
            <Zap className="h-3.5 w-3.5 text-primary" />
          </div>
          <span className="hidden sm:block text-sm">Trading Copilot</span>
          <span className="text-xs text-primary font-mono ml-1 hidden sm:block">AI</span>
        </Link>

        {/* Desktop nav */}
        <nav className="hidden md:flex items-center gap-1">
          {NAV_ITEMS.map(({ href, label, icon: Icon }) => (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors",
                pathname === href
                  ? "bg-primary/10 text-primary"
                  : "text-muted-foreground hover:text-foreground hover:bg-accent"
              )}
            >
              <Icon className="h-3.5 w-3.5" />
              {label}
            </Link>
          ))}
        </nav>

        <div className="flex items-center gap-2">
          <Link href="/pricing">
            <Button size="sm" variant="outline" className="hidden sm:flex h-7 text-xs">
              Upgrade
            </Button>
          </Link>
          <Link href="/login">
            <Button size="sm" className="h-7 text-xs hidden sm:flex">
              Sign In
            </Button>
          </Link>

          {/* Mobile menu toggle */}
          <button
            className="md:hidden p-1.5 rounded-md hover:bg-accent"
            onClick={() => setMobileOpen(!mobileOpen)}
          >
            {mobileOpen ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
          </button>
        </div>
      </div>

      {/* Mobile menu */}
      {mobileOpen && (
        <div className="md:hidden border-t border-border/50 bg-background/95 px-4 py-3 space-y-1">
          {NAV_ITEMS.map(({ href, label, icon: Icon }) => (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-2 px-3 py-2 rounded-md text-sm transition-colors",
                pathname === href ? "bg-primary/10 text-primary" : "text-muted-foreground hover:text-foreground hover:bg-accent"
              )}
              onClick={() => setMobileOpen(false)}
            >
              <Icon className="h-4 w-4" />
              {label}
            </Link>
          ))}
        </div>
      )}
    </header>
  );
}
