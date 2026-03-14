"use client";

import { useState, useEffect } from "react";
import { RefreshCw, TrendingUp, Activity, Zap, DollarSign } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { SignalCard } from "@/components/SignalCard";
import { TradingChart } from "@/components/TradingChart";
import { AgentStatusPanel } from "@/components/AgentStatus";
import { generateSignal, listSignals, getAgentStatus, type Signal, type AgentStatus } from "@/lib/api";
import { formatPrice, formatPct } from "@/lib/utils";
import { SymbolSearch } from "@/components/SymbolSearch";

const WATCHLIST = ["AAPL", "NVDA", "TSLA", "SPY", "BTC-USD", "EURUSD=X", "GC=F"];

export default function DashboardPage() {
  const [signals, setSignals] = useState<Signal[]>([]);
  const [agents, setAgents] = useState<AgentStatus[]>([]);
  const [selectedSignal, setSelectedSignal] = useState<Signal | null>(null);
  const [loading, setLoading] = useState(false);
  const [activeTicker, setActiveTicker] = useState("AAPL");

  useEffect(() => {
    loadData();
  }, []);

  async function loadData() {
    const [sigs, agentData] = await Promise.allSettled([listSignals(10), getAgentStatus()]);
    if (sigs.status === "fulfilled") {
      setSignals(sigs.value);
      if (sigs.value.length > 0 && !selectedSignal) setSelectedSignal(sigs.value[0]);
    }
    if (agentData.status === "fulfilled") setAgents(agentData.value.agents);
  }

  function handleTickerChange(ticker: string) {
    setActiveTicker(ticker);
  }

  async function handleGenerate(ticker?: string) {
    const t = ticker || activeTicker;
    setLoading(true);
    setActiveTicker(t);
    try {
      const signal = await generateSignal(t);
      setSignals((prev) => [signal, ...prev.slice(0, 9)]);
      setSelectedSignal(signal);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  const stats = [
    { label: "Active Signals", value: signals.filter((s) => s.status === "ACTIVE").length, icon: Zap, color: "text-primary" },
    { label: "Avg Confidence", value: signals.length ? `${(signals.reduce((a, s) => a + s.confidence_score, 0) / signals.length).toFixed(0)}%` : "—", icon: TrendingUp, color: "text-bull" },
    { label: "Agents Online", value: `${agents.filter((a) => a.status === "HEALTHY").length}/6`, icon: Activity, color: "text-bull" },
    { label: "Paper Equity", value: "$100,000", icon: DollarSign, color: "text-primary" },
  ];

  return (
    <div className="max-w-7xl mx-auto px-4 py-6">
      {/* Stats row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
        {stats.map(({ label, value, icon: Icon, color }) => (
          <Card key={label} className="border-border/50">
            <CardContent className="p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs text-muted-foreground">{label}</span>
                <Icon className={`h-4 w-4 ${color}`} />
              </div>
              <div className="text-xl font-bold font-mono">{value}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid lg:grid-cols-[1fr_320px] gap-6">
        {/* Left column */}
        <div className="space-y-4">
          {/* Symbol search + quick picks + analyze */}
          <Card className="border-border/50">
            <CardContent className="p-4">
              <div className="flex items-center gap-2 flex-wrap">
                {/* TradingView-style symbol search */}
                <SymbolSearch value={activeTicker} onChange={handleTickerChange} />

                {/* Quick pick chips */}
                <div className="flex items-center gap-1.5 flex-wrap">
                  {WATCHLIST.map((ticker) => (
                    <button
                      key={ticker}
                      onClick={() => handleTickerChange(ticker)}
                      className={`px-2.5 py-1 rounded-md text-xs font-mono font-medium border transition-colors ${
                        activeTicker === ticker
                          ? "bg-primary/10 border-primary/40 text-primary"
                          : "border-border/50 hover:border-primary/30 hover:text-primary text-muted-foreground"
                      }`}
                    >
                      {ticker.replace("=X","").replace("-USD","").replace("=F","").replace("^","")}
                    </button>
                  ))}
                </div>

                <div className="ml-auto flex items-center gap-2">
                  <Button
                    size="sm"
                    className="h-8 text-xs gap-1.5 bg-primary hover:bg-primary/90"
                    onClick={() => handleGenerate()}
                    disabled={loading}
                  >
                    <Activity className={`h-3 w-3 ${loading ? "animate-spin" : ""}`} />
                    {loading ? "Analyzing…" : "Run AI Analysis"}
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-8 text-xs"
                    onClick={loadData}
                    disabled={loading}
                  >
                    <RefreshCw className="h-3 w-3" />
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Chart */}
          <div className="space-y-2">
            <div className="flex items-center justify-between px-1">
              <h2 className="text-sm font-semibold">
                {selectedSignal ? `${selectedSignal.ticker} — ${selectedSignal.direction}` : "Price Chart"}
              </h2>
              {selectedSignal && (
                <span className="text-xs text-muted-foreground font-mono">
                  Entry {formatPrice(selectedSignal.entry_price)} → TP1 {formatPrice(selectedSignal.take_profit_1)}
                </span>
              )}
            </div>
            <TradingChart ticker={activeTicker} signal={selectedSignal} />
          </div>

          {/* Signal feed */}
          <div className="space-y-2">
            <div className="flex items-center justify-between px-1">
              <h2 className="text-sm font-semibold">Recent Signals</h2>
              {loading && (
                <div className="flex items-center gap-1 text-xs text-primary">
                  <Activity className="h-3 w-3 animate-spin" />
                  Running pipeline...
                </div>
              )}
            </div>
            {signals.length === 0 && !loading && (
              <Card className="border-border/50 border-dashed">
                <CardContent className="p-8 text-center text-muted-foreground text-sm">
                  Click a ticker above to generate your first signal
                </CardContent>
              </Card>
            )}
            {signals.map((signal) => (
              <div
                key={signal.signal_id}
                onClick={() => setSelectedSignal(signal)}
                className="cursor-pointer"
              >
                <SignalCard signal={signal} />
              </div>
            ))}
          </div>
        </div>

        {/* Right sidebar */}
        <div className="space-y-4">
          <AgentStatusPanel agents={agents.length > 0 ? agents : PLACEHOLDER_AGENTS} />

          {/* Pipeline info card */}
          <Card className="border-border/50">
            <CardHeader className="pb-2">
              <CardTitle>Pipeline Stages</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {[
                { stage: "1", name: "Parallel Analysis", detail: "4 agents run concurrently" },
                { stage: "2", name: "Bull/Bear Debate", detail: "Researcher agents argue both sides" },
                { stage: "3", name: "Trade Decision", detail: "TraderAgent synthesizes (Opus 4)" },
                { stage: "4", name: "Risk Check", detail: "Kelly sizing + exposure limits" },
                { stage: "5", name: "Fund Manager", detail: "Final approval & packaging" },
              ].map(({ stage, name, detail }) => (
                <div key={stage} className="flex items-start gap-2.5">
                  <div className="h-5 w-5 rounded-full bg-primary/10 border border-primary/20 flex items-center justify-center shrink-0 mt-0.5">
                    <span className="text-[10px] font-bold text-primary">{stage}</span>
                  </div>
                  <div>
                    <div className="text-xs font-medium">{name}</div>
                    <div className="text-[10px] text-muted-foreground">{detail}</div>
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

// Placeholder agents shown before API responds
const PLACEHOLDER_AGENTS = [
  { name: "FundamentalAnalyst", role: "P/E, P/B, earnings momentum", model: "claude-sonnet-4-6", strategies: ["3.2", "3.3"], status: "HEALTHY", avg_latency_ms: 1200, signals_today: 42, accuracy_7d: 61.5, last_active: new Date().toISOString() },
  { name: "TechnicalAnalyst", role: "EMA, RSI, momentum, Z-score", model: "claude-sonnet-4-6", strategies: ["3.1", "3.9", "3.11-3.13"], status: "HEALTHY", avg_latency_ms: 950, signals_today: 67, accuracy_7d: 64.2, last_active: new Date().toISOString() },
  { name: "SentimentAnalyst", role: "News NLP, social media", model: "claude-sonnet-4-6", strategies: ["18.3"], status: "HEALTHY", avg_latency_ms: 1800, signals_today: 38, accuracy_7d: 58.9, last_active: new Date().toISOString() },
  { name: "MacroAnalyst", role: "GDP, CPI, Fed, carry", model: "claude-sonnet-4-6", strategies: ["19.2", "8.2"], status: "HEALTHY", avg_latency_ms: 2100, signals_today: 25, accuracy_7d: 56.3, last_active: new Date().toISOString() },
  { name: "RiskManager", role: "Kelly, drawdown, correlation", model: "claude-sonnet-4-6", strategies: ["3.18", "6.5"], status: "HEALTHY", avg_latency_ms: 800, signals_today: 88, accuracy_7d: 72.1, last_active: new Date().toISOString() },
  { name: "TraderAgent", role: "Final decision & sizing", model: "claude-opus-4-6", strategies: ["3.20"], status: "HEALTHY", avg_latency_ms: 3800, signals_today: 55, accuracy_7d: 66.8, last_active: new Date().toISOString() },
];
