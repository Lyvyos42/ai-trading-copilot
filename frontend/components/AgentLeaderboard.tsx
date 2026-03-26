"use client";

import { cn } from "@/lib/utils";
import type { AgentPerformance } from "@/lib/api";

interface AgentLeaderboardProps {
  data: AgentPerformance[];
}

const AGENT_COLORS: Record<string, string> = {
  fundamental: "text-[hsl(42,78%,50%)]",
  technical: "text-[hsl(38,85%,52%)]",
  sentiment: "text-[hsl(142,65%,42%)]",
  macro: "text-[hsl(280,75%,58%)]",
  order_flow: "text-[hsl(201,90%,52%)]",
  regime_change: "text-[hsl(0,68%,52%)]",
  correlation: "text-[hsl(170,70%,45%)]",
};

export function AgentLeaderboard({ data }: AgentLeaderboardProps) {
  if (!data.length) {
    return (
      <div className="panel p-6 flex items-center justify-center h-[200px]">
        <span className="text-[hsl(var(--muted-foreground))] font-mono text-xs">NO AGENT DATA YET</span>
      </div>
    );
  }

  return (
    <div className="panel p-4">
      <div className="flex items-center gap-2 mb-3">
        <span className="text-[10px] font-mono font-bold text-[hsl(var(--muted-foreground))] tracking-widest">AGENT LEADERBOARD</span>
      </div>
      <table className="w-full">
        <thead>
          <tr className="border-b border-[hsl(var(--border))]">
            <th className="text-[9px] font-mono text-[hsl(var(--muted-foreground))] py-1.5 text-left">#</th>
            <th className="text-[9px] font-mono text-[hsl(var(--muted-foreground))] py-1.5 text-left">AGENT</th>
            <th className="text-[9px] font-mono text-[hsl(var(--muted-foreground))] py-1.5 text-right">ACCURACY</th>
            <th className="text-[9px] font-mono text-[hsl(var(--muted-foreground))] py-1.5 text-right">SIGNALS</th>
            <th className="text-[9px] font-mono text-[hsl(var(--muted-foreground))] py-1.5 text-right">AVG CONF</th>
          </tr>
        </thead>
        <tbody>
          {data.map((agent, i) => (
            <tr key={agent.agent} className="border-b border-[hsl(var(--border)/0.5)]">
              <td className="text-[10px] font-mono text-[hsl(var(--muted-foreground))] py-1.5">{i + 1}</td>
              <td className={cn("text-[11px] font-mono font-bold py-1.5 uppercase", AGENT_COLORS[agent.agent] || "text-[hsl(var(--foreground))]")}>
                {agent.agent.replace("_", " ")}
              </td>
              <td className="text-right">
                <span className={cn(
                  "text-[11px] font-mono font-bold",
                  agent.accuracy_pct >= 55 ? "text-bull" : agent.accuracy_pct >= 45 ? "text-[hsl(var(--foreground))]" : "text-bear"
                )}>
                  {agent.accuracy_pct.toFixed(1)}%
                </span>
              </td>
              <td className="text-[10px] font-mono text-[hsl(var(--muted-foreground))] text-right py-1.5">{agent.total_signals}</td>
              <td className="text-[10px] font-mono text-[hsl(var(--muted-foreground))] text-right py-1.5">{agent.avg_confidence.toFixed(0)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
