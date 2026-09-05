"use client";

import { useState, useEffect } from "react";
import { Clock, Zap, Activity, ChevronDown, Compass } from "lucide-react";
import { cn } from "@/lib/utils";

interface CockpitHeaderProps {
  activeProfile: string;
  onProfileChange: (profile: string) => void;
  regimeText?: string;
  regimeState?: "BULL" | "BEAR" | "NEUTRAL" | "HIGH_VOL";
  onToggleBriefing?: () => void;
  briefingOpen?: boolean;
}

interface MarketSession {
  name: string;
  openUtc: number;
  closeUtc: number;
  code: string;
}

const SESSIONS: MarketSession[] = [
  { name: "Tokyo", code: "TKY", openUtc: 0, closeUtc: 9 },
  { name: "London", code: "LDN", openUtc: 7, closeUtc: 16 },
  { name: "New York", code: "NYC", openUtc: 13, closeUtc: 21 },
];

const PROFILES = [
  { id: "balanced", label: "Balanced", tf: "1D", desc: "Multi-factor consensus" },
  { id: "scalper", label: "Scalper", tf: "5m", desc: "High-frequency momentum" },
  { id: "ict_smc", label: "ICT / SMC", tf: "15m", desc: "Liquidity sweeps and FVG" },
  { id: "orb", label: "ORB", tf: "15m", desc: "Opening range breakouts" },
  { id: "swing", label: "Swing", tf: "1D", desc: "Multi-day trend continuation" },
  { id: "vwap_pullback", label: "VWAP Pullback", tf: "30m", desc: "Mean reversion to benchmark" },
];

function formatTime(d: Date): string {
  return d.toISOString().substring(11, 19) + " UTC";
}

export function CockpitHeader({
  activeProfile,
  onProfileChange,
  regimeText = "NORMAL VOLATILITY",
  regimeState = "NEUTRAL",
  onToggleBriefing,
  briefingOpen = false,
}: CockpitHeaderProps) {
  const [now, setNow] = useState<Date | null>(null);
  const [profileDropdownOpen, setProfileDropdownOpen] = useState(false);

  useEffect(() => {
    setNow(new Date());
    const interval = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(interval);
  }, []);

  const currentUtcHour = now ? now.getUTCHours() + now.getUTCMinutes() / 60 : 12;

  return (
    <header className="h-9 border-b border-border/40 bg-surface-1/95 backdrop-blur-md px-3 flex items-center justify-between select-none z-30 shrink-0">
      {/* Left segment: Platform Identity, Live Clock, Daily Briefing Toggle */}
      <div className="flex items-center gap-2.5">
        <div className="flex items-center gap-2 pr-2.5 border-r border-border/40">
          <span className="live-dot" />
          <span className="text-[11px] font-mono font-bold tracking-widest text-primary">
            QUANTNEURAL
          </span>
          <span className="text-[9px] font-mono px-1 py-0.2 rounded border border-border/50 bg-surface-2 text-muted-foreground uppercase">
            2027 HUD
          </span>
        </div>

        <div className="flex items-center gap-1.5 text-[11px] font-mono text-muted-foreground">
          <Clock className="h-3 w-3 text-primary/70" />
          <span className="font-bold text-foreground">{now ? formatTime(now) : "— UTC"}</span>
        </div>

        {/* Daily Intelligence Briefing Toggle */}
        {onToggleBriefing && (
          <button
            onClick={onToggleBriefing}
            className={cn(
              "ml-1 flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono transition-colors border",
              briefingOpen
                ? "bg-primary/20 text-primary border-primary/40 font-bold"
                : "bg-surface-2/70 text-muted-foreground border-border/30 hover:text-foreground hover:bg-surface-3"
            )}
            title="Toggle Autonomous Daily Regime Briefing"
          >
            <Compass className="h-3 w-3 text-primary" />
            <span>DAILY BRIEFING</span>
          </button>
        )}
      </div>

      {/* Center segment: Institutional Kill Zones & Market Clocks */}
      <div className="hidden md:flex items-center gap-2">
        <span className="text-[9px] font-mono text-muted-foreground uppercase">
          KILL ZONES:
        </span>
        <div className="flex items-center gap-1">
          {SESSIONS.map((s) => {
            const isOpen =
              s.openUtc <= s.closeUtc
                ? currentUtcHour >= s.openUtc && currentUtcHour < s.closeUtc
                : currentUtcHour >= s.openUtc || currentUtcHour < s.closeUtc;

            return (
              <div
                key={s.code}
                className={cn(
                  "flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-mono border transition-colors",
                  isOpen
                    ? "bg-bull/10 text-bull border-bull/30 font-bold"
                    : "bg-surface-2/40 text-muted-foreground/80 border-border/20"
                )}
              >
                <span
                  className={cn(
                    "h-1.5 w-1.5 rounded-full",
                    isOpen ? "bg-bull animate-pulse" : "bg-muted-foreground/30"
                  )}
                />
                <span>{s.code}</span>
                <span className="opacity-70">
                  {isOpen ? "ACTIVE" : `${s.openUtc.toString().padStart(2, "0")}:00`}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Right segment: Regime Flag & Profile Selector */}
      <div className="flex items-center gap-2">
        {/* Regime Badge */}
        <div className="hidden sm:flex items-center gap-1 px-2 py-0.5 rounded border border-border/40 bg-surface-2 text-[10px] font-mono">
          <Activity className="h-2.5 w-2.5 text-primary" />
          <span className="text-muted-foreground text-[9px]">REGIME:</span>
          <span
            className={cn(
              "font-bold text-[9px]",
              regimeState === "BULL"
                ? "text-bull"
                : regimeState === "BEAR"
                ? "text-bear"
                : "text-primary"
            )}
          >
            {regimeText}
          </span>
        </div>

        {/* Profile Dropdown */}
        <div className="relative">
          <button
            onClick={() => setProfileDropdownOpen(!profileDropdownOpen)}
            className="flex items-center gap-1 px-2 py-0.5 rounded border border-primary/30 bg-primary/10 hover:bg-primary/20 text-primary text-[11px] font-mono font-bold transition-colors"
          >
            <Zap className="h-3 w-3" />
            <span>
              {PROFILES.find((p) => p.id === activeProfile)?.label || "Profile"} (
              {PROFILES.find((p) => p.id === activeProfile)?.tf || "1D"})
            </span>
            <ChevronDown className="h-2.5 w-2.5 opacity-70" />
          </button>

          {profileDropdownOpen && (
            <div className="absolute right-0 mt-1 w-56 rounded border border-border/60 bg-surface-2 p-1 shadow-2xl z-50 animate-fade-in">
              <div className="text-[9px] font-mono uppercase text-muted-foreground px-2 py-1 border-b border-border/30">
                Select Strategy Profile
              </div>
              {PROFILES.map((p) => (
                <button
                  key={p.id}
                  onClick={() => {
                    onProfileChange(p.id);
                    setProfileDropdownOpen(false);
                  }}
                  className={cn(
                    "w-full text-left px-2 py-1 rounded text-xs font-mono flex items-center justify-between hover:bg-surface-3 transition-colors",
                    activeProfile === p.id ? "text-primary font-bold bg-primary/5" : "text-foreground"
                  )}
                >
                  <div>
                    <div>{p.label}</div>
                    <div className="text-[9px] text-muted-foreground font-normal">{p.desc}</div>
                  </div>
                  <span className="text-[9px] px-1 py-0.2 rounded border border-border/40 bg-surface-1 text-muted-foreground">
                    {p.tf}
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
