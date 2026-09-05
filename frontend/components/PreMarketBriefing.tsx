"use client";

import { useState, useEffect } from "react";
import { Compass, X, ShieldCheck, Activity, Cpu } from "lucide-react";
import { cn } from "@/lib/utils";

interface PreMarketBriefingProps {
  isOpen?: boolean;
  onClose?: () => void;
}

export function PreMarketBriefing({ isOpen, onClose }: PreMarketBriefingProps) {
  const [internalOpen, setInternalOpen] = useState(false);
  const show = isOpen !== undefined ? isOpen : internalOpen;
  const handleClose = onClose || (() => setInternalOpen(false));

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && show) {
        handleClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [show, handleClose]);

  if (!show) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-16 px-4 bg-black/60 backdrop-blur-sm animate-fade-in">
      <div className="w-full max-w-2xl bg-surface-2 border border-border/70 rounded-md shadow-2xl overflow-hidden">
        {/* Modal Header */}
        <div className="flex items-center justify-between px-4 py-2.5 bg-surface-3 border-b border-border/50">
          <div className="flex items-center gap-2">
            <Compass className="h-4 w-4 text-primary" />
            <span className="text-xs font-mono font-bold text-foreground tracking-wider uppercase">
              AUTONOMOUS DAILY REGIME & MACRO INTELLIGENCE
            </span>
            <span className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-primary/10 text-primary border border-primary/20">
              SYNTHESIZED
            </span>
          </div>
          <button
            onClick={handleClose}
            className="text-muted-foreground hover:text-foreground p-1 rounded hover:bg-surface-4 transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Modal Content */}
        <div className="p-4 space-y-3 font-mono text-xs max-h-[70vh] overflow-y-auto">
          <div className="p-3 rounded border border-border/40 bg-surface-1/90 space-y-1">
            <div className="flex items-center gap-1.5 text-primary text-[11px] font-bold uppercase">
              <Activity className="h-3 w-3" /> 1. Market Volatility & Regime Assessment
            </div>
            <p className="text-[11px] text-muted-foreground leading-relaxed pl-4">
              Volatility clustering indicates an active expansion regime. Intraday momentum is statistically favored over multi-day swing holding. Quantitative risk manager enforces 0.5x Kelly buffer on breakout setups across high-beta equities and commodities.
            </p>
          </div>

          <div className="p-3 rounded border border-border/40 bg-surface-1/90 space-y-1">
            <div className="flex items-center gap-1.5 text-primary text-[11px] font-bold uppercase">
              <ShieldCheck className="h-3 w-3" /> 2. Cross-Asset Macro Stance
            </div>
            <p className="text-[11px] text-muted-foreground leading-relaxed pl-4">
              Treasury 10Y yield curve stabilization and global central bank rate trajectory suggest range-bound conditions across major FX pairs (EURUSD, USDJPY) with selective alpha concentration in AI infrastructure and gold spot liquidity sweeps.
            </p>
          </div>

          <div className="p-3 rounded border border-border/40 bg-surface-1/90 space-y-1">
            <div className="flex items-center gap-1.5 text-primary text-[11px] font-bold uppercase">
              <Cpu className="h-3 w-3" /> 3. Institutional Microstructure & Order Flow Bias
            </div>
            <p className="text-[11px] text-muted-foreground leading-relaxed pl-4">
              Cumulative Volume Delta (CVD) absorption detected at London liquidity boundaries. Active agents prioritize 5m/15m Fair Value Gap (FVG) retests and VWAP deviation bands during the London/New York session overlap window.
            </p>
          </div>
        </div>

        {/* Modal Footer */}
        <div className="px-4 py-2 bg-surface-3/50 border-t border-border/40 flex justify-between items-center text-[10px] font-mono text-muted-foreground">
          <span>Press ESC or click close to dismiss</span>
          <button
            onClick={handleClose}
            className="px-3 py-1 rounded bg-primary text-primary-foreground font-bold hover:bg-primary/90 transition-colors"
          >
            DISMISS
          </button>
        </div>
      </div>
    </div>
  );
}
