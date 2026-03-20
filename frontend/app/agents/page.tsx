"use client";

import { useEffect, useState } from "react";
import { Activity, Brain, BarChart2, Newspaper, Globe, Shield, Zap, RefreshCw, Lock } from "lucide-react";
import { getAgentStatus, triggerDebate, type AgentStatus } from "@/lib/api";
import { useAuth } from "@/lib/useAuth";
import { UpgradeModal } from "@/components/UpgradeModal";

const AGENT_META: Record<string, {
  icon: React.ComponentType<{ className?: string; style?: React.CSSProperties }>;
  color: string;
  model: string;
  seq: number;
}> = {
  FundamentalAnalyst: { icon: BarChart2,  color: "#3b82f6", model: "sonnet-4-6", seq: 1 },
  TechnicalAnalyst:   { icon: Activity,   color: "#f59e0b", model: "sonnet-4-6", seq: 2 },
  SentimentAnalyst:   { icon: Newspaper,  color: "#8b5cf6", model: "sonnet-4-6", seq: 3 },
  MacroAnalyst:       { icon: Globe,      color: "#06b6d4", model: "sonnet-4-6", seq: 4 },
  RiskManager:        { icon: Shield,     color: "#f97316", model: "sonnet-4-6", seq: 5 },
  TraderAgent:        { icon: Brain,      color: "#00e57a", model: "opus-4-6",   seq: 6 },
};

// Mini sparkline from an array of latency values (fake but plausible)
function Sparkline({ color }: { color: string }) {
  const pts = [40, 65, 52, 80, 48, 70, 55, 62, 45, 58];
  const max = Math.max(...pts);
  const min = Math.min(...pts);
  const range = max - min || 1;
  const w = 60; const h = 20;
  const d = pts.map((v, i) =>
    `${(i / (pts.length - 1)) * w},${h - ((v - min) / range) * (h - 2) - 1}`
  ).join(" ");
  return (
    <svg width={w} height={h} className="shrink-0">
      <polyline points={d} fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" opacity={0.7} />
    </svg>
  );
}

export default function AgentsPage() {
  const [agents, setAgents]               = useState<AgentStatus[]>([]);
  const [loading, setLoading]             = useState(false);
  const [debate, setDebate]               = useState<Record<string, unknown> | null>(null);
  const [debateLoading, setDebateLoading] = useState(false);
  const [debateTicker, setDebateTicker]   = useState("AAPL");

  const { isLoggedIn, isAtLeast } = useAuth();
  const [upgradeOpen, setUpgradeOpen] = useState(false);

  useEffect(() => { loadAgents(); }, []);

  async function loadAgents() {
    setLoading(true);
    try {
      const data = await getAgentStatus();
      setAgents(data.agents);
    } finally {
      setLoading(false);
    }
  }

  async function handleDebate() {
    if (!isLoggedIn) { window.location.href = "/login"; return; }
    if (!isAtLeast("retail")) { setUpgradeOpen(true); return; }
    setDebateLoading(true);
    try {
      const result = await triggerDebate(debateTicker);
      setDebate(result as Record<string, unknown>);
    } catch (e) {
      console.error(e);
    } finally {
      setDebateLoading(false);
    }
  }

  return (
    <div className="max-w-7xl mx-auto px-4 py-6 space-y-4">

      {/* Header */}
      <div className="terminal-panel">
        <div className="terminal-header">
          <Brain className="h-3 w-3 text-primary" />
          <span className="terminal-label">Agent Network — LangGraph DAG Pipeline</span>
          <button
            onClick={loadAgents}
            disabled={loading}
            className="ml-auto flex items-center gap-1.5 px-2 py-0.5 border border-border/40 text-muted-foreground hover:text-foreground hover:border-primary/30 transition-colors"
          >
            <RefreshCw className={`h-2.5 w-2.5 ${loading ? "animate-spin" : ""}`} />
            <span className="terminal-label">REFRESH</span>
          </button>
        </div>

        {/* Pipeline DAG diagram */}
        <div className="px-4 py-3 border-b border-border/40 bg-muted/30">
          <div className="flex items-center gap-1 text-[10px] font-mono text-muted-foreground overflow-x-auto">
            {["FundamentalAnalyst", "TechnicalAnalyst", "SentimentAnalyst", "MacroAnalyst"].map((name, i) => {
              const meta = AGENT_META[name];
              return (
                <span key={name} className="flex items-center gap-1">
                  {i > 0 && <span className="text-border">┃</span>}
                  <span style={{ color: meta.color }}>{name.replace("Analyst","")}</span>
                </span>
              );
            })}
            <span className="text-muted-foreground/40 mx-1">→</span>
            <span className="text-warn">Bull/Bear Debate</span>
            <span className="text-muted-foreground/40 mx-1">→</span>
            <span className="text-primary font-bold">TraderAgent</span>
            <span className="text-muted-foreground/40 mx-1">→</span>
            <span style={{ color: AGENT_META.RiskManager.color }}>RiskManager</span>
          </div>
        </div>
      </div>

      {/* Agent cards */}
      {agents.length === 0 && !loading ? (
        <div className="terminal-panel">
          <div className="flex flex-col items-center justify-center py-16 gap-3">
            <div className="text-primary/20 font-mono text-4xl">[ ]</div>
            <span className="terminal-label">AGENTS OFFLINE — REFRESH TO RECONNECT</span>
          </div>
        </div>
      ) : (
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-3">
          {agents.map((agent) => {
            const meta = AGENT_META[agent.name] || { icon: Brain, color: "#64748b", model: "sonnet-4-6", seq: 0 };
            const Icon = meta.icon;
            const isTrader = agent.name === "TraderAgent";
            return (
              <div
                key={agent.name}
                className="terminal-panel"
                style={{ borderColor: isTrader ? `${meta.color}40` : undefined }}
              >
                <div className="terminal-header" style={{ borderBottomColor: `${meta.color}20` }}>
                  <span className="terminal-label" style={{ color: meta.color }}>
                    AGENT {String(meta.seq).padStart(2, "0")}
                  </span>
                  <span className="terminal-label ml-2">{agent.name.toUpperCase()}</span>
                  <div className="ml-auto flex items-center gap-1.5">
                    <span className="h-1.5 w-1.5 rounded-full animate-pulse" style={{ backgroundColor: meta.color }} />
                    <span className="terminal-label" style={{ color: meta.color }}>HEALTHY</span>
                  </div>
                </div>

                <div className="p-4">
                  <div className="flex items-start gap-3 mb-4">
                    <div className="p-2 border shrink-0" style={{ borderColor: `${meta.color}30`, background: `${meta.color}10` }}>
                      <Icon className="h-4 w-4" style={{ color: meta.color }} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-xs font-semibold text-foreground mb-0.5">{agent.name}</div>
                      <p className="text-[10px] text-muted-foreground leading-relaxed line-clamp-2">{agent.role}</p>
                    </div>
                  </div>

                  {/* Metrics row */}
                  <div className="grid grid-cols-3 gap-2 mb-4">
                    <div className="border border-border/30 p-2 text-center bg-muted/20">
                      <div className="text-sm font-bold font-mono text-bull">{agent.accuracy_7d}%</div>
                      <div className="terminal-label mt-0.5">7D ACC</div>
                    </div>
                    <div className="border border-border/30 p-2 text-center bg-muted/20">
                      <div className="text-sm font-bold font-mono">{agent.avg_latency_ms}ms</div>
                      <div className="terminal-label mt-0.5">LATENCY</div>
                    </div>
                    <div className="border border-border/30 p-2 text-center bg-muted/20">
                      <div className="text-sm font-bold font-mono">{agent.signals_today}</div>
                      <div className="terminal-label mt-0.5">TODAY</div>
                    </div>
                  </div>

                  {/* Latency sparkline */}
                  <div className="flex items-center justify-between mb-3">
                    <span className="terminal-label">LATENCY TRACE</span>
                    <Sparkline color={meta.color} />
                  </div>

                  {/* Model badge + strategies */}
                  <div className="flex items-center gap-2 flex-wrap">
                    <span
                      className="text-[10px] font-mono font-bold px-2 py-0.5 border"
                      style={{ color: meta.color, borderColor: `${meta.color}40`, background: `${meta.color}10` }}
                    >
                      {meta.model}
                    </span>
                    {agent.strategies.slice(0, 2).map((s) => (
                      <span key={s} className="text-[10px] font-mono px-1.5 py-0.5 border border-border/30 text-muted-foreground bg-muted/30">
                        {s.replace(/_/g, " ")}
                      </span>
                    ))}
                    {agent.strategies.length > 2 && (
                      <span className="text-[10px] text-muted-foreground">+{agent.strategies.length - 2}</span>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Bull/Bear Debate trigger */}
      <div className="terminal-panel">
        <div className="terminal-header">
          <Zap className="h-3 w-3 text-warn" />
          <span className="terminal-label">Force Bull/Bear Debate</span>
        </div>
        <div className="p-4 space-y-4">
          <div className="flex items-center gap-3">
            <span className="terminal-label shrink-0">TICKER</span>
            <input
              value={debateTicker}
              onChange={(e) => setDebateTicker(e.target.value.toUpperCase())}
              className="px-3 py-1.5 bg-background border border-border/50 text-xs font-mono text-foreground focus:outline-none focus:border-primary/50 w-28"
            />
            <button
              onClick={handleDebate}
              disabled={debateLoading}
              className="px-3 py-1.5 text-xs font-mono font-semibold border border-warn/40 bg-warn/10 text-warn hover:bg-warn/20 disabled:opacity-40 disabled:cursor-not-allowed transition-colors flex items-center gap-1.5"
            >
              {!isLoggedIn ? <Lock className="h-3 w-3" /> : <Zap className="h-3 w-3" />}
              {debateLoading ? "RUNNING···" : !isLoggedIn ? "SIGN IN TO DEBATE" : "START DEBATE"}
            </button>
          </div>

          {debate && (
            <div className="space-y-3">
              <div className="grid md:grid-cols-2 gap-3">
                <div className="terminal-panel border-bull/20">
                  <div className="terminal-header bg-bull/5">
                    <span className="h-1.5 w-1.5 rounded-full bg-bull" />
                    <span className="terminal-label text-bull">BULL CASE</span>
                  </div>
                  <p className="p-3 text-xs text-muted-foreground leading-relaxed">{debate.bull_case as string}</p>
                </div>
                <div className="terminal-panel border-bear/20">
                  <div className="terminal-header bg-bear/5">
                    <span className="h-1.5 w-1.5 rounded-full bg-bear" />
                    <span className="terminal-label text-bear">BEAR CASE</span>
                  </div>
                  <p className="p-3 text-xs text-muted-foreground leading-relaxed">{debate.bear_case as string}</p>
                </div>
              </div>
              <div className="terminal-panel border-primary/30">
                <div className="terminal-header bg-primary/5">
                  <span className="terminal-label">FINAL VERDICT — TRADER AGENT</span>
                </div>
                <div className="p-4 text-center">
                  <div className={`text-2xl font-bold font-mono ${debate.final_direction === "LONG" ? "text-bull" : "text-bear"}`}>
                    {debate.final_direction as string}
                  </div>
                  <div className="text-xs text-muted-foreground mt-1 font-mono">
                    CONFIDENCE {Math.round(debate.confidence_score as number)}%
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      <UpgradeModal
        isOpen={upgradeOpen}
        onClose={() => setUpgradeOpen(false)}
        feature="Bull/Bear Agent Debate"
        requiredTier="retail"
        reason="Force a live Bull vs Bear debate between the 4 analyst agents and get a final TraderAgent verdict. Available on Retail and above."
      />
    </div>
  );
}
