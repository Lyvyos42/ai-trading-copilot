"use client";

import { useEffect, useState } from "react";
import { getAgentStatus, triggerDebate, type AgentStatus } from "@/lib/api";
import { useAuth } from "@/lib/useAuth";
import { UpgradeModal } from "@/components/UpgradeModal";
import {
  IconRefresh,
  IconSignal,
  IconLock,
  IconAgents,
  IconShield,
  ROLE_GEOMETRY,
} from "@/components/icons/GeoIcons";

// Per-agent accent color — committed, not derived from generic palette
const AGENT_META: Record<string, {
  color: string;
  model: string;
  seq: number;
  role: string;
}> = {
  FundamentalAnalyst: { color: "#D4A240", model: "sonnet-4-6", seq: 1, role: "Fundamental analysis. P/E, P/B, earnings momentum, balance sheet stress." },
  TechnicalAnalyst:   { color: "#f59e0b", model: "sonnet-4-6", seq: 2, role: "Price action. EMA crossovers, RSI divergence, volume-weighted momentum." },
  SentimentAnalyst:   { color: "#7c3aed", model: "sonnet-4-6", seq: 3, role: "Market sentiment. News NLP, social positioning, fear/greed index." },
  MacroAnalyst:       { color: "#06b6d4", model: "sonnet-4-6", seq: 4, role: "Macro regime. GDP, CPI, Fed policy, carry trades, cross-asset correlation." },
  RiskManager:        { color: "#f97316", model: "sonnet-4-6", seq: 5, role: "Risk enforcement. Kelly sizing, drawdown limits, portfolio correlation." },
  TraderAgent:        { color: "#22c55e", model: "opus-4-6",   seq: 6, role: "Final decision. Synthesizes all analysts, issues execution signal." },
};

/** Micro latency sparkline — pure SVG, no library */
function Sparkline({ color, values }: { color: string; values?: number[] }) {
  const pts = values || [40, 65, 52, 80, 48, 70, 55, 62, 45, 58];
  const max = Math.max(...pts);
  const min = Math.min(...pts);
  const range = max - min || 1;
  const w = 56; const h = 18;
  const d = pts.map((v, i) =>
    `${(i / (pts.length - 1)) * w},${h - ((v - min) / range) * (h - 4) - 2}`
  ).join(" ");
  return (
    <svg width={w} height={h} className="shrink-0" overflow="visible">
      <polyline
        points={d}
        fill="none"
        stroke={color}
        strokeWidth="1.2"
        strokeLinecap="round"
        strokeLinejoin="round"
        opacity={0.65}
      />
      {/* End dot */}
      {(() => {
        const last = pts[pts.length - 1];
        const x = w;
        const y = h - ((last - min) / range) * (h - 4) - 2;
        return <circle cx={x} cy={y} r="2" fill={color} opacity="0.9" />;
      })()}
    </svg>
  );
}

/** Pipeline stage diagram — horizontal, connected */
function PipelineDiagram() {
  const stages = [
    { id: "fundamental", label: "FUNDAMENTAL",  seq: "01" },
    { id: "technical",   label: "TECHNICAL",    seq: "02" },
    { id: "sentiment",   label: "SENTIMENT",    seq: "03" },
    { id: "macro",       label: "MACRO",        seq: "04" },
    { id: "debate",      label: "DEBATE",       seq: "05", accent: true },
    { id: "risk",        label: "RISK",         seq: "06", warn: true },
    { id: "trader",      label: "SIGNAL",       seq: "07", primary: true },
  ];

  return (
    <div className="px-4 py-3" style={{ borderBottom: "1px solid hsl(var(--border))" }}>
      <div className="flex items-center gap-0 overflow-x-auto">
        {stages.map((s, i) => {
          const color = s.primary
            ? "hsl(142 65% 42%)"
            : s.accent
            ? "hsl(38 85% 52%)"
            : s.warn
            ? "hsl(22 90% 55%)"
            : "hsl(var(--muted-foreground))";

          return (
            <div key={s.id} className="flex items-center">
              <div
                className="flex flex-col items-center gap-0.5 px-2.5 py-1"
                style={{
                  border: "1px solid",
                  borderColor: s.primary ? "hsl(142 65% 42% / 0.4)" : "hsl(var(--border))",
                  borderRadius: "2px",
                  background: s.primary ? "hsl(142 65% 42% / 0.05)" : "transparent",
                }}
              >
                <span
                  className="text-[7px] font-bold"
                  style={{ fontFamily: "'BerkeleyMono', 'IBM Plex Mono', monospace", color: "hsl(var(--muted-foreground) / 0.5)" }}
                >
                  {s.seq}
                </span>
                <span
                  className="text-[8px] font-bold tracking-[0.08em] whitespace-nowrap"
                  style={{ fontFamily: "'BerkeleyMono', 'IBM Plex Mono', monospace", color }}
                >
                  {s.label}
                </span>
              </div>
              {i < stages.length - 1 && (
                <svg width="16" height="10" viewBox="0 0 16 10" fill="none" className="shrink-0">
                  <line x1="0" y1="5" x2="12" y2="5" stroke="hsl(var(--border-strong))" strokeWidth="1" />
                  <polyline points="8,2 12,5 8,8" stroke="hsl(var(--border-strong))" strokeWidth="1" strokeLinecap="round" strokeLinejoin="round" fill="none" />
                </svg>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

/** 3D Agent Card — the core visual identity piece */
function AgentCard({ agent, isActive = false }: { agent: AgentStatus; isActive?: boolean }) {
  const meta = AGENT_META[agent.name] || { color: "#D4A240", model: "sonnet-4-6", seq: 0, role: "" };
  const geo = ROLE_GEOMETRY[agent.name];
  const GeoComponent = geo?.Component;
  const animClass = geo?.animationClass || "shape-researcher";
  const isTrader = agent.name === "TraderAgent";
  const color = meta.color;

  return (
    <div
      className="panel depth-card panel-ao relative overflow-hidden"
      style={{
        /* Elevated surface — agent cards have presence, they're not flat */
        background: `hsl(var(--surface-1))`,
        borderColor: isTrader ? `${color}35` : "hsl(var(--border))",
        transition: "transform 350ms cubic-bezier(0.23, 1, 0.32, 1), box-shadow 350ms ease",
      }}
    >
      {/* Accent edge — left-side colored rule, like a physical tab */}
      <div
        className="absolute left-0 top-0 bottom-0 w-[2px]"
        style={{
          background: `linear-gradient(180deg, ${color}00 0%, ${color}CC 30%, ${color}CC 70%, ${color}00 100%)`,
        }}
      />

      {/* Top-edge specular — overrides the generic panel::before with colored version for TraderAgent */}
      {isTrader && (
        <div
          className="absolute top-0 left-0 right-0 h-px z-10"
          style={{
            background: `linear-gradient(90deg, transparent 0%, ${color}50 30%, ${color}90 50%, ${color}50 70%, transparent 100%)`,
          }}
        />
      )}

      {/* Header */}
      <div
        className="flex items-center justify-between px-4 py-2.5 pl-5"
        style={{ borderBottom: "1px solid hsl(var(--border))" }}
      >
        <div className="flex items-center gap-2">
          <span
            className="text-[8px] font-bold tracking-[0.14em]"
            style={{ fontFamily: "'BerkeleyMono', 'IBM Plex Mono', monospace", color }}
          >
            {String(meta.seq).padStart(2, "0")}
          </span>
          <span
            className="text-[8px] font-bold tracking-[0.1em] uppercase"
            style={{ fontFamily: "'BerkeleyMono', 'IBM Plex Mono', monospace", color: "hsl(var(--foreground))" }}
          >
            {agent.name.replace("Analyst", " ANALYST").replace("Agent", " AGENT").replace("Manager", " MGR").toUpperCase()}
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          {/* Status indicator — precise dot, not rounded bubble */}
          <div
            className="h-1.5 w-1.5"
            style={{
              background: agent.status === "HEALTHY" ? "hsl(var(--bull))" : "hsl(var(--bear))",
              borderRadius: "50%",
              animation: "pulse-live 1.6s ease-in-out infinite",
            }}
          />
          <span
            className="text-[8px] font-bold tracking-[0.1em]"
            style={{
              fontFamily: "'BerkeleyMono', 'IBM Plex Mono', monospace",
              color: agent.status === "HEALTHY" ? "hsl(var(--bull))" : "hsl(var(--bear))",
            }}
          >
            {agent.status}
          </span>
        </div>
      </div>

      {/* Body */}
      <div className="px-4 py-3 pl-5">

        {/* 3D Geometry + Role info */}
        <div className="flex items-start gap-4 mb-4">
          {/* 3D geometric shape — rotates slowly, communicates agent role */}
          <div
            className="shrink-0 flex items-center justify-center"
            style={{
              width: 52,
              height: 52,
              background: `${color}08`,
              border: `1px solid ${color}20`,
              borderRadius: "3px",
              /* Subtle ambient occlusion on the shape container */
              boxShadow: `inset 0 -2px 4px ${color}10, inset 0 1px 0 ${color}15`,
            }}
          >
            {GeoComponent && (
              <div
                className={`${animClass}${isActive ? " shape-active" : ""}`}
                style={{ transformStyle: "preserve-3d" }}
              >
                <GeoComponent size={34} color={color} strokeWidth={1.1} active={isActive} />
              </div>
            )}
          </div>

          <div className="flex-1 min-w-0">
            {/* Role description */}
            <p
              className="text-[10px] leading-relaxed mb-2"
              style={{ color: "hsl(var(--muted-foreground))" }}
            >
              {meta.role}
            </p>
            {/* Model badge */}
            <span
              className="inline-flex items-center text-[9px] font-bold px-1.5 py-0.5"
              style={{
                fontFamily: "'BerkeleyMono', 'IBM Plex Mono', monospace",
                color,
                border: `1px solid ${color}35`,
                borderRadius: "2px",
                background: `${color}08`,
              }}
            >
              {meta.model}
            </span>
          </div>
        </div>

        {/* Metrics — three data cells */}
        <div
          className="grid grid-cols-3 gap-2 mb-3"
          style={{ borderTop: "1px solid hsl(var(--border))", paddingTop: "12px" }}
        >
          {[
            { label: "7D ACC", value: `${agent.accuracy_7d}%`, color: agent.accuracy_7d >= 60 ? "hsl(var(--bull))" : "hsl(var(--warn))" },
            { label: "LATENCY", value: `${agent.avg_latency_ms}ms`, color: "hsl(var(--foreground))" },
            { label: "TODAY", value: `${agent.signals_today}`, color },
          ].map(({ label, value, color: c }) => (
            <div
              key={label}
              className="flex flex-col items-center gap-0.5 py-2"
              style={{
                background: "hsl(var(--surface-0))",
                border: "1px solid hsl(var(--border))",
                borderRadius: "2px",
                /* Ambient occlusion — cells have depth relative to card */
                boxShadow: "inset 0 1px 3px hsl(0 0% 0% / 0.2)",
              }}
            >
              <span
                className="text-sm font-bold"
                style={{ fontFamily: "'BerkeleyMono', 'IBM Plex Mono', monospace", color: c, lineHeight: 1 }}
              >
                {value}
              </span>
              <span className="terminal-label">{label}</span>
            </div>
          ))}
        </div>

        {/* Latency trace */}
        <div className="flex items-center justify-between mb-3">
          <span className="terminal-label">LATENCY TRACE</span>
          <Sparkline color={color} />
        </div>

        {/* Strategy tags */}
        <div className="flex flex-wrap gap-1">
          {agent.strategies.slice(0, 3).map((s) => (
            <span
              key={s}
              className="text-[8px] px-1.5 py-0.5"
              style={{
                fontFamily: "'BerkeleyMono', 'IBM Plex Mono', monospace",
                color: "hsl(var(--muted-foreground))",
                border: "1px solid hsl(var(--border))",
                borderRadius: "2px",
                background: "hsl(var(--surface-0))",
              }}
            >
              {s.replace(/_/g, " ")}
            </span>
          ))}
          {agent.strategies.length > 3 && (
            <span
              className="text-[8px] px-1.5 py-0.5"
              style={{ fontFamily: "'BerkeleyMono', 'IBM Plex Mono', monospace", color: "hsl(var(--muted-foreground) / 0.6)" }}
            >
              +{agent.strategies.length - 3} more
            </span>
          )}
        </div>
      </div>
    </div>
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

      {/* Page header */}
      <div className="panel panel-active">
        <div
          className="panel-header"
          style={{ background: "hsl(var(--surface-2))" }}
        >
          <IconAgents size={12} color="hsl(var(--primary))" />
          <span className="terminal-label" style={{ color: "hsl(var(--foreground) / 0.6)" }}>
            Agent Network
          </span>
          <span
            className="text-[9px] font-bold"
            style={{ fontFamily: "'BerkeleyMono', 'IBM Plex Mono', monospace", color: "hsl(var(--muted-foreground))" }}
          >
            — LangGraph DAG Pipeline
          </span>
          <button
            onClick={loadAgents}
            disabled={loading}
            className="ml-auto flex items-center gap-1.5 px-2 py-1 transition-colors"
            style={{
              border: "1px solid hsl(var(--border-strong))",
              borderRadius: "2px",
              background: "none",
              cursor: "pointer",
              color: "hsl(var(--muted-foreground))",
              fontFamily: "'BerkeleyMono', 'IBM Plex Mono', monospace",
              fontSize: "9px",
              letterSpacing: "0.1em",
            }}
          >
            <div style={loading ? { animation: "spin 1s linear infinite" } : {}}>
              <IconRefresh size={11} color="currentColor" />
            </div>
            REFRESH
          </button>
        </div>
        <PipelineDiagram />
      </div>

      {/* Agent cards — 3-column grid */}
      {agents.length === 0 && !loading ? (
        <div
          className="panel flex flex-col items-center justify-center py-20 gap-3"
        >
          <svg width="32" height="32" viewBox="0 0 32 32" fill="none" stroke="hsl(var(--primary) / 0.2)" strokeWidth="1">
            <polygon points="16,3 27,9.5 16,16 5,9.5" />
            <polygon points="5,9.5 16,16 16,29 5,22.5" />
            <polygon points="27,9.5 16,16 16,29 27,22.5" />
          </svg>
          <span className="terminal-label">AGENTS OFFLINE — REFRESH TO RECONNECT</span>
        </div>
      ) : (
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-3">
          {agents.map((agent) => (
            <AgentCard key={agent.name} agent={agent} />
          ))}
        </div>
      )}

      {/* Bull/Bear Debate panel */}
      <div className="panel">
        <div className="panel-header">
          <IconSignal size={12} color="hsl(var(--warn))" />
          <span className="terminal-label">Force Bull / Bear Debate</span>
          <div
            className="ml-2 text-[8px] font-bold px-1.5 py-0.5"
            style={{
              fontFamily: "'BerkeleyMono', 'IBM Plex Mono', monospace",
              color: "hsl(var(--warn) / 0.8)",
              border: "1px solid hsl(var(--warn) / 0.2)",
              borderRadius: "2px",
              background: "hsl(var(--warn) / 0.05)",
            }}
          >
            RETAIL+
          </div>
        </div>
        <div className="p-4 space-y-4">
          <div className="flex items-center gap-3">
            <span className="terminal-label shrink-0">TICKER</span>
            <input
              value={debateTicker}
              onChange={(e) => setDebateTicker(e.target.value.toUpperCase())}
              className="input-terminal w-28"
              placeholder="AAPL"
            />
            <button
              onClick={handleDebate}
              disabled={debateLoading}
              className="flex items-center gap-1.5 px-3 py-1.5 transition-colors"
              style={{
                fontFamily: "'BerkeleyMono', 'IBM Plex Mono', monospace",
                fontSize: "10px",
                fontWeight: 700,
                letterSpacing: "0.08em",
                border: "1px solid hsl(var(--warn) / 0.4)",
                borderRadius: "2px",
                background: "hsl(var(--warn) / 0.06)",
                color: "hsl(var(--warn))",
                cursor: debateLoading ? "not-allowed" : "pointer",
                opacity: debateLoading ? 0.5 : 1,
              }}
            >
              {!isLoggedIn ? <IconLock size={11} color="currentColor" /> : <IconSignal size={11} color="currentColor" />}
              {debateLoading ? "RUNNING···" : !isLoggedIn ? "SIGN IN TO DEBATE" : "START DEBATE"}
            </button>
          </div>

          {debate && (
            <div className="space-y-3">
              <div className="grid md:grid-cols-2 gap-3">
                {/* Bull case */}
                <div
                  className="panel"
                  style={{ borderColor: "hsl(var(--bull) / 0.2)" }}
                >
                  <div
                    className="panel-header"
                    style={{ background: "hsl(var(--bull) / 0.04)", borderBottomColor: "hsl(var(--bull) / 0.15)" }}
                  >
                    <span
                      className="h-1.5 w-1.5 rounded-full shrink-0"
                      style={{ background: "hsl(var(--bull))" }}
                    />
                    <span className="terminal-label text-bull">BULL CASE</span>
                  </div>
                  <p className="p-3 text-[11px] leading-relaxed" style={{ color: "hsl(var(--muted-foreground))" }}>
                    {debate.bull_case as string}
                  </p>
                </div>
                {/* Bear case */}
                <div
                  className="panel"
                  style={{ borderColor: "hsl(var(--bear) / 0.2)" }}
                >
                  <div
                    className="panel-header"
                    style={{ background: "hsl(var(--bear) / 0.04)", borderBottomColor: "hsl(var(--bear) / 0.15)" }}
                  >
                    <span
                      className="h-1.5 w-1.5 rounded-full shrink-0"
                      style={{ background: "hsl(var(--bear))" }}
                    />
                    <span className="terminal-label text-bear">BEAR CASE</span>
                  </div>
                  <p className="p-3 text-[11px] leading-relaxed" style={{ color: "hsl(var(--muted-foreground))" }}>
                    {debate.bear_case as string}
                  </p>
                </div>
              </div>

              {/* Final verdict */}
              <div
                className="panel panel-active"
                style={{ borderColor: "hsl(var(--primary) / 0.3)" }}
              >
                <div className="panel-header">
                  <span className="terminal-label">FINAL VERDICT — TRADER AGENT</span>
                  <svg className="ml-1" width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="hsl(var(--primary) / 0.5)" strokeWidth="1">
                    <polygon points="5,1 9,5 5,9 1,5" />
                  </svg>
                </div>
                <div className="p-6 text-center">
                  <div
                    className="text-3xl font-bold mb-1"
                    style={{
                      fontFamily: "'BerkeleyMono', 'IBM Plex Mono', monospace",
                      color: debate.final_direction === "LONG" ? "hsl(var(--bull))" : "hsl(var(--bear))",
                      letterSpacing: "-0.02em",
                    }}
                  >
                    {debate.final_direction as string}
                  </div>
                  <div
                    className="text-[11px]"
                    style={{ fontFamily: "'BerkeleyMono', 'IBM Plex Mono', monospace", color: "hsl(var(--muted-foreground))" }}
                  >
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
