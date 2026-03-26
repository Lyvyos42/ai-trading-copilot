"use client";

import { X, Clock } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Signal } from "@/lib/api";

interface SignalDetailModalProps {
  signal: Signal;
  onClose: () => void;
}

export function SignalDetailModal({ signal, onClose }: SignalDetailModalProps) {
  const isLong = signal.direction === "LONG";
  const isWin = signal.outcome === "WIN";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
      <div className="panel-raised relative w-full max-w-2xl max-h-[90vh] overflow-y-auto p-6" onClick={(e) => e.stopPropagation()}>
        <button onClick={onClose} className="absolute top-3 right-3 text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))]">
          <X className="h-4 w-4" />
        </button>

        <div className="flex items-center gap-3 mb-4">
          <div className={cn("px-2 py-0.5 rounded text-[10px] font-mono font-bold", isLong ? "bg-[hsl(var(--bull)/0.1)] text-bull" : "bg-[hsl(var(--bear)/0.1)] text-bear")}>
            {signal.direction}
          </div>
          <span className="text-lg font-mono font-bold">{signal.ticker}</span>
          <span className="text-[10px] font-mono text-[hsl(var(--muted-foreground))] uppercase">{signal.asset_class}</span>
          {signal.outcome && (
            <div className={cn("px-2 py-0.5 rounded text-[10px] font-mono font-bold ml-auto", isWin ? "bg-[hsl(var(--bull)/0.1)] text-bull" : "bg-[hsl(var(--bear)/0.1)] text-bear")}>
              {signal.outcome} {signal.pnl_pct != null && `(${signal.pnl_pct >= 0 ? "+" : ""}${signal.pnl_pct.toFixed(2)}%)`}
            </div>
          )}
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
          <LevelCell label="ENTRY" value={signal.entry_price} />
          <LevelCell label="STOP LOSS" value={signal.stop_loss} color="text-bear" />
          <LevelCell label="TP1" value={signal.take_profit_1} color="text-bull" />
          <LevelCell label="TP2" value={signal.take_profit_2} color="text-bull" />
          {signal.exit_price && <LevelCell label="EXIT" value={signal.exit_price} color={isWin ? "text-bull" : "text-bear"} />}
        </div>

        <div className="flex items-center gap-4 mb-4 text-[10px] font-mono text-[hsl(var(--muted-foreground))]">
          <span>CONF: <span className="text-[hsl(var(--foreground))] font-bold">{signal.confidence_score}</span></span>
          <span>STATUS: <span className="text-[hsl(var(--foreground))] font-bold">{signal.status}</span></span>
          <span><Clock className="inline h-3 w-3" /> {new Date(signal.timestamp).toLocaleString()}</span>
        </div>

        {signal.agent_votes && typeof signal.agent_votes === "object" && (
          <div className="mb-4">
            <span className="text-[10px] font-mono font-bold text-[hsl(var(--muted-foreground))] tracking-widest">AGENT VOTES</span>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-2 mt-2">
              {Object.entries(signal.agent_votes).map(([agent, vote]) => {
                if (typeof vote !== "object" || vote === null) return null;
                const v = vote as { direction?: string; confidence?: number };
                if (!v.direction) return null;
                return (
                  <div key={agent} className="flex items-center justify-between bg-[hsl(var(--surface-2))] rounded px-2 py-1">
                    <span className="text-[10px] font-mono text-[hsl(var(--foreground))] uppercase">{agent.replace("_", " ")}</span>
                    <div className="flex items-center gap-1.5">
                      <span className={cn("text-[10px] font-mono font-bold", v.direction === "LONG" ? "text-bull" : "text-bear")}>
                        {v.direction}
                      </span>
                      <span className="text-[9px] font-mono text-[hsl(var(--muted-foreground))]">{v.confidence ?? 0}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

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

function LevelCell({ label, value, color }: { label: string; value: number; color?: string }) {
  return (
    <div className="data-cell">
      <span className="data-cell-label">{label}</span>
      <span className={cn("data-cell-value", color || "text-[hsl(var(--foreground))]")}>{value.toFixed(2)}</span>
    </div>
  );
}
