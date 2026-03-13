"use client";

import { useEffect, useState } from "react";
import { Activity, Brain, BarChart2, Newspaper, Globe, Shield, Zap, RefreshCw } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { getAgentStatus, triggerDebate, type AgentStatus } from "@/lib/api";

const AGENT_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  FundamentalAnalyst: BarChart2,
  TechnicalAnalyst: Activity,
  SentimentAnalyst: Newspaper,
  MacroAnalyst: Globe,
  RiskManager: Shield,
  TraderAgent: Brain,
};

export default function AgentsPage() {
  const [agents, setAgents] = useState<AgentStatus[]>([]);
  const [debate, setDebate] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(false);
  const [debateLoading, setDebateLoading] = useState(false);
  const [debateTicker, setDebateTicker] = useState("AAPL");

  useEffect(() => {
    loadAgents();
  }, []);

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
    <div className="max-w-7xl mx-auto px-4 py-6">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold mb-1">Agent Network</h1>
          <p className="text-sm text-muted-foreground">6 specialized AI agents in a LangGraph DAG pipeline</p>
        </div>
        <Button size="sm" variant="outline" onClick={loadAgents} disabled={loading}>
          <RefreshCw className={`h-3.5 w-3.5 mr-1 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </div>

      {/* Agent grid */}
      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4 mb-8">
        {agents.map((agent) => {
          const Icon = AGENT_ICONS[agent.name] || Brain;
          const isTrader = agent.name === "TraderAgent";
          return (
            <Card key={agent.name} className={`border-border/50 ${isTrader ? "border-primary/30 bg-primary/5" : ""}`}>
              <CardContent className="p-5">
                <div className="flex items-start gap-3 mb-3">
                  <div className={`p-2 rounded-lg ${isTrader ? "bg-primary/10 border border-primary/20" : "bg-secondary"}`}>
                    <Icon className={`h-5 w-5 ${isTrader ? "text-primary" : "text-muted-foreground"}`} />
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-semibold text-sm">{agent.name}</span>
                      <span className={`text-xs px-1.5 py-0.5 rounded font-mono ${isTrader ? "bg-primary/10 text-primary" : "bg-secondary text-secondary-foreground"}`}>
                        {isTrader ? "opus-4-6" : "sonnet-4-6"}
                      </span>
                    </div>
                    <p className="text-xs text-muted-foreground mt-0.5 leading-relaxed">{agent.role}</p>
                  </div>
                </div>

                <div className="grid grid-cols-3 gap-2 mb-3">
                  <div className="text-center p-2 rounded-md bg-background/50 border border-border/30">
                    <div className="text-sm font-bold text-bull">{agent.accuracy_7d}%</div>
                    <div className="text-[10px] text-muted-foreground">7d accuracy</div>
                  </div>
                  <div className="text-center p-2 rounded-md bg-background/50 border border-border/30">
                    <div className="text-sm font-bold font-mono">{agent.avg_latency_ms}ms</div>
                    <div className="text-[10px] text-muted-foreground">avg latency</div>
                  </div>
                  <div className="text-center p-2 rounded-md bg-background/50 border border-border/30">
                    <div className="text-sm font-bold">{agent.signals_today}</div>
                    <div className="text-[10px] text-muted-foreground">signals/day</div>
                  </div>
                </div>

                <div className="flex gap-1 flex-wrap">
                  {agent.strategies.slice(0, 3).map((s) => (
                    <span key={s} className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-secondary text-secondary-foreground">
                      {s.replace(/_/g, " ")}
                    </span>
                  ))}
                  {agent.strategies.length > 3 && (
                    <span className="text-[10px] text-muted-foreground">+{agent.strategies.length - 3}</span>
                  )}
                </div>

                <div className="flex items-center gap-1.5 mt-3">
                  <div className="h-1.5 w-1.5 rounded-full bg-bull animate-pulse-slow" />
                  <span className="text-[10px] text-muted-foreground">HEALTHY</span>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Bull/Bear debate trigger */}
      <Card className="border-border/50">
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2">
            <Zap className="h-3.5 w-3.5 text-primary" />
            Force Bull/Bear Debate
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex gap-3">
            <input
              value={debateTicker}
              onChange={(e) => setDebateTicker(e.target.value.toUpperCase())}
              placeholder="Ticker..."
              className="px-3 py-2 rounded-md border border-border/50 bg-background text-sm w-32 focus:outline-none focus:border-primary/50"
            />
            <Button onClick={handleDebate} disabled={debateLoading} size="sm">
              {debateLoading ? "Running..." : "Start Debate"}
            </Button>
          </div>

          {debate && (
            <div className="space-y-3">
              <div className="grid md:grid-cols-2 gap-3">
                <div className="p-3 rounded-lg border border-bull/20 bg-bull/5">
                  <div className="text-xs font-semibold text-bull mb-2 flex items-center gap-1">
                    <span className="h-1.5 w-1.5 rounded-full bg-bull" /> Bull Case
                  </div>
                  <p className="text-xs text-muted-foreground leading-relaxed">{debate.bull_case as string}</p>
                </div>
                <div className="p-3 rounded-lg border border-bear/20 bg-bear/5">
                  <div className="text-xs font-semibold text-bear mb-2 flex items-center gap-1">
                    <span className="h-1.5 w-1.5 rounded-full bg-bear" /> Bear Case
                  </div>
                  <p className="text-xs text-muted-foreground leading-relaxed">{debate.bear_case as string}</p>
                </div>
              </div>
              <div className="p-3 rounded-lg border border-border/50 bg-primary/5 text-center">
                <div className="text-xs text-muted-foreground mb-1">Final Verdict</div>
                <div className={`text-lg font-bold ${debate.final_direction === "LONG" ? "text-bull" : "text-bear"}`}>
                  {debate.final_direction as string} — {Math.round(debate.confidence_score as number)}% confidence
                </div>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
