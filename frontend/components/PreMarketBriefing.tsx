"use client";

import { useState } from "react";
import { Compass, ChevronDown, ChevronUp, ShieldCheck, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";

export function PreMarketBriefing() {
  const [open, setOpen] = useState(false);

  return (
    <div className="border-b border-border/40 bg-surface-2/40 select-none">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-3 py-1.5 hover:bg-surface-2 transition-colors text-left"
      >
        <div className="flex items-center gap-2">
          <Compass className="h-3.5 w-3.5 text-primary" />
          <span className="text-[11px] font-mono font-bold text-foreground tracking-wider">
            DAILY REGIME BRIEFING & CATALYSTS
          </span>
          <span className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-primary/10 text-primary border border-primary/20">
            AUTONOMOUS
          </span>
        </div>
        <div className="flex items-center gap-1 text-[10px] font-mono text-muted-foreground">
          <span>{open ? "COLLAPSE" : "EXPAND"}</span>
          {open ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
        </div>
      </button>

      {open && (
        <div className="p-3 border-t border-border/30 bg-surface-1/90 space-y-2 text-xs font-mono animate-fade-in">
          <div className="flex items-start gap-2">
            <span className="text-primary font-bold">1.</span>
            <p className="text-[11px] text-muted-foreground leading-relaxed">
              <strong className="text-foreground">Regime Assessment:</strong> Volatility clustering indicates an expansion regime. Intraday momentum favored over wide swing holds; risk manager enforces 0.5x Kelly buffer on breakout setups.
            </p>
          </div>

          <div className="flex items-start gap-2">
            <span className="text-primary font-bold">2.</span>
            <p className="text-[11px] text-muted-foreground leading-relaxed">
              <strong className="text-foreground">Macro Stance:</strong> Treasury yield curve stability and central bank commentary suggest range-bound conditions across FX majors with selective alpha in high-beta equity tech.
            </p>
          </div>

          <div className="flex items-start gap-2">
            <span className="text-primary font-bold">3.</span>
            <p className="text-[11px] text-muted-foreground leading-relaxed">
              <strong className="text-foreground">Order Flow Bias:</strong> CVD absorption detected at key European liquidity pools. Monitor 15m Fair Value Gaps during London/NY session overlap.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
