"use client";

import { useState } from "react";
import {
  Target,
  ArrowUpRight,
  ArrowDownRight,
  Copy,
  Check,
  Shield,
  Layers,
  Sparkles,
  TrendingUp,
  TrendingDown,
} from "lucide-react";
import { cn, formatPrice, formatPct, formatPositionSize } from "@/lib/utils";
import type { Signal } from "@/lib/api";

interface TradingCanvasHUDProps {
  ticker: string;
  signal: Signal | null;
  activeInterval: string;
  onIntervalChange: (interval: string) => void;
  show3D: boolean;
  onToggle3D: () => void;
  onAdoptSignal?: (signal: Signal) => void;
  isAdopted?: boolean;
}

const INTERVALS = ["5m", "15m", "1h", "4h", "1d"];

export function TradingCanvasHUD({
  ticker,
  signal,
  activeInterval,
  onIntervalChange,
  show3D,
  onToggle3D,
  onAdoptSignal,
  isAdopted = false,
}: TradingCanvasHUDProps) {
  const [copied, setCopied] = useState(false);

  if (!signal) {
    return (
      <div className="flex items-center justify-between px-4 py-2 border-b border-border/40 bg-surface-1/60 backdrop-blur-sm">
        <div className="flex items-center gap-2">
          <span className="text-sm font-mono font-bold text-foreground">{ticker}</span>
          <span className="text-[10px] font-mono text-muted-foreground">MONITORING MARKET</span>
        </div>
        <div className="flex items-center gap-1">
          {INTERVALS.map((inv) => (
            <button
              key={inv}
              onClick={() => onIntervalChange(inv)}
              className={cn(
                "px-2 py-0.5 rounded text-[10px] font-mono transition-colors",
                activeInterval === inv
                  ? "bg-primary text-primary-foreground font-bold"
                  : "text-muted-foreground hover:text-foreground hover:bg-surface-2"
              )}
            >
              {inv.toUpperCase()}
            </button>
          ))}
        </div>
      </div>
    );
  }

  const isNoSignal = signal.status === "NO_SIGNAL" || signal.direction === "NEUTRAL";
  const isShort = signal.direction === "SHORT";
  const entry = signal.entry_price || signal.current_price;
  const target = signal.research_target || signal.take_profit_1;
  const inval = signal.invalidation_level || signal.stop_loss;
  const spot = signal.current_price || entry;

  // Price Journey calculation:
  // If Long: 0% at Invalidation, Entry at mid, 100% at Target.
  // If Short: 0% at Invalidation, Entry at mid, 100% at Target.
  let journeyPct = 0;
  if (entry && target && inval && spot) {
    if (isShort) {
      const totalDist = inval - target;
      if (totalDist > 0) {
        journeyPct = Math.max(0, Math.min(100, ((inval - spot) / totalDist) * 100));
      }
    } else {
      const totalDist = target - inval;
      if (totalDist > 0) {
        journeyPct = Math.max(0, Math.min(100, ((spot - inval) / totalDist) * 100));
      }
    }
  }

  // Deltas
  const targetDelta =
    target && entry && entry > 0
      ? isShort
        ? ((entry - target) / entry) * 100
        : ((target - entry) / entry) * 100
      : null;

  const invalDelta =
    inval && entry && entry > 0
      ? isShort
        ? -((inval - entry) / entry) * 100
        : ((inval - entry) / entry) * 100
      : null;

  const handleCopy = () => {
    const text = `${signal.ticker} ${signal.direction}\nEntry: ${entry || "Market"}\nTarget: ${target || "—"}\nInvalidation: ${inval || "—"}\nR:R: ${signal.risk_reward_ratio || "—"}\nSize: ${formatPositionSize(signal.position_size_pct)}`;
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="border-b border-border/40 bg-surface-1/90 backdrop-blur-md px-3 py-2">
      {/* Top row: Symbol, Timeframe pills, Action buttons */}
      <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
        <div className="flex items-center gap-2">
          <span className="text-base font-mono font-bold text-foreground tracking-tight">
            {signal.ticker}
          </span>
          <span
            className={cn(
              "px-1.5 py-0.5 rounded text-[10px] font-mono font-bold uppercase",
              signal.direction === "LONG"
                ? "bg-bull/15 text-bull border border-bull/30"
                : signal.direction === "SHORT"
                ? "bg-bear/15 text-bear border border-bear/30"
                : "bg-muted text-muted-foreground border border-border"
            )}
          >
            {signal.direction}
          </span>
          <span className="text-[10px] font-mono text-muted-foreground border border-border/40 px-1.5 py-0.5 rounded uppercase">
            {signal.asset_class}
          </span>
          {signal.analytical_window && (
            <span className="text-[10px] font-mono text-primary/80 border border-primary/20 px-1.5 py-0.5 rounded">
              {signal.analytical_window}
            </span>
          )}
        </div>

        {/* Center: Timeframe selector */}
        <div className="flex items-center gap-1 bg-surface-2 p-0.5 rounded border border-border/40">
          {INTERVALS.map((inv) => (
            <button
              key={inv}
              onClick={() => onIntervalChange(inv)}
              className={cn(
                "px-2 py-0.5 rounded text-[10px] font-mono transition-colors",
                activeInterval === inv
                  ? "bg-primary text-primary-foreground font-bold shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              {inv.toUpperCase()}
            </button>
          ))}
        </div>

        {/* Right: Actions */}
        <div className="flex items-center gap-1.5">
          <button
            onClick={onToggle3D}
            className={cn(
              "flex items-center gap-1 px-2 py-1 rounded text-[10px] font-mono border transition-colors",
              show3D
                ? "bg-primary text-primary-foreground font-bold border-primary"
                : "border-border/40 hover:bg-surface-2 text-muted-foreground"
            )}
          >
            <Layers className="h-3 w-3" />
            <span>ORDER FLOW 3D</span>
          </button>

          <button
            onClick={handleCopy}
            className="flex items-center gap-1 px-2 py-1 rounded text-[10px] font-mono border border-border/40 hover:bg-surface-2 text-muted-foreground transition-colors"
          >
            {copied ? <Check className="h-3 w-3 text-bull" /> : <Copy className="h-3 w-3" />}
            <span>{copied ? "COPIED" : "COPY LEVELS"}</span>
          </button>

          {onAdoptSignal && (
            <button
              onClick={() => onAdoptSignal(signal)}
              disabled={isAdopted}
              className={cn(
                "flex items-center gap-1 px-2.5 py-1 rounded text-[10px] font-mono font-bold border transition-colors",
                isAdopted
                  ? "bg-bull/10 text-bull border-bull/30"
                  : "bg-primary/10 text-primary border-primary/30 hover:bg-primary/20"
              )}
            >
              <Sparkles className="h-3 w-3" />
              <span>{isAdopted ? "TRACKING ACTIVE" : "ADOPT SIGNAL"}</span>
            </button>
          )}
        </div>
      </div>

      {/* Floating Level Projections & Price Journey Bar (only if tradeable signal) */}
      {!isNoSignal && (
        <div className="space-y-2 pt-1 border-t border-border/30">
          {/* Level Cards Strip */}
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
            <div className="p-1.5 rounded border border-border/40 bg-surface-2 text-center">
              <div className="text-[9px] font-mono text-muted-foreground">ENTRY LEVEL</div>
              <div className="text-xs font-mono font-bold text-foreground">
                {formatPrice(entry, signal.ticker)}
              </div>
            </div>

            <div className="p-1.5 rounded border border-bull/30 bg-bull/5 text-center">
              <div className="text-[9px] font-mono text-bull flex items-center justify-center gap-0.5">
                <ArrowUpRight className="h-2.5 w-2.5" /> TARGET
              </div>
              <div className="text-xs font-mono font-bold text-bull">
                {formatPrice(target, signal.ticker)}
              </div>
              {targetDelta !== null && (
                <div className="text-[9px] font-mono text-bull/80">
                  {targetDelta >= 0 ? "+" : ""}
                  {targetDelta.toFixed(1)}%
                </div>
              )}
            </div>

            <div className="p-1.5 rounded border border-bear/30 bg-bear/5 text-center">
              <div className="text-[9px] font-mono text-bear flex items-center justify-center gap-0.5">
                <ArrowDownRight className="h-2.5 w-2.5" /> INVALIDATION
              </div>
              <div className="text-xs font-mono font-bold text-bear">
                {formatPrice(inval, signal.ticker)}
              </div>
              {invalDelta !== null && (
                <div className="text-[9px] font-mono text-bear/80">
                  {invalDelta >= 0 ? "+" : ""}
                  {invalDelta.toFixed(1)}%
                </div>
              )}
            </div>

            <div className="p-1.5 rounded border border-border/40 bg-surface-2 text-center">
              <div className="text-[9px] font-mono text-muted-foreground">R:R RATIO</div>
              <div className="text-xs font-mono font-bold text-primary">
                {signal.risk_reward_ratio && signal.risk_reward_ratio > 0
                  ? `${signal.risk_reward_ratio.toFixed(1)}:1`
                  : "—"}
              </div>
              <div className="text-[9px] font-mono text-muted-foreground">risk adjusted</div>
            </div>

            <div className="p-1.5 rounded border border-border/40 bg-surface-2 text-center">
              <div className="text-[9px] font-mono text-muted-foreground">POSITION SIZE</div>
              <div className="text-xs font-mono font-bold text-foreground">
                {formatPositionSize(signal.position_size_pct)}
              </div>
              <div className="text-[9px] font-mono text-muted-foreground">
                {typeof signal.position_size_pct === "number" && signal.position_size_pct > 0
                  ? "Kelly derived"
                  : "uncalibrated"}
              </div>
            </div>
          </div>

          {/* Real-time Price Journey Bar */}
          <div className="p-2 rounded border border-border/30 bg-surface-2/40">
            <div className="flex items-center justify-between text-[10px] font-mono text-muted-foreground mb-1">
              <span className="text-bear font-bold">STOP {formatPrice(inval, signal.ticker)}</span>
              <span className="font-bold text-foreground">
                SPOT {formatPrice(spot, signal.ticker)} ({journeyPct.toFixed(0)}% TO TARGET)
              </span>
              <span className="text-bull font-bold">TARGET {formatPrice(target, signal.ticker)}</span>
            </div>
            <div className="h-2 w-full bg-surface-3 rounded-full overflow-hidden relative">
              {/* Entry marker */}
              <div
                className="absolute top-0 bottom-0 w-0.5 bg-foreground/60 z-10"
                style={{ left: "35%" }}
                title="Entry Zone"
              />
              {/* Fill progress */}
              <div
                className={cn(
                  "h-full transition-all duration-500 rounded-full",
                  isShort
                    ? "bg-gradient-to-r from-bear/70 via-warn/70 to-bull"
                    : "bg-gradient-to-r from-bear/70 via-warn/70 to-bull"
                )}
                style={{ width: `${journeyPct}%` }}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
