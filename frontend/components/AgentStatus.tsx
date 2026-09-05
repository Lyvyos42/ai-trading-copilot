"use client";

import { memo } from "react";
import { Activity, Brain, BarChart2, Newspaper, Globe, Shield, Waves, RefreshCw, GitBranch, FlaskConical, ShieldCheck } from "lucide-react";
import { type AgentStatus } from "@/lib/api";
import { cn } from "@/lib/utils";

const AGENT_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  FundamentalAnalyst:  BarChart2,
  TechnicalAnalyst:    Activity,
  SentimentAnalyst:    Newspaper,
  MacroAnalyst:        Globe,
  OrderFlowAnalyst:    Waves,
  RegimeChangeAnalyst: RefreshCw,
  CorrelationAnalyst:  GitBranch,
  QuantAnalyst:        FlaskConical,
  RiskManager:         Shield,
  RiskGate:            ShieldCheck,
  TraderAgent:         Brain,
};

const AGENT_SHORT: Record<string, string> = {
  FundamentalAnalyst:  "FUNDAMENTAL",
  TechnicalAnalyst:    "TECHNICAL",
  SentimentAnalyst:    "SENTIMENT",
  MacroAnalyst:        "MACRO",
  OrderFlowAnalyst:    "ORDER FLOW",
  RegimeChangeAnalyst: "REGIME",
  CorrelationAnalyst:  "CORRELATION",
  QuantAnalyst:        "QUANT",
  RiskManager:         "RISK MGR",
  RiskGate:            "RISK GATE",
  TraderAgent:         "TRADER",
};

interface AgentStatusPanelProps {
  agents: AgentStatus[];
  /** Compact terminal-panel mode for sidebar */
  compact?: boolean;
}

export const AgentStatusPanel = memo(function AgentStatusPanel({ agents, compact }: AgentStatusPanelProps) {
  if (compact) {
    return (
      <div className="divide-y divide-border/50">
        {agents.map((agent) => {
          const Icon    = AGENT_ICONS[agent.name] || Brain;
          const isTrader = agent.name === "TraderAgent";
          const healthy  = agent.status === "HEALTHY";

          return (
            <div
              key={agent.name}
              className={cn(
                "flex items-center gap-1.5 px-2.5 py-1 transition-colors",
                isTrader && "bg-primary/[0.04]"
              )}
            >
              {/* Icon */}
              <div className={cn(
                "h-4 w-4 rounded flex items-center justify-center shrink-0",
                isTrader ? "bg-primary/10 border border-primary/20" : "bg-muted border border-border/50"
              )}>
                <Icon className={cn("h-2 w-2", isTrader ? "text-primary" : "text-muted-foreground")} />
              </div>

              {/* Name + stats inline */}
              <div className="flex-1 min-w-0 flex items-center gap-1.5">
                <span className={cn(
                  "text-[12px] font-mono font-bold truncate",
                  isTrader ? "text-primary" : "text-foreground"
                )}>
                  {AGENT_SHORT[agent.name] || agent.name.toUpperCase()}
                </span>
                {isTrader && (
                  <span className="text-[11px] font-mono text-primary/60 border border-primary/20 rounded px-0.5">OPUS</span>
                )}
                <span className="text-[12px] font-mono text-muted-foreground/60 ml-auto mr-1">{agent.avg_latency_ms}ms {agent.signals_today} sig</span>
              </div>

              {/* Status + accuracy */}
              <div className="flex items-center gap-1.5 shrink-0">
                <span className={cn(
                  "text-[12px] font-mono font-bold",
                  agent.accuracy_7d != null
                    ? (agent.accuracy_7d >= 65 ? "text-bull" : agent.accuracy_7d >= 55 ? "text-warn" : "text-bear")
                    : "text-muted-foreground"
                )}>
                  {agent.accuracy_7d != null
                    ? `${agent.accuracy_7d}%${agent.accuracy_sample ? ` n=${agent.accuracy_sample}` : ""}`
                    : "—"}
                </span>
                <div className="flex items-center gap-0.5">
                  <div className={cn(
                    "h-1 w-1 rounded-full",
                    healthy ? "bg-bull animate-pulse" : "bg-bear"
                  )} />
                  <span className="text-[11px] font-mono text-muted-foreground">
                    {healthy ? "LIVE" : "DOWN"}
                  </span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    );
  }

  // Full-size card view (for /agents page)
  return (
    <div className="terminal-panel">
      <div className="terminal-header">
        <Activity className="h-3 w-3 text-primary" />
        <span className="terminal-label">Agent Network</span>
      </div>
      <div className="divide-y divide-border/50">
        {agents.map((agent) => {
          const Icon    = AGENT_ICONS[agent.name] || Brain;
          const isTrader = agent.name === "TraderAgent";
          const healthy  = agent.status === "HEALTHY";

          return (
            <div key={agent.name} className="flex items-center gap-3 px-4 py-3">
              <div className={cn(
                "p-2 rounded border",
                isTrader ? "bg-primary/10 border-primary/20" : "bg-muted border-border/50"
              )}>
                <Icon className={cn("h-4 w-4", isTrader ? "text-primary" : "text-muted-foreground")} />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold">{agent.name}</span>
                  {isTrader && (
                    <span className="text-[13px] font-mono text-primary border border-primary/30 rounded px-1">OPUS 4.6</span>
                  )}
                </div>
                <div className="text-xs text-muted-foreground mt-0.5">{agent.role}</div>
                <div className="flex items-center gap-3 mt-1 text-xs text-muted-foreground font-mono">
                  <span>{agent.avg_latency_ms}ms latency</span>
                  <span>{agent.signals_today} signals today</span>
                </div>
              </div>
              <div className="text-right">
                <div className={cn(
                  "text-lg font-mono font-bold",
                  agent.accuracy_7d != null
                    ? (agent.accuracy_7d >= 65 ? "text-bull" : agent.accuracy_7d >= 55 ? "text-warn" : "text-bear")
                    : "text-muted-foreground"
                )}>
                  {agent.accuracy_7d != null ? `${agent.accuracy_7d}%` : "—"}
                </div>
                <div className="text-[13px] text-muted-foreground">
                  {agent.accuracy_7d != null
                    ? `7d accuracy · ${agent.accuracy_sample ?? 0} resolved`
                    : "unmeasured"}
                </div>
                <div className="flex items-center justify-end gap-1 mt-1">
                  <div className={cn(
                    "h-1.5 w-1.5 rounded-full",
                    healthy ? "bg-bull animate-pulse" : "bg-bear"
                  )} />
                  <span className="text-[13px] font-mono text-muted-foreground">{healthy ? "HEALTHY" : "DOWN"}</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
});
