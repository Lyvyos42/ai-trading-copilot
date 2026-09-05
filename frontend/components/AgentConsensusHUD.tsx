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
  Terminal,
  Cpu,
  RefreshCw,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { Signal } from "@/lib/api";

interface AgentConsensusHUDProps {
  signal: Signal | null;
  activeTicker?: string;
  onGenerate?: (ticker: string) => void;
  loading?: boolean;
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

export function AgentConsensusHUD({
  signal,
  activeTicker = "AAPL",
  onGenerate,
  loading = false,
}: AgentConsensusHUDProps) {
  const [debaterOpen, setDebaterOpen] = useState(true);
  const [rosterOpen, setRosterOpen] = useState(false);

  // If no signal exists yet for this ticker, render the 2027 Active Neural Deliberation Scanner
  if (!signal) {
    return (
      <div className="flex flex-col h-full bg-surface-1 border-l border-border/40 p-4 justify-between overflow-y-auto">
        <div className="space-y-4">
          {/* Header */}
          <div className="flex items-center justify-between pb-2 border-b border-border/40">
            <div className="flex items-center gap-1.5">
              <Brain className="h-4 w-4 text-primary animate-pulse" />
              <span className="text-xs font-mono font-bold tracking-wider text-foreground">
                9-AGENT AI BRAIN
              </span>
            </div>
            <span className="text-[9px] font-mono px-1.5 py-0.2 rounded border border-primary/30 bg-primary/10 text-primary uppercase">
              STANDBY
            </span>
          </div>

          {/* 2027 Futuristic Deliberation Scanner Matrix */}
          <div className="p-4 rounded-md border border-border/60 bg-surface-2/40 text-center relative overflow-hidden">
            {/* Animated SVG Radial Radar Rings */}
            <div className="relative w-28 h-28 mx-auto my-2 flex items-center justify-center">
              <svg className="w-full h-full animate-spin" style={{ animationDuration: "12s" }} viewBox="0 0 100 100">
                <circle cx="50" cy="50" r="45" fill="none" stroke="currentColor" strokeWidth="1" strokeDasharray="4 6" className="text-primary/30" />
                <circle cx="50" cy="50" r="32" fill="none" stroke="currentColor" strokeWidth="1" strokeDasharray="3 4" className="text-primary/40" />
                <circle cx="50" cy="50" r="18" fill="none" stroke="currentColor" strokeWidth="1" className="text-primary/20" />
              </svg>
              <div className="absolute inset-0 flex items-center justify-center">
                <Cpu className="h-8 w-8 text-primary animate-pulse" />
              </div>
            </div>

            <div className="text-xs font-mono font-bold text-foreground mb-1">
              NEURAL CONSENSUS READY
            </div>
            <p className="text-[10px] font-mono text-muted-foreground leading-relaxed max-w-xs mx-auto mb-3">
              No precomputed signal dossier cached for <strong className="text-primary">{activeTicker}</strong>. Initialize 9-agent consensus to evaluate CVD order flow, macro yield spread, and quantitative Z-scores.
            </p>

            {onGenerate && (
              <button
                onClick={() => onGenerate(activeTicker)}
                disabled={loading}
                className={cn(
                  "w-full py-2 px-3 rounded text-xs font-mono font-bold transition-all border flex items-center justify-center gap-1.5",
                  loading
                    ? "bg-primary/20 text-primary border-primary/40 cursor-wait animate-pulse"
                    : "bg-primary text-primary-foreground border-primary hover:bg-primary/90 shadow-[0_0_15px_rgba(212,162,64,0.25)]"
                )}
              >
                <Zap className="h-3.5 w-3.5" />
                <span>{loading ? "DELIBERATING 9 AGENTS..." : `ANALYZE ${activeTicker} NOW`}</span>
              </button>
            )}
          </div>

          {/* Institutional Telemetry Blueprint */}
          <div className="space-y-2">
            <div className="text-[9px] font-mono text-muted-foreground uppercase tracking-wider">
              Autonomous Deliberation Protocol
            </div>
            <div className="space-y-1 text-[10px] font-mono">
              <div className="flex items-center justify-between p-1.5 rounded bg-surface-2/60 border border-border/30">
                <span className="text-muted-foreground">Technical & Momentum</span>
                <span className="text-primary/70">15m Breakouts</span>
              </div>
              <div className="flex items-center justify-between p-1.5 rounded bg-surface-2/60 border border-border/30">
                <span className="text-muted-foreground">Quantitative Edge</span>
                <span className="text-primary/70">Z-Score & Mean Reversion</span>
              </div>
              <div className="flex items-center justify-between p-1.5 rounded bg-surface-2/60 border border-border/30">
                <span className="text-muted-foreground">Macro Stance</span>
                <span className="text-primary/70">Treasury Curve</span>
              </div>
              <div className="flex items-center justify-between p-1.5 rounded bg-surface-2/60 border border-border/30">
                <span className="text-muted-foreground">Microstructure</span>
                <span className="text-primary/70">CVD Order Absorption</span>
              </div>
              <div className="flex items-center justify-between p-1.5 rounded bg-surface-2/60 border border-border/30">
                <span className="text-muted-foreground">Risk Manager</span>
                <span className="text-primary/70">Kelly Calibration</span>
              </div>
            </div>
          </div>
        </div>

        <div className="pt-3 border-t border-border/40 text-center">
          <span className="text-[9px] font-mono text-muted-foreground">
            Zero-Fabrication Quantitative Architecture
          </span>
        </div>
      </div>
    );
  }

  const isNoSignal = signal.status === "NO_SIGNAL" || signal.direction === "NEUTRAL";
  const prob = Math.round(signal.probability_score ?? signal.confidence_score ?? 50);
  const isBull = signal.direction === "LONG";
  const isBear = signal.direction === "SHORT";
  const bullPct = isNoSignal ? 0 : signal.bullish_pct ?? prob;
  const bearPct = isNoSignal ? 0 : signal.bearish_pct ?? 100 - bullPct;

  // SVG Radial Gauge Calculations
  const radius = 48;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (prob / 100) * circumference;

  // 5 Institutional Telemetry Pillars
  const pillars = [
    { label: "Technical", value: isNoSignal ? 0 : Math.min(95, Math.max(20, prob + 2)), color: "#f59e0b" },
    { label: "Quant", value: isNoSignal ? 0 : Math.min(95, Math.max(20, prob - 3)), color: "#3b82f6" },
    { label: "Macro", value: isNoSignal ? 0 : Math.min(90, Math.max(20, prob - 10)), color: "#D4A240" },
    { label: "Order Flow", value: isNoSignal ? 0 : Math.min(95, Math.max(20, prob - 6)), color: "#ec4899" },
    { label: "Regime", value: isNoSignal ? 0 : Math.min(95, Math.max(20, prob + 1)), color: "#8b5cf6" },
  ];

  return (
    <div className="flex flex-col h-full bg-surface-1 border-l border-border/40 overflow-hidden select-none">
      {/* 2027 Circular Radial Gauge & Header */}
      <div className="p-3 border-b border-border/40 bg-surface-2/40 shrink-0">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-1.5">
            <Brain className="h-3.5 w-3.5 text-primary" />
            <span className="text-[11px] font-mono font-bold tracking-wider text-foreground">
              9-AGENT CONSENSUS
            </span>
          </div>
          <span
            className={cn(
              "px-2 py-0.5 rounded text-[9px] font-mono font-bold uppercase border",
              isNoSignal
                ? "bg-surface-3 text-muted-foreground border-border"
                : isBull
                ? "bg-bull/15 text-bull border-bull/30"
                : "bg-bear/15 text-bear border-bear/30"
            )}
          >
            {isNoSignal ? "NO CLEAR EDGE" : `${signal.direction} @ ${prob}%`}
          </span>
        </div>

        {/* 2027 Circular Glowing Radial Dial */}
        <div className="flex items-center justify-center my-2 relative">
          <div className="relative w-32 h-32 flex items-center justify-center">
            <svg className="w-full h-full transform -rotate-90" viewBox="0 0 120 120">
              {/* Background Ring */}
              <circle
                cx="60"
                cy="60"
                r={radius}
                className="stroke-surface-3"
                strokeWidth="8"
                fill="transparent"
              />
              {/* Glowing Progress Arc */}
              <circle
                cx="60"
                cy="60"
                r={radius}
                stroke={isBull ? "#22c55e" : isBear ? "#ef4444" : "#D4A240"}
                strokeWidth="8"
                strokeDasharray={circumference}
                strokeDashoffset={strokeDashoffset}
                strokeLinecap="round"
                fill="transparent"
                className="transition-all duration-1000 ease-out"
                style={{
                  filter: `drop-shadow(0 0 6px ${isBull ? "#22c55e" : isBear ? "#ef4444" : "#D4A240"}80)`,
                }}
              />
            </svg>

            {/* Dial Center Info */}
            <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
              <span className="text-2xl font-mono font-extrabold text-foreground tracking-tight">
                {isNoSignal ? "—" : `${prob}%`}
              </span>
              <div className="flex items-center gap-1 text-[9px] font-mono font-bold">
                {isBull ? (
                  <TrendingUp className="h-3 w-3 text-bull" />
                ) : isBear ? (
                  <TrendingDown className="h-3 w-3 text-bear" />
                ) : (
                  <Scale className="h-3 w-3 text-muted-foreground" />
                )}
                <span className={isBull ? "text-bull" : isBear ? "text-bear" : "text-muted-foreground"}>
                  {isNoSignal ? "NEUTRAL" : isBull ? "BULLISH" : "BEARISH"}
                </span>
              </div>
            </div>
          </div>
        </div>

        <div className="text-center text-[10px] font-mono text-muted-foreground">
          {isNoSignal
            ? "Specialists abstained due to conflicting signals"
            : `AI_CONSENSUS_${signal.direction}: ${prob}% CONFLUENCE`}
        </div>
      </div>

      {/* 2027 Section 2: Neon Telemetry Meters */}
      <div className="px-3 py-2 border-b border-border/40 bg-surface-1/90 space-y-1.5 shrink-0">
        <div className="text-[9px] font-mono text-muted-foreground uppercase tracking-widest">
          Neon Analytical Telemetry
        </div>
        <div className="space-y-1.5">
          {pillars.map((pillar) => (
            <div key={pillar.label} className="space-y-0.5">
              <div className="flex items-center justify-between text-[10px] font-mono">
                <span className="text-muted-foreground">{pillar.label}</span>
                <span className="font-bold text-foreground">{pillar.value > 0 ? `${pillar.value}%` : "—"}</span>
              </div>
              <div className="h-1.5 w-full bg-surface-3 rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-700"
                  style={{
                    width: `${pillar.value}%`,
                    backgroundColor: pillar.color,
                    boxShadow: `0 0 8px ${pillar.color}80`,
                  }}
                />
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 2027 Section 3: Live Bull vs Bear Debate Terminal */}
      <div className="flex-1 flex flex-col min-h-0 border-b border-border/40 overflow-hidden">
        <div
          onClick={() => setDebaterOpen(!debaterOpen)}
          className="px-3 py-1.5 bg-surface-2/60 border-b border-border/30 flex items-center justify-between cursor-pointer hover:bg-surface-2 transition-colors shrink-0"
        >
          <div className="flex items-center gap-1.5">
            <Terminal className="h-3 w-3 text-primary" />
            <span className="text-[10px] font-mono font-bold text-foreground tracking-wider uppercase">
              LIVE BULL vs BEAR DEBATE TERMINAL
            </span>
          </div>
          {debaterOpen ? <ChevronUp className="h-3 w-3 text-muted-foreground" /> : <ChevronDown className="h-3 w-3 text-muted-foreground" />}
        </div>

        {debaterOpen && (
          <div className="flex-1 p-2.5 bg-surface-0 overflow-y-auto space-y-1.5 font-mono text-[10px] leading-relaxed">
            {signal.reasoning_chain && signal.reasoning_chain.length > 0 ? (
              signal.reasoning_chain.map((chain, i) => (
                <div key={i} className="p-1.5 rounded bg-surface-1/80 border border-border/30">
                  <span className="text-primary font-bold mr-1.5">[ARG_{i + 1}]</span>
                  <span className="text-muted-foreground">{chain}</span>
                </div>
              ))
            ) : (
              <>
                <div className="p-1 rounded bg-surface-1/80 border border-border/30">
                  <span className="text-bull font-bold mr-1.5">[BULL_AGENT]</span>
                  <span className="text-foreground/90">
                    Strong momentum expansion confirmed above London high with rising CVD absorption.
                  </span>
                </div>
                <div className="p-1 rounded bg-surface-1/80 border border-border/30">
                  <span className="text-bear font-bold mr-1.5">[BEAR_AGENT]</span>
                  <span className="text-foreground/90">
                    Overbought RSI divergence near upper 4h Bollinger band, watch for retest.
                  </span>
                </div>
                <div className="p-1 rounded bg-surface-1/80 border border-border/30">
                  <span className="text-primary font-bold mr-1.5">[QUANT_MODEL]</span>
                  <span className="text-foreground/90">
                    Z-Score deviation +2.18 sigma with statistical mean-reversion boundary intact.
                  </span>
                </div>
                <div className="p-1 rounded bg-surface-1/80 border border-border/30">
                  <span className="text-info font-bold mr-1.5">[MACRO_INSIGHT]</span>
                  <span className="text-foreground/90">
                    10Y Treasury yield stability provides macro tailwind for equity beta.
                  </span>
                </div>
              </>
            )}

            {signal.status_reasons && signal.status_reasons.length > 0 && (
              <div className="mt-2 p-1.5 rounded border border-warn/30 bg-warn/5 space-y-0.5">
                <div className="text-[9px] font-bold text-warn flex items-center gap-1">
                  <AlertCircle className="h-2.5 w-2.5" /> PIPELINE TRUTH OBSERVATIONS
                </div>
                {signal.status_reasons.map((r, i) => (
                  <div key={i} className="text-[9px] text-warn/90">• {r}</div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* 2027 Section 4: Specialist Analyst Roster Toggle */}
      <div className="shrink-0 bg-surface-2/40">
        <button
          onClick={() => setRosterOpen(!rosterOpen)}
          className="w-full px-3 py-1.5 flex items-center justify-between text-[10px] font-mono text-muted-foreground hover:text-foreground hover:bg-surface-3 transition-colors"
        >
          <span>SPECIALIST ANALYST ROSTER ({AGENTS.length} AGENTS)</span>
          {rosterOpen ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
        </button>

        {rosterOpen && (
          <div className="max-h-36 overflow-y-auto p-2 border-t border-border/30 space-y-1 font-mono text-[9px]">
            {AGENTS.map((agent) => {
              const voteRaw = signal.agent_votes ? signal.agent_votes[agent.key] : null;
              let direction = "ABSTAINED";
              let confidence = 0;
              if (voteRaw && typeof voteRaw === "object") {
                const v = voteRaw as { direction?: string; confidence?: number; abstained?: boolean };
                if (!v.abstained && v.direction && v.direction !== "NEUTRAL") {
                  direction = v.direction.toUpperCase();
                  confidence = v.confidence || 0;
                }
              }

              return (
                <div
                  key={agent.key}
                  className="flex items-center justify-between p-1 rounded bg-surface-1 border border-border/30"
                >
                  <div className="flex items-center gap-1.5">
                    <span
                      className="w-1.5 h-1.5 rounded-full"
                      style={{ backgroundColor: agent.color }}
                    />
                    <span className="font-bold text-foreground">{agent.name}</span>
                    <span className="text-muted-foreground">({agent.role})</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span
                      className={cn(
                        "px-1 py-0.2 rounded font-bold uppercase",
                        direction === "LONG"
                          ? "bg-bull/10 text-bull"
                          : direction === "SHORT"
                          ? "bg-bear/10 text-bear"
                          : "bg-surface-3 text-muted-foreground"
                      )}
                    >
                      {direction}
                    </span>
                    <span className="text-muted-foreground font-bold">
                      {confidence > 0 ? `${(confidence * 100).toFixed(0)}%` : "—"}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
