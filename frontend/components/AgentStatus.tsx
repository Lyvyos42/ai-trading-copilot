"use client";

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

export function AgentStatusPanel({ agents, compact }: AgentStatusPanelProps) {
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
                "flex items-center gap-2 px-3 py-2 transition-colors",
                isTrader && "bg-primary/[0.04]"
              )}
            >
              {/* Icon */}
              <div className={cn(
                "h-5 w-5 rounded flex items-center justify-center shrink-0",
                isTrader ? "bg-primary/10 border border-primary/20" : "bg-muted border border-border/50"
              )}>
                <Icon className={cn("h-2.5 w-2.5", isTrader ? "text-primary" : "text-muted-foreground")} />
              </div>

              {/* Name + role */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1">
                  <span className={cn(
                    "text-[10px] font-mono font-bold truncate",
                    isTrader ? "text-primary" : "text-foreground"
                  )}>
                    {AGENT_SHORT[agent.name] || agent.name.toUpperCase()}
                  </span>
                  {isTrader && (
                    <span className="text-[8px] font-mono text-primary/60 border border-primary/20 rounded px-0.5">OPUS</span>
                  )}
                </div>
                <div className="flex items-center gap-2 mt-0.5">
                  <span className="text-[9px] font-mono text-muted-foreground">{agent.avg_latency_ms}ms</span>
                  <span className="text-[9px] font-mono text-muted-foreground">{agent.signals_today} sig</span>
                </div>
              </div>

              {/* Status + accuracy */}
              <div className="text-right shrink-0">
                <div className={cn(
                  "text-[10px] font-mono font-bold",
                  agent.accuracy_7d >= 65 ? "text-bull" : agent.accuracy_7d >= 55 ? "text-warn" : "text-bear"
                )}>
                  {agent.accuracy_7d}%
                </div>
                <div className="flex items-center justify-end gap-1 mt-0.5">
                  <div className={cn(
                    "h-1.5 w-1.5 rounded-full",
                    healthy ? "bg-bull animate-pulse" : "bg-bear"
                  )} />
                  <span className="text-[8px] font-mono text-muted-foreground">
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
                    <span className="text-[9px] font-mono text-primary border border-primary/30 rounded px-1">OPUS 4.6</span>
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
                  agent.accuracy_7d >= 65 ? "text-bull" : agent.accuracy_7d >= 55 ? "text-warn" : "text-bear"
                )}>
                  {agent.accuracy_7d}%
                </div>
                <div className="text-[9px] text-muted-foreground">7d accuracy</div>
                <div className="flex items-center justify-end gap-1 mt-1">
                  <div className={cn(
                    "h-1.5 w-1.5 rounded-full",
                    healthy ? "bg-bull animate-pulse" : "bg-bear"
                  )} />
                  <span className="text-[9px] font-mono text-muted-foreground">{healthy ? "HEALTHY" : "DOWN"}</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
