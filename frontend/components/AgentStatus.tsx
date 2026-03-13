"use client";

import { Activity, Brain, BarChart2, Newspaper, Globe, Shield, TrendingUp } from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { type AgentStatus } from "@/lib/api";
import { cn } from "@/lib/utils";

const AGENT_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  FundamentalAnalyst: BarChart2,
  TechnicalAnalyst: Activity,
  SentimentAnalyst: Newspaper,
  MacroAnalyst: Globe,
  RiskManager: Shield,
  TraderAgent: Brain,
};

interface AgentStatusPanelProps {
  agents: AgentStatus[];
}

export function AgentStatusPanel({ agents }: AgentStatusPanelProps) {
  return (
    <Card className="border-border/50">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2">
          <Activity className="h-3.5 w-3.5 text-primary" />
          Agent Network
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {agents.map((agent) => {
          const Icon = AGENT_ICONS[agent.name] || Brain;
          const isTrader = agent.name === "TraderAgent";
          return (
            <div
              key={agent.name}
              className={cn(
                "flex items-center gap-3 p-2.5 rounded-lg border transition-colors",
                isTrader ? "border-primary/30 bg-primary/5" : "border-border/30 bg-card/50"
              )}
            >
              <div className={cn("p-1.5 rounded-md", isTrader ? "bg-primary/10" : "bg-secondary")}>
                <Icon className={cn("h-3.5 w-3.5", isTrader ? "text-primary" : "text-muted-foreground")} />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1.5">
                  <span className="text-xs font-medium truncate">{agent.name}</span>
                  {isTrader && (
                    <span className="text-[10px] px-1 py-0.5 bg-primary/10 text-primary rounded font-mono">opus-4-6</span>
                  )}
                </div>
                <div className="flex items-center gap-2 mt-0.5">
                  <span className="text-[10px] text-muted-foreground">{agent.avg_latency_ms}ms</span>
                  <span className="text-[10px] text-muted-foreground">•</span>
                  <span className="text-[10px] text-muted-foreground">{agent.signals_today} signals</span>
                </div>
              </div>
              <div className="text-right shrink-0">
                <div className="text-xs font-semibold text-bull">{agent.accuracy_7d}%</div>
                <div className="flex items-center gap-1 mt-0.5">
                  <div className="h-1.5 w-1.5 rounded-full bg-bull animate-pulse-slow" />
                  <span className="text-[10px] text-muted-foreground">live</span>
                </div>
              </div>
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}
