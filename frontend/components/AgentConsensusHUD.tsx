"use client";

import { useState } from "react";
import {
  Shield,
  Activity,
  Zap,
  TrendingUp,
  TrendingDown,
  Scale,
  Brain,
  ChevronDown,
  ChevronUp,
  AlertCircle,
  HelpCircle,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { Signal } from "@/lib/api";

interface AgentConsensusHUDProps {
  signal: Signal | null;
}

interface AgentMeta {
  key: string;
  name: string;
  role: string;
  color: string;
}

const AGENTS: AgentMeta[] = [
  { key: "technical", name: "Technical", role: "Momentum & S/R", color: "#f59e0b" },
  { key: "quant", name: "Quantitative", role: "Z-Score & Edge", color: "#3b82f6" },
  { key: "fundamental", name: "Fundamental", role: "Valuation & Earnings", color: "#D4A240" },
  { key: "sentiment", name: "Sentiment", role: "News & Narrative", color: "#7c3aed" },
  { key: "macro", name: "Macro", role: "Yields & Central Bank", color: "hsl(var(--primary))" },
  { key: "order_flow", name: "Order Flow", role: "CVD & Microstructure", color: "#ec4899" },
  { key: "regime_change", name: "Regime", role: "Volatility & Term Structure", color: "#8b5cf6" },
  { key: "correlation", name: "Correlation", role: "Cluster Contagion", color: "#14b8a6" },
  { key: "risk_manager", name: "Risk Manager", role: "Kelly & Position Safety", color: "#22c55e" },
];

export function AgentConsensusHUD({ signal }: AgentConsensusHUDProps) {
  const [debaterOpen, setDebaterOpen] = useState(true);
  const [auditOpen, setAuditOpen] = useState(false);

  if (!signal) {
    return (
      <div className="flex flex-col h-full bg-surface-1 p-4 text-center justify-center border-l border-border/40">
        <Brain className="h-8 w-8 mx-auto text-muted-foreground/30 mb-2" />
        <div className="text-xs font-mono font-bold text-muted-foreground">SELECT A SIGNAL</div>
        <p className="text-[11px] font-mono text-muted-foreground/60 max-w-xs mx-auto mt-1">
          The 9-agent consensus brain will render directional votes, confidence weights, and debate synthesis here.
        </p>
      </div>
    );
  }

  const isNoSignal = signal.status === "NO_SIGNAL" || signal.direction === "NEUTRAL";
  const prob = signal.probability_score ?? signal.confidence_score ?? 50;
  const bullPct = isNoSignal ? 0 : signal.bullish_pct ?? prob;
  const bearPct = isNoSignal ? 0 : signal.bearish_pct ?? 100 - bullPct;

  return (
    <div className="flex flex-col h-full bg-surface-1 border-l border-border/40 overflow-hidden">
      {/* Header: Consensus Gauge */}
      <div className="p-3.5 border-b border-border/40 bg-surface-2/40">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-1.5">
            <Brain className="h-4 w-4 text-primary" />
            <span className="text-xs font-mono font-bold tracking-wider text-foreground">
              9-AGENT CONSENSUS
            </span>
          </div>
          <span
            className={cn(
              "px-2 py-0.5 rounded text-[10px] font-mono font-bold",
              isNoSignal
                ? "bg-muted text-muted-foreground border border-border"
                : signal.direction === "LONG"
                ? "bg-bull/15 text-bull border border-bull/30"
                : "bg-bear/15 text-bear border border-bear/30"
            )}
          >
            {isNoSignal ? "RESTRAINT / NO EDGE" : `${signal.direction} @ ${prob.toFixed(0)}%`}
          </span>
        </div>

        {/* Dual Bar */}
        <div className="space-y-1">
          <div className="flex items-center justify-between text-[10px] font-mono">
            <span className="text-bull font-bold">{bullPct.toFixed(0)}% BULLISH</span>
            <span className="text-bear font-bold">{bearPct.toFixed(0)}% BEARISH</span>
          </div>
          <div className="h-2 w-full bg-surface-3 rounded-full overflow-hidden flex">
            <div
              className="bg-bull/80 transition-all duration-300"
              style={{ width: `${bullPct}%` }}
            />
            <div
              className="bg-bear/80 transition-all duration-300"
              style={{ width: `${bearPct}%` }}
            />
          </div>
        </div>

        {/* Status Reasons / Restraint explanation */}
        {signal.status_reasons && signal.status_reasons.length > 0 && (
          <div className="mt-2.5 p-2 rounded border border-warn/30 bg-warn/5">
            <div className="text-[10px] font-mono font-bold text-warn mb-1 flex items-center gap-1">
              <AlertCircle className="h-3 w-3" /> PIPELINE AUDIT OBSERVATIONS
            </div>
            <div className="space-y-0.5">
              {signal.status_reasons.map((reason, i) => (
                <div key={i} className="text-[10px] font-mono text-warn/90 leading-tight">
                  • {reason}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Agents Roster */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        <div className="text-[10px] font-mono text-muted-foreground uppercase tracking-widest px-1">
          Specialist Analyst Roster
        </div>

        {AGENTS.map((agent) => {
          const voteRaw = signal.agent_votes ? signal.agent_votes[agent.key] : null;
          let direction = "ABSTAINED";
          let confidence = 0;
          let isAbstained = true;

          if (voteRaw && typeof voteRaw === "object") {
            const v = voteRaw as { direction?: string; confidence?: number; abstained?: boolean };
            if (!v.abstained && v.direction && v.direction !== "NEUTRAL") {
              direction = v.direction.toUpperCase();
              confidence = v.confidence || 0;
              isAbstained = false;
            }
          } else if (typeof voteRaw === "boolean") {
            direction = voteRaw ? "APPROVED" : "REJECTED";
            isAbstained = false;
            confidence = 100;
          }

          const isBull = direction === "LONG" || direction === "BULLISH";
          const isBear = direction === "SHORT" || direction === "BEARISH";

          return (
            <div
              key={agent.key}
              className="p-2 rounded border border-border/30 bg-surface-2/60 hover:bg-surface-2 transition-colors"
            >
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-1.5">
                  <span
                    className="h-2 w-2 rounded-full"
                    style={{ background: agent.color }}
                  />
                  <span className="text-xs font-mono font-bold text-foreground">
                    {agent.name}
                  </span>
                  <span className="text-[9px] font-mono text-muted-foreground">
                    {agent.role}
                  </span>
                </div>

                <span
                  className={cn(
                    "text-[10px] font-mono px-1.5 py-0.2 rounded font-bold",
                    isAbstained
                      ? "text-muted-foreground/70 bg-surface-3"
                      : isBull
                      ? "text-bull bg-bull/10 border border-bull/20"
                      : isBear
                      ? "text-bear bg-bear/10 border border-bear/20"
                      : "text-primary bg-primary/10"
                  )}
                >
                  {direction} {confidence > 0 && !isAbstained ? `${confidence}%` : ""}
                </span>
              </div>

              {/* Confidence Meter */}
              {!isAbstained && confidence > 0 && (
                <div className="h-1 w-full bg-surface-3 rounded-full overflow-hidden">
                  <div
                    className={cn(
                      "h-full rounded-full transition-all duration-300",
                      isBull ? "bg-bull" : isBear ? "bg-bear" : "bg-primary"
                    )}
                    style={{ width: `${confidence}%` }}
                  />
                </div>
              )}
            </div>
          );
        })}

        {/* Debater Protocol Accordion */}
        {(signal.bull_case || signal.bear_case) && (
          <div className="border border-border/40 rounded bg-surface-2/40 overflow-hidden mt-3">
            <button
              onClick={() => setDebaterOpen(!debaterOpen)}
              className="w-full flex items-center justify-between px-3 py-2 text-xs font-mono font-bold text-foreground bg-surface-2 hover:bg-surface-3 transition-colors"
            >
              <div className="flex items-center gap-1.5">
                <Scale className="h-3.5 w-3.5 text-primary" />
                <span>BULL / BEAR DEBATE AUDIT</span>
              </div>
              {debaterOpen ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
            </button>

            {debaterOpen && (
              <div className="p-3 space-y-2 border-t border-border/30 text-xs font-mono">
                {signal.bull_case && (
                  <div className="p-2 rounded border border-bull/20 bg-bull/5">
                    <div className="text-bull font-bold flex items-center gap-1 mb-0.5 text-[11px]">
                      <TrendingUp className="h-3 w-3" /> BULL CASE
                    </div>
                    <p className="text-[11px] text-foreground/80 leading-relaxed">
                      {signal.bull_case}
                    </p>
                  </div>
                )}
                {signal.bear_case && (
                  <div className="p-2 rounded border border-bear/20 bg-bear/5">
                    <div className="text-bear font-bold flex items-center gap-1 mb-0.5 text-[11px]">
                      <TrendingDown className="h-3 w-3" /> BEAR CASE
                    </div>
                    <p className="text-[11px] text-foreground/80 leading-relaxed">
                      {signal.bear_case}
                    </p>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Pipeline Reasoning Chain Accordion */}
        {signal.reasoning_chain && signal.reasoning_chain.length > 0 && (
          <div className="border border-border/40 rounded bg-surface-2/40 overflow-hidden">
            <button
              onClick={() => setAuditOpen(!auditOpen)}
              className="w-full flex items-center justify-between px-3 py-2 text-xs font-mono font-bold text-foreground bg-surface-2 hover:bg-surface-3 transition-colors"
            >
              <div className="flex items-center gap-1.5">
                <Zap className="h-3.5 w-3.5 text-primary" />
                <span>EXECUTION REASONING CHAIN ({signal.reasoning_chain.length})</span>
              </div>
              {auditOpen ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
            </button>

            {auditOpen && (
              <div className="p-3 space-y-1.5 border-t border-border/30 text-[11px] font-mono text-muted-foreground">
                {signal.reasoning_chain.map((step, i) => (
                  <div key={i} className="flex items-start gap-1.5 leading-relaxed">
                    <span className="text-primary font-bold">{i + 1}.</span>
                    <span>{step}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
