"use client";

import { useState } from "react";
import { Target, Shield, Sparkles, Activity, Zap } from "lucide-react";
import { cn, formatPrice } from "@/lib/utils";
import type { Signal } from "@/lib/api";

interface ChartHolographicOverlayProps {
  signal: Signal | null;
  ticker: string;
  interval?: string;
  onGenerate?: (ticker: string) => void;
  loading?: boolean;
}

export function ChartHolographicOverlay({
  signal,
  ticker,
  interval = "5m",
  onGenerate,
  loading = false,
}: ChartHolographicOverlayProps) {
  const [hudVisible, setHudVisible] = useState(true);

  // STRICT VALIDATION: Ensure the signal actually belongs to the active ticker.
  // Never show values from a previous symbol!
  const matchingSignal =
    signal && signal.ticker.toUpperCase() === ticker.toUpperCase() ? signal : null;

  const isShort = matchingSignal?.direction === "SHORT";
  const entry = matchingSignal?.entry_price || matchingSignal?.current_price;
  const target = matchingSignal?.research_target || matchingSignal?.take_profit_1;
  const stopLoss = matchingSignal?.invalidation_level || matchingSignal?.stop_loss;

  const targetDelta =
    target && entry && entry > 0
      ? isShort
        ? ((entry - target) / entry) * 100
        : ((target - entry) / entry) * 100
      : null;

  const stopDelta =
    stopLoss && entry && entry > 0
      ? isShort
        ? ((stopLoss - entry) / entry) * 100
        : ((entry - stopLoss) / entry) * 100
      : null;

  return (
    <div className="absolute inset-0 pointer-events-none overflow-hidden z-10 select-none">
      {/* Top Controls & Status Bar (Docked over chart header, pointer-events-auto) */}
      <div className="absolute top-2.5 right-3 flex items-center gap-2 pointer-events-auto z-20">
        {/* Toggle HUD Button */}
        <button
          onClick={() => setHudVisible(!hudVisible)}
          className={cn(
            "px-2 py-0.5 rounded text-[9px] font-mono font-bold border transition-colors flex items-center gap-1 backdrop-blur-md shadow-lg",
            hudVisible
              ? "bg-primary/20 text-primary border-primary/50 shadow-[0_0_10px_rgba(212,162,64,0.15)]"
              : "bg-surface-2/80 text-muted-foreground border-border/40 hover:text-foreground"
          )}
          title="Toggle 2027 Quantitative Level Telemetry"
        >
          <Sparkles className="h-2.5 w-2.5" />
          <span>HUD TELEMETRY: {hudVisible ? "ON" : "OFF"}</span>
        </button>

        {/* If no signal cached for this ticker, offer instant deliberate button */}
        {!matchingSignal && onGenerate && (
          <button
            onClick={() => onGenerate(ticker)}
            disabled={loading}
            className="px-2 py-0.5 rounded text-[9px] font-mono font-bold border border-primary/50 bg-primary/20 text-primary hover:bg-primary/30 transition-colors flex items-center gap-1 shadow-lg animate-pulse"
          >
            <Zap className="h-2.5 w-2.5" />
            <span>{loading ? "SYNTHESIZING..." : `ANALYZE ${ticker}`}</span>
          </button>
        )}
      </div>

      {/* Floating Holographic Telemetry Cards (Docked to chart margins, 100% symbol-synchronized) */}
      {hudVisible && (
        <>
          {matchingSignal && entry && target && stopLoss ? (
            /* Active Signal Holographic HUD */
            <div className="absolute top-2.5 left-3 pointer-events-auto flex flex-wrap items-center gap-1.5 animate-fade-in z-20">
              {/* Instrument & Direction Badge */}
              <div className="flex items-center gap-1 px-2 py-1 rounded bg-surface-1/90 backdrop-blur-md border border-border/70 text-[10px] font-mono shadow-xl">
                <span className="font-bold text-foreground">{ticker}</span>
                <span
                  className={cn(
                    "px-1 py-0.2 rounded font-bold uppercase text-[8px]",
                    matchingSignal.direction === "LONG"
                      ? "bg-bull/15 text-bull border border-bull/30"
                      : matchingSignal.direction === "SHORT"
                      ? "bg-bear/15 text-bear border border-bear/30"
                      : "bg-surface-3 text-muted-foreground"
                  )}
                >
                  {matchingSignal.direction}
                </span>
                <span className="text-muted-foreground">({interval.toUpperCase()})</span>
              </div>

              {/* Target Price Glowing Ray Pill */}
              <div className="flex items-center gap-1 px-2 py-1 rounded bg-surface-1/90 backdrop-blur-md border border-bull/40 text-[10px] font-mono shadow-[0_0_12px_rgba(34,197,94,0.15)] text-bull">
                <Target className="h-3 w-3" />
                <span className="font-bold">TP: {formatPrice(target, ticker)}</span>
                {targetDelta !== null && (
                  <span className="text-[9px] font-bold opacity-90">
                    ({targetDelta >= 0 ? "+" : ""}{targetDelta.toFixed(1)}%)
                  </span>
                )}
              </div>

              {/* Stop Loss Glowing Ray Pill */}
              <div className="flex items-center gap-1 px-2 py-1 rounded bg-surface-1/90 backdrop-blur-md border border-bear/40 text-[10px] font-mono shadow-[0_0_12px_rgba(239,68,68,0.15)] text-bear">
                <Shield className="h-3 w-3" />
                <span className="font-bold">SL: {formatPrice(stopLoss, ticker)}</span>
                {stopDelta !== null && (
                  <span className="text-[9px] font-bold opacity-90">
                    ({stopDelta >= 0 ? "+" : ""}{stopDelta.toFixed(1)}%)
                  </span>
                )}
              </div>

              {/* R:R Ratio Chip */}
              {matchingSignal.risk_reward_ratio && matchingSignal.risk_reward_ratio > 0 && (
                <div className="px-2 py-1 rounded bg-surface-1/90 backdrop-blur-md border border-border/70 text-[10px] font-mono font-bold text-primary shadow-xl">
                  R:R {matchingSignal.risk_reward_ratio.toFixed(1)}:1
                </div>
              )}
            </div>
          ) : (
            /* Standby Calibration State (Strictly for current ticker, NEVER showing previous ticker) */
            <div className="absolute top-2.5 left-3 pointer-events-auto flex items-center gap-2 px-2.5 py-1 rounded bg-surface-1/90 backdrop-blur-md border border-border/60 text-[10px] font-mono shadow-xl z-20">
              <span className="h-1.5 w-1.5 rounded-full bg-primary animate-pulse" />
              <span className="text-muted-foreground">ACTIVE INSTRUMENT:</span>
              <span className="font-bold text-foreground">{ticker}</span>
              <span className="text-muted-foreground border-l border-border/40 pl-2">
                {loading ? "DELIBERATING 9 AGENTS..." : "READY FOR SYNTHESIS"}
              </span>
            </div>
          )}
        </>
      )}
    </div>
  );
}
