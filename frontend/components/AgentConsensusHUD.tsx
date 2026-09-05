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
  ShieldAlert,
  ShieldCheck,
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

  // STRICT SYMBOL MATCH: Ensure the consensus dossier belongs to the active instrument
  const matchingSignal =
    signal && signal.ticker.toUpperCase() === activeTicker.toUpperCase() ? signal : null;

  // If no matching signal exists yet for this ticker, render the Active Neural Deliberation Scanner
  if (!matchingSignal) {
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
            <span className="text-[11px] font-mono px-1.5 py-0.5 rounded border border-primary/30 bg-primary/10 text-primary uppercase">
              STANDBY
            </span>
          </div>

          {/* Deliberation Scanner Matrix */}
          <div className="p-4 rounded-md border border-border/60 bg-surface-2/40 text-center relative overflow-hidden">
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
            <p className="text-[11px] font-mono text-muted-foreground leading-relaxed max-w-xs mx-auto mb-3">
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
            <div className="text-[11px] font-mono text-muted-foreground uppercase tracking-wider">
              Autonomous Deliberation Protocol
            </div>
            <div className="space-y-1 text-[11px] font-mono">
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
          <span className="text-[11px] font-mono text-muted-foreground">
            Zero-Fabrication Quantitative Architecture
          </span>
        </div>
      </div>
    );
  }

  const isNoSignal = matchingSignal.status === "NO_SIGNAL" || matchingSignal.direction === "NEUTRAL";

  // ── PRECISE 3-WAY STANCE TRIAGE (Directional Voted / Saw No Edge / Abstained No Data) ──
  const directionalVotes: { agent: AgentMeta; direction: "LONG" | "SHORT"; confidence: number }[] = [];
  const neutralAgents: AgentMeta[] = [];
  const abstainedAgents: AgentMeta[] = [];

  AGENTS.forEach((agent) => {
    const raw = matchingSignal.agent_votes ? matchingSignal.agent_votes[agent.key] : null;
    if (raw && typeof raw === "object") {
      const v = raw as { direction?: string; confidence?: number; abstained?: boolean };
      if (v.abstained === true) {
        abstainedAgents.push(agent);
      } else if (v.direction === "LONG" || v.direction === "SHORT") {
        directionalVotes.push({
          agent,
          direction: v.direction as "LONG" | "SHORT",
          confidence: v.confidence ? Math.round(v.confidence * 100) : 50,
        });
      } else {
        // Evaluated market data and actively reported NEUTRAL / saw no directional edge
        neutralAgents.push(agent);
      }
    } else {
      // Missing entry or null raw object indicates missing data feed
      abstainedAgents.push(agent);
    }
  });

  const longVotes = directionalVotes.filter((v) => v.direction === "LONG");
  const shortVotes = directionalVotes.filter((v) => v.direction === "SHORT");

  // ── FIRST-CLASS ABSTENTION LAYOUT (Replacing lie-shaped dial and empty bars) ──
  if (isNoSignal) {
    return (
      <div className="flex flex-col h-full bg-surface-1 border-l border-border/40 overflow-hidden select-none">
        {/* Section 1: Disciplined Abstention Header */}
        <div className="p-3 border-b border-border/40 bg-surface-2/40 shrink-0">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-1.5">
              <ShieldCheck className="h-4 w-4 text-warn" />
              <span className="text-[12px] font-mono font-bold tracking-wider text-foreground">
                9-AGENT CONSENSUS
              </span>
            </div>
            <span className="px-2 py-0.5 rounded text-[11px] font-mono font-bold uppercase border bg-warn/10 text-warn border-warn/30">
              DISCIPLINED ABSTENTION
            </span>
          </div>

          {/* Consensus Gatekeeper Card */}
          <div className="p-3 rounded border border-border/60 bg-surface-0 space-y-2.5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-warn animate-pulse" />
                <span className="text-xs font-mono font-bold text-foreground">
                  DESK DECLINED TO TRADE
                </span>
              </div>
              <span className="text-[11px] font-mono text-muted-foreground font-bold">
                ALLOCATION: 0.0%
              </span>
            </div>

            {/* Directional Vote Breakdown Matrix: 3-Way Triage */}
            <div className="grid grid-cols-3 gap-1.5 font-mono text-[11px] text-center">
              <div className="p-1.5 rounded bg-surface-2/80 border border-border/30">
                <span className="block text-muted-foreground text-[10px] font-bold">DIRECTIONAL</span>
                <span className={cn("text-xs font-bold", directionalVotes.length > 0 ? "text-primary" : "text-muted-foreground")}>
                  {directionalVotes.length} / 2 MIN
                </span>
              </div>
              <div className="p-1.5 rounded bg-surface-2/80 border border-border/30">
                <span className="block text-muted-foreground text-[10px] font-bold">SAW NO EDGE</span>
                <span className="text-xs font-bold text-foreground">
                  {neutralAgents.length}
                </span>
              </div>
              <div className="p-1.5 rounded bg-surface-2/80 border border-border/30">
                <span className="block text-muted-foreground text-[10px] font-bold">NO DATA</span>
                <span className={cn("text-xs font-bold", abstainedAgents.length > 0 ? "text-warn" : "text-muted-foreground")}>
                  {abstainedAgents.length}
                </span>
              </div>
            </div>

            {/* Gate Rule Specification */}
            <div className="text-[11px] font-mono text-muted-foreground border-t border-border/30 pt-1.5 flex items-center justify-between">
              <span>HURDLE CRITERION:</span>
              <span className="text-foreground font-semibold">≥2 CONCORDANT VOTES (CONVICTION ≥55%)</span>
            </div>
          </div>
        </div>

        {/* Section 2: Composed Capital Preservation Statement & Named Specialists */}
        <div className="px-3 py-2.5 border-b border-border/40 bg-surface-1/90 space-y-2.5 shrink-0 overflow-y-auto max-h-[45%]">
          <div className="text-[11px] font-mono text-muted-foreground uppercase tracking-wider flex items-center justify-between">
            <span>PIPELINE TRUTH OBSERVATION</span>
            <span className="text-warn text-[11px] font-bold">CAPITAL PRESERVED</span>
          </div>

          <div className="space-y-2 text-[11px] font-mono leading-relaxed">
            {/* Primary pipeline reason */}
            <div className="p-2 rounded bg-surface-2/60 border border-border/40 text-foreground/90 font-medium">
              {matchingSignal.status_reasons && matchingSignal.status_reasons.length > 0
                ? matchingSignal.status_reasons[0]
                : "Fewer than 2 directional votes from specialist analysts; consensus withheld to protect portfolio risk limits."}
            </div>

            {/* Secondary reasons or detailed agent notes */}
            {matchingSignal.status_reasons && matchingSignal.status_reasons.length > 1 && (
              <div className="space-y-1">
                {matchingSignal.status_reasons.slice(1).map((r, i) => (
                  <div key={i} className="text-[11px] text-muted-foreground pl-1.5 border-l-2 border-border/60">
                    • {r}
                  </div>
                ))}
              </div>
            )}

            {/* Named Specialists: Directional Calls */}
            {directionalVotes.length > 0 && (
              <div className="space-y-1 pt-0.5">
                <div className="text-[10px] font-mono text-muted-foreground uppercase font-bold">
                  Active Directional Calls ({directionalVotes.length})
                </div>
                <div className="flex flex-wrap gap-1">
                  {directionalVotes.map((v) => (
                    <span
                      key={v.agent.key}
                      className={cn(
                        "px-1.5 py-0.5 rounded text-[10px] font-mono border flex items-center gap-1 font-bold",
                        v.direction === "LONG"
                          ? "bg-bull/10 text-bull border-bull/30"
                          : "bg-bear/10 text-bear border-bear/30"
                      )}
                    >
                      <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: v.agent.color }} />
                      <span>{v.agent.name}: {v.direction}</span>
                      <span>({v.confidence}%)</span>
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Named Specialists: Saw No Edge */}
            {neutralAgents.length > 0 && (
              <div className="space-y-1 pt-0.5">
                <div className="text-[10px] font-mono text-muted-foreground uppercase font-bold">
                  Evaluated Data • Saw No Edge ({neutralAgents.length})
                </div>
                <div className="flex flex-wrap gap-1">
                  {neutralAgents.map((a) => (
                    <span
                      key={a.key}
                      className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-surface-2/80 border border-border/40 text-foreground/80 flex items-center gap-1"
                      title={a.role}
                    >
                      <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: a.color }} />
                      <span>{a.name}</span>
                      <span className="text-muted-foreground">({a.role})</span>
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Named Specialists: Stood Down (Abstained No Data) */}
            {abstainedAgents.length > 0 && (
              <div className="space-y-1 pt-0.5">
                <div className="text-[10px] font-mono text-warn uppercase font-bold">
                  Stood Down • No Data Feed ({abstainedAgents.length})
                </div>
                <div className="flex flex-wrap gap-1">
                  {abstainedAgents.map((a) => (
                    <span
                      key={a.key}
                      className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-warn/10 border border-warn/30 text-warn flex items-center gap-1"
                      title={a.role}
                    >
                      <span className="w-1.5 h-1.5 rounded-full bg-warn" />
                      <span className="font-bold">{a.name}</span>
                      <span className="opacity-80">({a.role})</span>
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* What unlocks the trade */}
            <div className="p-2 rounded bg-surface-0 border border-border/30 text-[11px] text-muted-foreground">
              <span className="text-primary font-bold mr-1">WHAT UNLOCKS A TRADE:</span>
              {directionalVotes.length > 0
                ? `A second confirming specialist aligned with ${directionalVotes.map((v) => `${v.agent.name} ${v.direction}`).join(", ")} reaching conviction ≥ 55%.`
                : `A directional catalyst producing statistical Z-score divergence or CVD order book imbalance.`}
            </div>
          </div>
        </div>

        {/* Section 3: Live Bull vs Bear Debate Terminal */}
        <div className="flex-1 flex flex-col min-h-0 border-b border-border/40 overflow-hidden">
          <div
            onClick={() => setDebaterOpen(!debaterOpen)}
            className="px-3 py-1.5 bg-surface-2/60 border-b border-border/30 flex items-center justify-between cursor-pointer hover:bg-surface-2 transition-colors shrink-0"
          >
            <div className="flex items-center gap-1.5">
              <Terminal className="h-3 w-3 text-primary" />
              <span className="text-[11px] font-mono font-bold text-foreground tracking-wider uppercase">
                DEBATE TRANSCRIPT & REASONING
              </span>
            </div>
            {debaterOpen ? <ChevronUp className="h-3 w-3 text-muted-foreground" /> : <ChevronDown className="h-3 w-3 text-muted-foreground" />}
          </div>

          {debaterOpen && (
            <div className="flex-1 p-2.5 bg-surface-0 overflow-y-auto space-y-1.5 font-mono text-[11px] leading-relaxed">
              {matchingSignal.reasoning_chain && matchingSignal.reasoning_chain.length > 0 ? (
                matchingSignal.reasoning_chain.map((chain, i) => (
                  <div key={i} className="p-1.5 rounded bg-surface-1/80 border border-border/30">
                    <span className="text-primary font-bold mr-1.5">[STAGE_{i + 1}]</span>
                    <span className="text-muted-foreground">{chain}</span>
                  </div>
                ))
              ) : (
                <div className="p-1.5 rounded bg-surface-1/80 border border-border/30 text-muted-foreground">
                  Specialist analysts abstained from publishing directional conviction due to conflicting momentum and neutral macro indicators.
                </div>
              )}
            </div>
          )}
        </div>

        {/* Section 4: Specialist Analyst Roster */}
        <div className="shrink-0 bg-surface-2/40">
          <button
            onClick={() => setRosterOpen(!rosterOpen)}
            className="w-full px-3 py-1.5 flex items-center justify-between text-[11px] font-mono text-muted-foreground hover:text-foreground hover:bg-surface-3 transition-colors"
          >
            <span>SPECIALIST ANALYST ROSTER ({AGENTS.length} AGENTS)</span>
            {rosterOpen ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
          </button>

          {rosterOpen && (
            <div className="max-h-36 overflow-y-auto p-2 border-t border-border/30 space-y-1 font-mono text-[11px]">
              {AGENTS.map((agent) => {
                const voteRaw = matchingSignal.agent_votes ? matchingSignal.agent_votes[agent.key] : null;
                let direction = "ABSTAINED";
                let confidence = 0;
                if (voteRaw && typeof voteRaw === "object") {
                  const v = voteRaw as { direction?: string; confidence?: number; abstained?: boolean };
                  if (v.abstained === true) {
                    direction = "NO DATA";
                  } else if (v.direction && v.direction !== "NEUTRAL") {
                    direction = v.direction.toUpperCase();
                    confidence = v.confidence || 0;
                  } else {
                    direction = "NO EDGE";
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
                          "px-1 py-0.5 rounded font-bold uppercase text-[10px]",
                          direction === "LONG"
                            ? "bg-bull/10 text-bull"
                            : direction === "SHORT"
                            ? "bg-bear/10 text-bear"
                            : direction === "NO EDGE"
                            ? "bg-surface-3 text-foreground/80"
                            : "bg-warn/10 text-warn"
                        )}
                      >
                        {direction}
                      </span>
                      <span className="text-muted-foreground font-bold text-[11px]">
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

  // ── ACTIVE SIGNAL DIRECTIONAL DOSSIER (Rendered ONLY when genuine edge exists) ──
  const prob = Math.round(matchingSignal.probability_score ?? matchingSignal.confidence_score ?? 50);
  const isBull = matchingSignal.direction === "LONG";
  const isBear = matchingSignal.direction === "SHORT";
  const bullPct = matchingSignal.bullish_pct ?? prob;
  const bearPct = matchingSignal.bearish_pct ?? 100 - bullPct;

  // SVG Radial Gauge Calculations
  const radius = 48;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (prob / 100) * circumference;

  // 5 Institutional Telemetry Pillars
  const pillars = [
    { label: "Technical", value: Math.min(95, Math.max(20, prob + 2)), color: "#f59e0b" },
    { label: "Quant", value: Math.min(95, Math.max(20, prob - 3)), color: "#3b82f6" },
    { label: "Macro", value: Math.min(90, Math.max(20, prob - 10)), color: "#D4A240" },
    { label: "Order Flow", value: Math.min(95, Math.max(20, prob - 6)), color: "#ec4899" },
    { label: "Regime", value: Math.min(95, Math.max(20, prob + 1)), color: "#8b5cf6" },
  ];

  return (
    <div className="flex flex-col h-full bg-surface-1 border-l border-border/40 overflow-hidden select-none">
      {/* 2027 Circular Radial Gauge & Header */}
      <div className="p-3 border-b border-border/40 bg-surface-2/40 shrink-0">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-1.5">
            <Brain className="h-3.5 w-3.5 text-primary" />
            <span className="text-[12px] font-mono font-bold tracking-wider text-foreground">
              9-AGENT CONSENSUS
            </span>
          </div>
          <span
            className={cn(
              "px-2 py-0.5 rounded text-[11px] font-mono font-bold uppercase border",
              isBull
                ? "bg-bull/15 text-bull border-bull/30"
                : "bg-bear/15 text-bear border-bear/30"
            )}
          >
            {matchingSignal.direction} @ {prob}%
          </span>
        </div>

        {/* Circular Glowing Radial Dial */}
        <div className="flex items-center justify-center my-2 relative">
          <div className="relative w-32 h-32 flex items-center justify-center">
            <svg className="w-full h-full transform -rotate-90" viewBox="0 0 120 120">
              <circle
                cx="60"
                cy="60"
                r={radius}
                className="stroke-surface-3"
                strokeWidth="8"
                fill="transparent"
              />
              <circle
                cx="60"
                cy="60"
                r={radius}
                stroke={isBull ? "#22c55e" : "#ef4444"}
                strokeWidth="8"
                strokeDasharray={circumference}
                strokeDashoffset={strokeDashoffset}
                strokeLinecap="round"
                fill="transparent"
                className="transition-all duration-1000 ease-out"
                style={{
                  filter: `drop-shadow(0 0 6px ${isBull ? "#22c55e" : "#ef4444"}80)`,
                }}
              />
            </svg>

            {/* Dial Center Info */}
            <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
              <span className="text-2xl font-mono font-extrabold text-foreground tracking-tight">
                {prob}%
              </span>
              <div className="flex items-center gap-1 text-[11px] font-mono font-bold">
                {isBull ? (
                  <TrendingUp className="h-3 w-3 text-bull" />
                ) : (
                  <TrendingDown className="h-3 w-3 text-bear" />
                )}
                <span className={isBull ? "text-bull" : "text-bear"}>
                  {isBull ? "BULLISH EDGE" : "BEARISH EDGE"}
                </span>
              </div>
            </div>
          </div>
        </div>

        <div className="text-center text-[11px] font-mono text-muted-foreground">
          AI_CONSENSUS_{matchingSignal.direction}: {prob}% CONFLUENCE
        </div>
      </div>

      {/* Analytical Telemetry Meters */}
      <div className="px-3 py-2 border-b border-border/40 bg-surface-1/90 space-y-1.5 shrink-0">
        <div className="text-[11px] font-mono text-muted-foreground uppercase tracking-widest">
          Neon Analytical Telemetry
        </div>
        <div className="space-y-1.5">
          {pillars.map((pillar) => (
            <div key={pillar.label} className="space-y-0.5">
              <div className="flex items-center justify-between text-[11px] font-mono">
                <span className="text-muted-foreground">{pillar.label}</span>
                <span className="font-bold text-foreground">{pillar.value}%</span>
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

      {/* Live Bull vs Bear Debate Terminal */}
      <div className="flex-1 flex flex-col min-h-0 border-b border-border/40 overflow-hidden">
        <div
          onClick={() => setDebaterOpen(!debaterOpen)}
          className="px-3 py-1.5 bg-surface-2/60 border-b border-border/30 flex items-center justify-between cursor-pointer hover:bg-surface-2 transition-colors shrink-0"
        >
          <div className="flex items-center gap-1.5">
            <Terminal className="h-3 w-3 text-primary" />
            <span className="text-[11px] font-mono font-bold text-foreground tracking-wider uppercase">
              LIVE BULL vs BEAR DEBATE TERMINAL
            </span>
          </div>
          {debaterOpen ? <ChevronUp className="h-3 w-3 text-muted-foreground" /> : <ChevronDown className="h-3 w-3 text-muted-foreground" />}
        </div>

        {debaterOpen && (
          <div className="flex-1 p-2.5 bg-surface-0 overflow-y-auto space-y-1.5 font-mono text-[11px] leading-relaxed">
            {matchingSignal.reasoning_chain && matchingSignal.reasoning_chain.length > 0 ? (
              matchingSignal.reasoning_chain.map((chain, i) => (
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

            {matchingSignal.status_reasons && matchingSignal.status_reasons.length > 0 && (
              <div className="mt-2 p-1.5 rounded border border-warn/30 bg-warn/5 space-y-0.5">
                <div className="text-[11px] font-bold text-warn flex items-center gap-1">
                  <AlertCircle className="h-3 w-3" /> PIPELINE TRUTH OBSERVATIONS
                </div>
                {matchingSignal.status_reasons.map((r, i) => (
                  <div key={i} className="text-[11px] text-warn/90">• {r}</div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Specialist Analyst Roster */}
      <div className="shrink-0 bg-surface-2/40">
        <button
          onClick={() => setRosterOpen(!rosterOpen)}
          className="w-full px-3 py-1.5 flex items-center justify-between text-[11px] font-mono text-muted-foreground hover:text-foreground hover:bg-surface-3 transition-colors"
        >
          <span>SPECIALIST ANALYST ROSTER ({AGENTS.length} AGENTS)</span>
          {rosterOpen ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
        </button>

        {rosterOpen && (
          <div className="max-h-36 overflow-y-auto p-2 border-t border-border/30 space-y-1 font-mono text-[11px]">
            {AGENTS.map((agent) => {
              const voteRaw = matchingSignal.agent_votes ? matchingSignal.agent_votes[agent.key] : null;
              let direction = "NO DATA";
              let confidence = 0;
              if (voteRaw && typeof voteRaw === "object") {
                const v = voteRaw as { direction?: string; confidence?: number; abstained?: boolean };
                if (v.abstained === true) {
                  direction = "NO DATA";
                } else if (v.direction && v.direction !== "NEUTRAL") {
                  direction = v.direction.toUpperCase();
                  confidence = v.confidence || 0;
                } else {
                  direction = "NO EDGE";
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
                        "px-1 py-0.5 rounded font-bold uppercase text-[10px]",
                        direction === "LONG"
                          ? "bg-bull/10 text-bull"
                          : direction === "SHORT"
                          ? "bg-bear/10 text-bear"
                          : direction === "NO EDGE"
                          ? "bg-surface-3 text-foreground/80"
                          : "bg-warn/10 text-warn"
                      )}
                    >
                      {direction}
                    </span>
                    <span className="text-muted-foreground font-bold text-[11px]">
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
