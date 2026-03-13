"use client";

import { useState } from "react";
import { TrendingUp, TrendingDown, Clock, Target, Shield, Zap, ChevronDown, ChevronUp } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { type Signal, executePosition } from "@/lib/api";
import { formatPrice, formatPct, timeAgo, directionBg } from "@/lib/utils";
import { cn } from "@/lib/utils";

interface SignalCardProps {
  signal: Signal;
  onExecute?: (id: string) => void;
}

const AGENT_LABELS: Record<string, string> = {
  fundamental: "Fundamental",
  technical: "Technical",
  sentiment: "Sentiment",
  macro: "Macro",
};

export function SignalCard({ signal, onExecute }: SignalCardProps) {
  const [expanded, setExpanded] = useState(false);
  const [loading, setLoading] = useState(false);

  const isLong = signal.direction === "LONG";
  const Icon = isLong ? TrendingUp : TrendingDown;
  const riskPct = Math.abs((signal.stop_loss - signal.entry_price) / signal.entry_price * 100);
  const rewardPct = Math.abs((signal.take_profit_1 - signal.entry_price) / signal.entry_price * 100);

  const handleExecute = async () => {
    setLoading(true);
    try {
      await executePosition(signal.signal_id);
      onExecute?.(signal.signal_id);
    } catch {
      // silently handle — auth not required for demo
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card className="border-border/50 hover:border-border transition-colors animate-fade-in">
      <CardContent className="p-4">
        {/* Header Row */}
        <div className="flex items-start justify-between mb-3">
          <div className="flex items-center gap-2">
            <div className={cn("p-1.5 rounded-md", isLong ? "bg-bull/10" : "bg-bear/10")}>
              <Icon className={cn("h-4 w-4", isLong ? "text-bull" : "text-bear")} />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-foreground text-lg">{signal.ticker}</span>
                <Badge variant={isLong ? "bull" : "bear"}>{signal.direction}</Badge>
                <Badge variant="outline" className="text-xs">{signal.asset_class}</Badge>
              </div>
              <div className="flex items-center gap-1.5 mt-0.5 text-xs text-muted-foreground">
                <Clock className="h-3 w-3" />
                {timeAgo(signal.timestamp)}
                {signal.pipeline_latency_ms && (
                  <span className="flex items-center gap-0.5 ml-1">
                    <Zap className="h-3 w-3 text-yellow-500" />
                    {signal.pipeline_latency_ms}ms
                  </span>
                )}
              </div>
            </div>
          </div>
          <div className="text-right">
            <div className="text-xs text-muted-foreground mb-1">Confidence</div>
            <ConfidenceRing score={signal.confidence_score} />
          </div>
        </div>

        {/* Price Levels */}
        <div className="grid grid-cols-4 gap-2 mb-3">
          <PriceBox label="Entry" value={signal.entry_price} className="border-primary/30" />
          <PriceBox label="Stop" value={signal.stop_loss} className="border-bear/30 text-bear" />
          <PriceBox label="TP1" value={signal.take_profit_1} className="border-bull/30 text-bull" />
          <PriceBox label="TP2" value={signal.take_profit_2} className="border-bull/20 text-bull/70" />
        </div>

        {/* Risk/Reward bar */}
        <div className="flex items-center gap-2 mb-3 text-xs">
          <span className="text-muted-foreground w-12">Risk/Rwd</span>
          <div className="flex-1 flex gap-0.5 h-2 rounded overflow-hidden">
            <div
              className="bg-bear/60 rounded-l"
              style={{ width: `${Math.min(riskPct * 5, 40)}%` }}
            />
            <div
              className="bg-bull/60 rounded-r flex-1"
              style={{ width: `${Math.min(rewardPct * 5, 60)}%` }}
            />
          </div>
          <span className="text-bear w-10 text-right">{riskPct.toFixed(1)}%</span>
          <span className="text-muted-foreground">/</span>
          <span className="text-bull w-10">{rewardPct.toFixed(1)}%</span>
        </div>

        {/* Agent votes */}
        <div className="flex gap-1.5 mb-3 flex-wrap">
          {Object.entries(signal.agent_votes).map(([agent, vote]) => {
            if (agent === "risk_approved") return null;
            if (typeof vote !== "object" || vote === null) return null;
            const v = vote as { direction?: string; confidence?: number };
            return (
              <div
                key={agent}
                className={cn(
                  "text-xs px-2 py-0.5 rounded border",
                  directionBg(v.direction || "NEUTRAL")
                )}
              >
                {AGENT_LABELS[agent] || agent}: {v.direction || "N/A"}
              </div>
            );
          })}
          {signal.agent_votes.risk_approved !== undefined && (
            <div className={cn(
              "text-xs px-2 py-0.5 rounded border flex items-center gap-1",
              signal.agent_votes.risk_approved ? "bg-bull/10 text-bull border-bull/20" : "bg-bear/10 text-bear border-bear/20"
            )}>
              <Shield className="h-3 w-3" />
              Risk {signal.agent_votes.risk_approved ? "OK" : "REJECTED"}
            </div>
          )}
        </div>

        {/* Strategy badges */}
        {signal.strategy_sources?.length > 0 && (
          <div className="flex gap-1 flex-wrap mb-3">
            {signal.strategy_sources.slice(0, 3).map((s) => (
              <span key={s} className="text-xs bg-secondary text-secondary-foreground px-1.5 py-0.5 rounded font-mono">
                {s.replace(/_/g, " ")}
              </span>
            ))}
            {signal.strategy_sources.length > 3 && (
              <span className="text-xs text-muted-foreground">+{signal.strategy_sources.length - 3} more</span>
            )}
          </div>
        )}

        {/* Expanded reasoning chain */}
        {expanded && signal.reasoning_chain?.length > 0 && (
          <div className="mb-3 space-y-1">
            <div className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-1">Reasoning Chain</div>
            {signal.reasoning_chain.map((step, i) => (
              <div key={i} className="text-xs text-muted-foreground flex gap-2">
                <span className="text-primary/60 font-mono w-4 shrink-0">{i + 1}.</span>
                <span>{step}</span>
              </div>
            ))}
          </div>
        )}

        {/* Actions */}
        <div className="flex items-center justify-between pt-2 border-t border-border/50">
          <Button
            variant="ghost"
            size="sm"
            className="text-xs text-muted-foreground h-7 px-2"
            onClick={() => setExpanded(!expanded)}
          >
            {expanded ? <ChevronUp className="h-3 w-3 mr-1" /> : <ChevronDown className="h-3 w-3 mr-1" />}
            {expanded ? "Less" : "Reasoning"}
          </Button>
          <div className="flex gap-2">
            <Button variant="ghost" size="sm" className="h-7 text-xs">
              <Target className="h-3 w-3 mr-1" /> Backtest
            </Button>
            <Button
              size="sm"
              variant={isLong ? "bull" : "bear"}
              className="h-7 text-xs"
              onClick={handleExecute}
              disabled={loading}
            >
              {loading ? "..." : "Paper Trade"}
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function PriceBox({ label, value, className }: { label: string; value: number; className?: string }) {
  return (
    <div className={cn("text-center p-2 rounded-md border bg-background/40", className)}>
      <div className="text-xs text-muted-foreground mb-0.5">{label}</div>
      <div className="text-sm font-mono font-semibold">{formatPrice(value)}</div>
    </div>
  );
}

function ConfidenceRing({ score }: { score: number }) {
  const color = score >= 70 ? "#22c55e" : score >= 50 ? "#f59e0b" : "#ef4444";
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
      <span className="absolute text-xs font-bold" style={{ color }}>{Math.round(score)}%</span>
    </div>
  );
}
