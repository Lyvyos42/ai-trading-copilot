"use client";

import { X, Clock, ArrowUpRight, ArrowDownRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { formatPrice } from "@/lib/utils";
import type { Signal } from "@/lib/api";

interface SignalDetailModalProps {
  signal: Signal;
  onClose: () => void;
}

export function SignalDetailModal({ signal, onClose }: SignalDetailModalProps) {
  const prob = signal.probability_score ?? signal.confidence_score ?? 50;
  const bullPct = signal.bullish_pct ?? prob;
  const bearPct = signal.bearish_pct ?? (100 - bullPct);
  const isBullish = prob >= 50;
  const isWin = signal.outcome === "WIN";
  const convictionTier = signal.conviction_tier || "MODERATE";
  const rrRatio = signal.risk_reward_ratio ?? 0;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
      <div className="panel-raised relative w-full max-w-2xl max-h-[90vh] overflow-y-auto p-6" onClick={(e) => e.stopPropagation()}>
        <button onClick={onClose} className="absolute top-3 right-3 text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))]">
          <X className="h-4 w-4" />
        </button>

        {/* Header: Ticker + Probability + Conviction */}
        <div className="flex items-center gap-3 mb-4">
          <span className="text-lg font-mono font-bold">{signal.ticker}</span>
          <span className={cn(
            "px-2 py-0.5 rounded text-[10px] font-mono font-bold",
            isBullish ? "bg-[hsl(var(--bull)/0.1)] text-bull" : "bg-[hsl(var(--bear)/0.1)] text-bear"
          )}>
            {Math.round(prob)}% {isBullish ? "BULLISH" : "BEARISH"}
          </span>
          <span className="text-[10px] font-mono text-[hsl(var(--muted-foreground))] uppercase">{signal.asset_class}</span>
          <span className={cn(
            "text-[9px] font-mono font-bold px-1.5 py-0.5 rounded border",
            convictionTier === "HIGH" ? "bg-[hsl(var(--bull)/0.1)] text-bull border-[hsl(var(--bull)/0.2)]" :
            convictionTier === "MODERATE" ? "bg-[hsl(38,85%,52%,0.1)] text-[hsl(38,85%,52%)] border-[hsl(38,85%,52%,0.2)]" :
            "bg-[hsl(var(--muted)/0.5)] text-[hsl(var(--muted-foreground))] border-[hsl(var(--border)/0.3)]"
          )}>
            {convictionTier}
          </span>
          {signal.outcome && (
            <div className={cn("px-2 py-0.5 rounded text-[10px] font-mono font-bold ml-auto",
              isWin ? "bg-[hsl(var(--bull)/0.1)] text-bull" : "bg-[hsl(var(--bear)/0.1)] text-bear"
            )}>
              {signal.outcome} {signal.pnl_pct != null && `(${signal.pnl_pct >= 0 ? "+" : ""}${signal.pnl_pct.toFixed(2)}%)`}
            </div>
          )}
        </div>

        {/* Probability bar */}
        <div className="mb-4">
          <div className="flex items-center justify-between mb-1">
            <span className="text-[10px] font-mono text-bull font-bold">{bullPct.toFixed(0)}% BULL</span>
            <span className="text-[10px] font-mono text-bear font-bold">{bearPct.toFixed(0)}% BEAR</span>
          </div>
          <div className="w-full flex h-2.5 rounded overflow-hidden">
            <div className="bg-[hsl(var(--bull)/0.7)] transition-all" style={{ width: `${bullPct}%` }} />
            <div className="bg-[hsl(var(--bear)/0.7)] transition-all" style={{ width: `${bearPct}%` }} />
          </div>
        </div>

        {/* Research Target + Invalidation + R:R */}
        <div className="grid grid-cols-3 gap-3 mb-4">
          <div className="data-cell">
            <span className="data-cell-label flex items-center gap-1"><ArrowUpRight className="h-3 w-3 text-bull" /> RESEARCH TARGET</span>
            <span className="data-cell-value text-bull">
              {signal.research_target ? formatPrice(signal.research_target) : formatPrice(signal.take_profit_1)}
            </span>
          </div>
          <div className="data-cell">
            <span className="data-cell-label flex items-center gap-1"><ArrowDownRight className="h-3 w-3 text-bear" /> INVALIDATION</span>
            <span className="data-cell-value text-bear">
              {signal.invalidation_level ? formatPrice(signal.invalidation_level) : formatPrice(signal.stop_loss)}
            </span>
          </div>
          <div className="data-cell">
            <span className="data-cell-label">POTENTIAL R:R</span>
            <span className="data-cell-value text-[hsl(var(--foreground))]">{rrRatio > 0 ? `${rrRatio.toFixed(1)}:1` : "N/A"}</span>
          </div>
        </div>

        {/* Meta row */}
        <div className="flex items-center gap-4 mb-4 text-[10px] font-mono text-[hsl(var(--muted-foreground))]">
          <span>STATUS: <span className="text-[hsl(var(--foreground))] font-bold">{signal.status}</span></span>
          {signal.analytical_window && (
            <span>WINDOW: <span className="text-[hsl(var(--foreground))] font-bold">{signal.analytical_window}</span></span>
          )}
          <span><Clock className="inline h-3 w-3" /> {new Date(signal.timestamp).toLocaleString()}</span>
        </div>

        {/* Bull / Bear cases */}
        {(signal.bull_case || signal.bear_case) && (
          <div className="grid grid-cols-2 gap-3 mb-4">
            {signal.bull_case && (
              <div className="p-3 rounded border border-[hsl(var(--bull)/0.2)] bg-[hsl(var(--bull)/0.05)]">
                <span className="text-[9px] font-mono font-bold text-bull flex items-center gap-1 mb-1">
                  <ArrowUpRight className="h-3 w-3" /> BULL CASE
                </span>
                <p className="text-[10px] font-mono text-[hsl(var(--foreground)/0.8)] leading-relaxed">{signal.bull_case}</p>
              </div>
            )}
            {signal.bear_case && (
              <div className="p-3 rounded border border-[hsl(var(--bear)/0.2)] bg-[hsl(var(--bear)/0.05)]">
                <span className="text-[9px] font-mono font-bold text-bear flex items-center gap-1 mb-1">
                  <ArrowDownRight className="h-3 w-3" /> BEAR CASE
                </span>
                <p className="text-[10px] font-mono text-[hsl(var(--foreground)/0.8)] leading-relaxed">{signal.bear_case}</p>
              </div>
            )}
          </div>
        )}

        {/* Agent contributions */}
        {signal.agent_votes && typeof signal.agent_votes === "object" && (
          <div className="mb-4">
            <span className="text-[10px] font-mono font-bold text-[hsl(var(--muted-foreground))] tracking-widest">AGENT CONTRIBUTIONS</span>
            <div className="space-y-1.5 mt-2">
              {Object.entries(signal.agent_votes).map(([agent, vote]) => {
                if (typeof vote !== "object" || vote === null || ["risk_approved", "quant_validated"].includes(agent)) return null;
                const v = vote as { direction?: string; confidence?: number; bullish_contribution?: number; bearish_contribution?: number };
                const bullC = v.bullish_contribution ?? (v.direction === "LONG" ? (v.confidence ?? 50) / 7 : 0);
                const bearC = v.bearish_contribution ?? (v.direction === "SHORT" ? (v.confidence ?? 50) / 7 : 0);
                const net = bullC - bearC;
                const isPos = net >= 0;
                return (
                  <div key={agent} className="flex items-center gap-2">
                    <span className="text-[10px] font-mono text-[hsl(var(--muted-foreground))] w-20 shrink-0 uppercase">
                      {agent.replace("_", " ")}
                    </span>
                    <div className="flex-1 h-2 bg-[hsl(var(--muted)/0.3)] rounded overflow-hidden relative">
                      <div className="absolute left-1/2 top-0 bottom-0 w-px bg-[hsl(var(--border)/0.5)]" />
                      {isPos ? (
                        <div className="absolute top-0 bottom-0 bg-[hsl(var(--bull)/0.6)] rounded-r"
                          style={{ left: '50%', width: `${Math.min(Math.abs(net) * 2, 50)}%` }} />
                      ) : (
                        <div className="absolute top-0 bottom-0 bg-[hsl(var(--bear)/0.6)] rounded-l"
                          style={{ right: '50%', width: `${Math.min(Math.abs(net) * 2, 50)}%` }} />
                      )}
                    </div>
                    <span className={cn(
                      "text-[10px] font-mono font-bold w-10 text-right",
                      isPos ? "text-bull" : "text-bear"
                    )}>
                      {isPos ? "+" : ""}{net.toFixed(0)}pp
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Reasoning chain */}
        {signal.reasoning_chain && signal.reasoning_chain.length > 0 && (
          <div className="mb-4">
            <span className="text-[10px] font-mono font-bold text-[hsl(var(--muted-foreground))] tracking-widest">REASONING CHAIN</span>
            <div className="mt-2 space-y-1">
              {signal.reasoning_chain.map((step, i) => (
                <div key={i} className="text-[11px] font-mono text-[hsl(var(--foreground)/0.8)] flex gap-2">
                  <span className="text-[hsl(var(--muted-foreground))] shrink-0">{i + 1}.</span>
                  <span>{step}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Strategy sources */}
        {signal.strategy_sources && signal.strategy_sources.length > 0 && (
          <div>
            <span className="text-[10px] font-mono font-bold text-[hsl(var(--muted-foreground))] tracking-widest">STRATEGIES</span>
            <div className="flex flex-wrap gap-1.5 mt-2">
              {signal.strategy_sources.map((s, i) => (
                <span key={i} className="px-1.5 py-0.5 rounded text-[9px] font-mono bg-[hsl(var(--primary)/0.1)] text-[hsl(var(--primary))]">{s}</span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
