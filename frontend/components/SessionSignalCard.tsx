"use client";

import { TrendingUp, TrendingDown, Minus, ShieldCheck, ShieldX } from "lucide-react";
import { cn } from "@/lib/utils";
import type { SessionSignal } from "@/lib/api";

interface SessionSignalCardProps {
  signal: SessionSignal;
}

export function SessionSignalCard({ signal }: SessionSignalCardProps) {
  const isLong = signal.direction === "LONG";
  const isShort = signal.direction === "SHORT";
  const isNeutral = signal.direction === "NEUTRAL";
  const DirectionIcon = isLong ? TrendingUp : isShort ? TrendingDown : Minus;
  const dirColor = isLong ? "text-bull" : isShort ? "text-bear" : "text-muted-foreground";

  return (
    <div className={cn(
      "rounded-lg border bg-background overflow-hidden",
      isLong ? "border-bull/30" : isShort ? "border-bear/30" : "border-border"
    )}>
      {/* Header */}
      <div className={cn(
        "flex items-center justify-between px-4 py-2",
        isLong ? "bg-bull/5" : isShort ? "bg-bear/5" : "bg-muted/10"
      )}>
        <div className="flex items-center gap-2">
          <DirectionIcon className={cn("h-4 w-4", dirColor)} />
          <span className={cn("text-sm font-mono font-bold", dirColor)}>
            {signal.direction}
          </span>
          <span className="text-[14px] font-mono text-muted-foreground">
            {signal.ticker}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className={cn(
            "text-[13px] font-mono font-bold px-1.5 py-0.5 rounded border",
            signal.urgency === "EXECUTE_NOW"
              ? "text-bull border-bull/30 bg-bull/10 animate-pulse"
              : signal.urgency === "WAIT_FOR_LEVEL"
                ? "text-warn border-warn/30 bg-warn/10"
                : "text-muted-foreground border-border"
          )}>
            {signal.urgency.replace(/_/g, " ")}
          </span>
          <span className={cn("text-sm font-mono font-bold", dirColor)}>
            {signal.confidence}%
          </span>
        </div>
      </div>

      {/* Levels grid */}
      {!isNeutral && (
        <div className="grid grid-cols-4 gap-px bg-border/30">
          {[
            { label: "ENTRY", value: signal.entry, color: "text-foreground" },
            { label: "STOP", value: signal.stop_loss, color: "text-bear" },
            { label: "TP1", value: signal.take_profit_1, color: "text-bull" },
            { label: "TP2", value: signal.take_profit_2, color: "text-bull" },
          ].map(({ label, value, color }) => (
            <div key={label} className="bg-background px-3 py-2 text-center">
              <div className="text-[8px] font-mono text-muted-foreground">{label}</div>
              <div className={cn("text-[14px] font-mono font-bold", color)}>
                {typeof value === "number" ? value.toFixed(2) : "—"}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Footer stats */}
      <div className="flex items-center gap-3 px-4 py-2 border-t border-border/30">
        <span className="text-[8px] font-mono text-muted-foreground">
          R:R <span className="text-foreground font-bold">{signal.risk_reward_ratio?.toFixed(1) || "—"}</span>
        </span>
        <span className="text-[8px] font-mono text-muted-foreground">
          Size <span className="text-foreground font-bold">{signal.position_size_pct?.toFixed(1)}%</span>
        </span>
        <span className="text-[8px] font-mono text-muted-foreground">
          Agree <span className="text-foreground font-bold">{signal.agent_agreement}/5</span>
        </span>
        <div className="ml-auto flex items-center gap-1">
          {signal.risk_gate_passed ? (
            <ShieldCheck className="h-3 w-3 text-bull" />
          ) : (
            <ShieldX className="h-3 w-3 text-bear" />
          )}
          <span className={cn(
            "text-[8px] font-mono font-bold",
            signal.risk_gate_passed ? "text-bull" : "text-bear"
          )}>
            {signal.risk_gate_mode}
          </span>
        </div>
      </div>

      {/* Agent votes */}
      <div className="flex items-center gap-1 px-4 py-1.5 border-t border-border/20 bg-muted/5">
        {signal.agent_votes?.map((vote) => (
          <span
            key={vote.agent}
            className={cn(
              "text-[7px] font-mono font-bold px-1.5 py-0.5 rounded border",
              vote.direction === "LONG" ? "text-bull border-bull/20 bg-bull/5" :
              vote.direction === "SHORT" ? "text-bear border-bear/20 bg-bear/5" :
              "text-muted-foreground border-border/30"
            )}
          >
            {vote.agent.slice(0, 4).toUpperCase()} {vote.confidence}%
          </span>
        ))}
      </div>
    </div>
  );
}
