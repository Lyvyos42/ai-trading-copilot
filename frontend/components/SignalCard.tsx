"use client";

import { useState } from "react";
import { TrendingUp, TrendingDown, Clock, Target, Shield, Zap, ChevronDown, ChevronUp } from "lucide-react";
import { type Signal, executePosition } from "@/lib/api";
import { formatPrice, timeAgo, directionBg } from "@/lib/utils";
import { cn } from "@/lib/utils";

const AGENT_SHORT: Record<string, string> = {
  fundamental: "FUND",
  technical:   "TECH",
  sentiment:   "SENT",
  macro:       "MACRO",
};

interface SignalCardProps {
  signal: Signal;
  onExecute?: (id: string) => void;
  /** Compact mode for dashboard feed panel */
  compact?: boolean;
}

export function SignalCard({ signal, onExecute, compact }: SignalCardProps) {
  const [expanded, setExpanded]   = useState(false);
  const [loading, setLoading]     = useState(false);
  const [executeError, setExecuteError] = useState<string | null>(null);
  const [executed, setExecuted]   = useState(false);

  const isLong    = signal.direction === "LONG";
  const riskPct   = Math.abs((signal.stop_loss - signal.entry_price) / signal.entry_price * 100);
  const rewardPct = Math.abs((signal.take_profit_1 - signal.entry_price) / signal.entry_price * 100);
  const rrRatio   = (rewardPct / riskPct).toFixed(1);

  const handleExecute = async (e: React.MouseEvent) => {
    e.stopPropagation();
    setLoading(true);
    setExecuteError(null);
    try {
      await executePosition(signal.signal_id);
      setExecuted(true);
      onExecute?.(signal.signal_id);
    } catch (err) {
      setExecuteError(err instanceof Error ? err.message : "Failed to execute trade");
    } finally {
      setLoading(false);
    }
  };

  /* ── COMPACT MODE — terminal feed row ─────────────────────────── */
  if (compact) {
    return (
      <div className="px-3 py-2.5">
        {/* Row 1: Ticker + Direction + Confidence */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className={cn(
              "text-[9px] font-mono font-bold px-1 rounded",
              isLong ? "bg-bull/10 text-bull" : "bg-bear/10 text-bear"
            )}>
              {isLong ? "▲" : "▼"}
            </span>
            <span className="text-xs font-mono font-bold text-foreground">{signal.ticker}</span>
            <span className={cn(
              "text-[9px] font-mono font-semibold px-1.5 rounded border",
              isLong ? "border-bull/30 text-bull" : "border-bear/30 text-bear"
            )}>
              {signal.direction}
            </span>
          </div>
          <div className="flex items-center gap-1.5">
            <ConfBar score={signal.confidence_score} />
            <span className={cn(
              "text-[10px] font-mono font-bold",
              signal.confidence_score >= 70 ? "text-bull" : signal.confidence_score >= 50 ? "text-warn" : "text-bear"
            )}>
              {Math.round(signal.confidence_score)}%
            </span>
          </div>
        </div>

        {/* Row 2: Prices */}
        <div className="flex items-center gap-3 mt-1.5">
          <span className="text-[9px] font-mono text-muted-foreground">
            ENTRY <span className="text-foreground font-semibold">{formatPrice(signal.entry_price)}</span>
          </span>
          <span className="text-[9px] font-mono text-muted-foreground">
            TP1 <span className="text-bull font-semibold">{formatPrice(signal.take_profit_1)}</span>
          </span>
          <span className="text-[9px] font-mono text-muted-foreground">
            SL <span className="text-bear font-semibold">{formatPrice(signal.stop_loss)}</span>
          </span>
        </div>

        {/* Row 3: Meta */}
        <div className="flex items-center justify-between mt-1.5">
          <div className="flex items-center gap-1 text-[9px] font-mono text-muted-foreground">
            <Clock className="h-2.5 w-2.5" />
            {timeAgo(signal.timestamp)}
            {signal.pipeline_latency_ms && (
              <span className="flex items-center gap-0.5 ml-1 text-warn">
                <Zap className="h-2.5 w-2.5" />{signal.pipeline_latency_ms}ms
              </span>
            )}
          </div>
          <span className="text-[9px] font-mono text-muted-foreground">R:R {rrRatio}x</span>
        </div>

        {/* Agent votes row */}
        <div className="flex gap-1 mt-2 flex-wrap">
          {Object.entries(signal.agent_votes).map(([agent, vote]) => {
            if (agent === "risk_approved" || typeof vote !== "object" || !vote) return null;
            const v = vote as { direction?: string };
            return (
              <span key={agent} className={cn(
                "text-[8px] font-mono px-1 py-0.5 rounded border",
                directionBg(v.direction || "NEUTRAL")
              )}>
                {AGENT_SHORT[agent] || agent}:{v.direction?.[0] || "?"}
              </span>
            );
          })}
          {signal.agent_votes.risk_approved !== undefined && (
            <span className={cn(
              "text-[8px] font-mono px-1 py-0.5 rounded border flex items-center gap-0.5",
              signal.agent_votes.risk_approved ? "bg-bull/10 text-bull border-bull/20" : "bg-bear/10 text-bear border-bear/20"
            )}>
              <Shield className="h-2 w-2" />
              {signal.agent_votes.risk_approved ? "RISK✓" : "RISK✗"}
            </span>
          )}
        </div>
      </div>
    );
  }

  /* ── FULL MODE — signal detail card ───────────────────────────── */
  return (
    <div className="terminal-panel animate-fade-in">
      <div className="p-4">
        {/* Header */}
        <div className="flex items-start justify-between mb-3">
          <div className="flex items-center gap-2">
            <div className={cn("p-1.5 rounded border", isLong ? "bg-bull/10 border-bull/20" : "bg-bear/10 border-bear/20")}>
              {isLong
                ? <TrendingUp className="h-4 w-4 text-bull" />
                : <TrendingDown className="h-4 w-4 text-bear" />}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-foreground text-lg font-mono">{signal.ticker}</span>
                <span className={cn(
                  "text-xs font-mono font-bold px-1.5 py-0.5 rounded border",
                  isLong ? "bg-bull/10 text-bull border-bull/30" : "bg-bear/10 text-bear border-bear/30"
                )}>
                  {signal.direction}
                </span>
                <span className="text-xs font-mono text-muted-foreground border border-border px-1.5 rounded">
                  {signal.asset_class}
                </span>
              </div>
              <div className="flex items-center gap-1.5 mt-0.5 text-xs text-muted-foreground font-mono">
                <Clock className="h-3 w-3" />
                {timeAgo(signal.timestamp)}
                {signal.pipeline_latency_ms && (
                  <span className="flex items-center gap-0.5 ml-1 text-warn">
                    <Zap className="h-3 w-3" />{signal.pipeline_latency_ms}ms
                  </span>
                )}
              </div>
            </div>
          </div>
          <ConfidenceRing score={signal.confidence_score} />
        </div>

        {/* Price levels */}
        <div className="grid grid-cols-4 gap-2 mb-3">
          <PriceBox label="ENTRY" value={signal.entry_price} colorClass="text-primary" borderClass="border-primary/30" />
          <PriceBox label="SL" value={signal.stop_loss} colorClass="text-bear" borderClass="border-bear/30" />
          <PriceBox label="TP1" value={signal.take_profit_1} colorClass="text-bull" borderClass="border-bull/30" />
          <PriceBox label="TP2" value={signal.take_profit_2} colorClass="text-bull/70" borderClass="border-bull/20" />
        </div>

        {/* Risk/reward bar */}
        <div className="flex items-center gap-2 mb-3 text-xs font-mono">
          <span className="text-muted-foreground w-12">RISK/RWD</span>
          <div className="flex-1 flex gap-0.5 h-1.5 rounded overflow-hidden">
            <div className="bg-bear/60" style={{ width: `${Math.min(riskPct * 5, 40)}%` }} />
            <div className="bg-bull/60 flex-1" style={{ width: `${Math.min(rewardPct * 5, 60)}%` }} />
          </div>
          <span className="text-bear w-10 text-right">{riskPct.toFixed(1)}%</span>
          <span className="text-muted-foreground">/</span>
          <span className="text-bull w-10">{rewardPct.toFixed(1)}%</span>
          <span className="text-muted-foreground ml-2">{rrRatio}x</span>
        </div>

        {/* Agent votes */}
        <div className="flex gap-1.5 mb-3 flex-wrap">
          {Object.entries(signal.agent_votes).map(([agent, vote]) => {
            if (agent === "risk_approved") return null;
            if (typeof vote !== "object" || !vote) return null;
            const v = vote as { direction?: string };
            return (
              <div key={agent} className={cn("text-xs font-mono px-2 py-0.5 rounded border", directionBg(v.direction || "NEUTRAL"))}>
                {AGENT_SHORT[agent] || agent}: {v.direction || "N/A"}
              </div>
            );
          })}
          {signal.agent_votes.risk_approved !== undefined && (
            <div className={cn(
              "text-xs font-mono px-2 py-0.5 rounded border flex items-center gap-1",
              signal.agent_votes.risk_approved ? "bg-bull/10 text-bull border-bull/20" : "bg-bear/10 text-bear border-bear/20"
            )}>
              <Shield className="h-3 w-3" />
              RISK {signal.agent_votes.risk_approved ? "APPROVED" : "REJECTED"}
            </div>
          )}
        </div>

        {/* Strategy tags */}
        {signal.strategy_sources?.length > 0 && (
          <div className="flex gap-1 flex-wrap mb-3">
            {signal.strategy_sources.slice(0, 3).map((s) => (
              <span key={s} className="text-[9px] font-mono bg-secondary text-secondary-foreground px-1.5 py-0.5 rounded border border-border/50">
                {s.replace(/_/g, " ")}
              </span>
            ))}
            {signal.strategy_sources.length > 3 && (
              <span className="text-[9px] font-mono text-muted-foreground">+{signal.strategy_sources.length - 3} more</span>
            )}
          </div>
        )}

        {/* Reasoning chain */}
        {expanded && signal.reasoning_chain?.length > 0 && (
          <div className="mb-3 space-y-1 border border-border/50 rounded p-2 bg-muted/30">
            <div className="terminal-label mb-1">REASONING CHAIN</div>
            {signal.reasoning_chain.map((step, i) => (
              <div key={i} className="text-xs text-muted-foreground flex gap-2 font-mono">
                <span className="text-primary/60 w-4 shrink-0">{i + 1}.</span>
                <span>{step}</span>
              </div>
            ))}
          </div>
        )}

        {/* Actions */}
        <div className="flex flex-col gap-1.5 pt-2 border-t border-border/50">
          {executeError && (
            <div className="text-[10px] font-mono text-bear bg-bear/10 border border-bear/30 rounded px-2 py-1">
              ✗ {executeError}
            </div>
          )}
          {executed && (
            <div className="text-[10px] font-mono text-bull bg-bull/10 border border-bull/30 rounded px-2 py-1">
              ✓ Paper trade opened — check Portfolio
            </div>
          )}
          <div className="flex items-center justify-between">
            <button
              className="flex items-center gap-1 text-[10px] font-mono text-muted-foreground hover:text-foreground transition-colors"
              onClick={() => setExpanded(!expanded)}
            >
              {expanded ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
              {expanded ? "HIDE" : "REASONING"}
            </button>
            <div className="flex gap-2">
              <button className="text-[10px] font-mono px-2 py-1 rounded border border-border/50 text-muted-foreground hover:text-foreground transition-colors flex items-center gap-1">
                <Target className="h-2.5 w-2.5" /> BACKTEST
              </button>
              <button
                onClick={handleExecute}
                disabled={loading || executed}
                className={cn(
                  "text-[10px] font-mono px-3 py-1 rounded border font-bold transition-colors",
                  (loading || executed) ? "opacity-50 cursor-not-allowed" : "",
                  isLong
                    ? "bg-bull/10 border-bull/30 text-bull hover:bg-bull/20"
                    : "bg-bear/10 border-bear/30 text-bear hover:bg-bear/20"
                )}
              >
                {loading ? "…" : executed ? "EXECUTED" : "PAPER TRADE"}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function PriceBox({ label, value, colorClass, borderClass }: {
  label: string; value: number; colorClass: string; borderClass: string;
}) {
  return (
    <div className={cn("text-center p-2 rounded border bg-background/40", borderClass)}>
      <div className="terminal-label mb-0.5">{label}</div>
      <div className={cn("text-xs font-mono font-bold", colorClass)}>{formatPrice(value)}</div>
    </div>
  );
}

function ConfBar({ score }: { score: number }) {
  const color = score >= 70 ? "bg-bull" : score >= 50 ? "bg-warn" : "bg-bear";
  return (
    <div className="h-1.5 w-12 bg-muted rounded overflow-hidden">
      <div className={cn("h-full rounded", color)} style={{ width: `${score}%` }} />
    </div>
  );
}

function ConfidenceRing({ score }: { score: number }) {
  const color = score >= 70 ? "#00c55a" : score >= 50 ? "#f59e0b" : "#e63946";
  const radius = 16;
  const circ = 2 * Math.PI * radius;
  const dash = (score / 100) * circ;
  return (
    <div className="relative inline-flex items-center justify-center">
      <svg width="44" height="44" viewBox="0 0 44 44">
        <circle cx="22" cy="22" r={radius} fill="none" stroke="hsl(var(--border))" strokeWidth="3" />
        <circle
          cx="22" cy="22" r={radius}
          fill="none" stroke={color} strokeWidth="3"
          strokeDasharray={`${dash} ${circ}`}
          strokeLinecap="round"
          transform="rotate(-90 22 22)"
        />
      </svg>
      <span className="absolute text-[10px] font-mono font-bold" style={{ color }}>{Math.round(score)}</span>
    </div>
  );
}
