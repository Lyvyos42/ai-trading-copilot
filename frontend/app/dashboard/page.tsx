"use client";

import { useState, useEffect } from "react";
import { RefreshCw, TrendingUp, Activity, Zap, DollarSign } from "lucide-react";
import { SignalCard } from "@/components/SignalCard";
import { TradingViewChart } from "@/components/TradingViewChart";
import { AgentStatusPanel } from "@/components/AgentStatus";
import { generateSignal, listSignals, getAgentStatus, wakeBackend, type Signal, type AgentStatus } from "@/lib/api";
import { ScannerPanel } from "@/components/ScannerPanel";
import { formatPrice } from "@/lib/utils";
import { SymbolSearch } from "@/components/SymbolSearch";
import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/useAuth";
import { UpgradeModal } from "@/components/UpgradeModal";

const WATCHLIST = ["AAPL", "NVDA", "BTC-USD", "EURUSD=X", "XAUUSD", "US500", "USDJPY=X"];


export default function DashboardPage() {
  const [signals, setSignals]               = useState<Signal[]>([]);
  const [agents, setAgents]                 = useState<AgentStatus[]>([]);
  const [selectedSignal, setSelectedSignal] = useState<Signal | null>(null);
  const [loading, setLoading]               = useState(false);
  const [analysisError, setAnalysisError]   = useState<string | null>(null);
  const [tradeOpened, setTradeOpened]       = useState(false);
  const [activeTicker, setActiveTicker]     = useState(() =>
    (typeof window !== "undefined" && localStorage.getItem("dashboard_ticker")) || "AAPL"
  );
const [upgradeOpen, setUpgradeOpen]       = useState(false);

  const { isLoggedIn } = useAuth();

  useEffect(() => {
    wakeBackend();
    loadData();
  }, []);

  useEffect(() => {
    localStorage.setItem("dashboard_ticker", activeTicker);
  }, [activeTicker]);

  async function loadData() {
    const [sigs, agentData] = await Promise.allSettled([listSignals(10), getAgentStatus()]);
    if (sigs.status === "fulfilled") {
      // Deduplicate: keep only the most recent signal per ticker
      const seen = new Set<string>();
      const deduped = sigs.value.filter(s => {
        if (seen.has(s.ticker)) return false;
        seen.add(s.ticker);
        return true;
      });
      setSignals(deduped);
      if (deduped.length > 0 && !selectedSignal) setSelectedSignal(deduped[0]);
    }
    if (agentData.status === "fulfilled") setAgents(agentData.value.agents);
  }

  async function handleGenerate(ticker?: string) {
    const t = ticker || activeTicker;
    setLoading(true);
    setAnalysisError(null);
    setActiveTicker(t);
    try {
      const signal = await generateSignal(t);
      // Deduplicate: replace existing signal for same ticker, keep latest
      setSignals((prev) => [signal, ...prev.filter(s => s.ticker !== signal.ticker).slice(0, 8)]);
      setSelectedSignal(signal);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Analysis failed";
      // Distinguish network errors (cold start) from API errors
      const isColdStart = msg.toLowerCase().includes("fetch") || msg.toLowerCase().includes("network");
      setAnalysisError(
        isColdStart
          ? "Backend is waking up (Render free tier). This takes ~60s on first use. Please wait and try again."
          : msg
      );
    } finally {
      setLoading(false);
    }
  }

  const activeSignals = signals.filter((s) => s.status === "ACTIVE").length;
  const activeTickerLocked = signals.some(
    s => s.ticker === activeTicker && s.status === "ACTIVE"
  );
  const avgConf       = signals.length
    ? (signals.reduce((a, s) => a + s.confidence_score, 0) / signals.length).toFixed(0)
    : null;
  const healthyAgents = agents.filter((a) => a.status === "HEALTHY").length;

  return (
    <div className="h-[calc(100vh-72px)] flex flex-col bg-background overflow-hidden">

      {/* ── TOP STATS BAR ──────────────────────────────────────────── */}
      <div className="grid grid-cols-2 md:flex items-stretch border-b border-border bg-[hsl(0_0%_3%)] shrink-0">
        {[
          {
            label: "ACTIVE SIGNALS",
            value: activeSignals,
            suffix: null,
            icon: Zap,
            color: "text-primary",
          },
          {
            label: "AVG CONFIDENCE",
            value: avgConf ?? "—",
            suffix: avgConf ? "%" : null,
            icon: TrendingUp,
            color: "text-bull",
          },
          {
            label: "AGENTS ONLINE",
            value: `${healthyAgents}`,
            suffix: "/6",
            icon: Activity,
            color: "text-bull",
          },
          {
            label: "PAPER EQUITY",
            value: "$100,000",
            suffix: null,
            icon: DollarSign,
            color: "text-primary",
          },
        ].map(({ label, value, suffix, icon: Icon, color }, i) => (
          <div
            key={label}
            className={cn(
              "flex-1 flex items-center justify-between px-4 py-2 border-r border-border last:border-r-0",
              i % 2 === 0 ? "bg-transparent" : "bg-white/[0.01]"
            )}
          >
            <div>
              <div className="terminal-label">{label}</div>
              <div className={`font-mono text-sm font-bold mt-0.5 ${color}`}>
                {value}
                {suffix && <span className="text-muted-foreground text-xs">{suffix}</span>}
              </div>
            </div>
            <Icon className={`h-4 w-4 ${color} opacity-60`} />
          </div>
        ))}
      </div>

      {/* ── MAIN PANELS ──────────────────────────────────────────────── */}
      <div className="flex flex-col lg:flex-row flex-1 min-h-0 overflow-hidden">

        {/* LEFT — Chart + Controls */}
        <div className="flex flex-col flex-1 min-w-0 min-h-0 lg:border-r border-border border-b lg:border-b-0">

          {/* Control bar */}
          <div className="flex items-center gap-2 px-3 py-2 border-b border-border bg-[hsl(0_0%_3%)] shrink-0 flex-wrap">
            <SymbolSearch value={activeTicker} onChange={setActiveTicker} />

            <div className="flex items-center gap-1 flex-wrap">
              {WATCHLIST.map((ticker) => {
                const label = ticker.replace("=X","").replace("-USD","").replace("=F","").replace("^","");
                return (
                  <button
                    key={ticker}
                    onClick={() => setActiveTicker(ticker)}
                    className={cn(
                      "px-2 py-0.5 rounded text-[10px] font-mono font-bold border transition-colors",
                      activeTicker === ticker
                        ? "bg-primary/10 border-primary/50 text-primary"
                        : "border-border/50 text-muted-foreground hover:border-primary/30 hover:text-primary"
                    )}
                  >
                    {label}
                  </button>
                );
              })}
            </div>

            <div className="ml-auto flex items-center gap-2">
              <button
                onClick={() => {
                  if (!isLoggedIn) { window.location.href = "/login"; return; }
                  if (activeTickerLocked) return;
                  handleGenerate();
                }}
                disabled={loading || activeTickerLocked}
                className={cn(
                  "flex items-center gap-1.5 px-3 py-1 rounded text-[10px] font-mono font-bold border transition-colors",
                  loading || activeTickerLocked
                    ? "border-border/40 text-muted-foreground/50 cursor-not-allowed"
                    : "border-primary/50 text-primary hover:bg-primary/10"
                )}
              >
                <Activity className={`h-3 w-3 ${loading ? "animate-spin" : ""}`} />
                {loading ? "ANALYZING… (up to 60s)" : activeTickerLocked ? "SIGNAL ACTIVE — MARK WIN/LOSS" : "RUN AI ANALYSIS"}
              </button>
              <button
                onClick={loadData}
                disabled={loading}
                className="p-1.5 rounded border border-border/50 text-muted-foreground hover:text-foreground hover:border-border transition-colors"
              >
                <RefreshCw className="h-3 w-3" />
              </button>
            </div>
          </div>

          {/* Chart area */}
          <div className="flex-1 flex flex-col min-h-0 relative">
            <div className="flex-1 min-h-0 overflow-hidden" style={{ minHeight: "300px" }}>
              <TradingViewChart ticker={activeTicker} fillContainer />
            </div>
          </div>
        </div>

        {/* CENTER — Signal Feed */}
        <div className="flex flex-col lg:w-72 shrink-0 border-t lg:border-t-0 lg:border-r border-border max-h-64 lg:max-h-none overflow-hidden">
          <div className="terminal-header shrink-0">
            <span className="terminal-label">SIGNAL FEED</span>
            {loading && (
              <div className="ml-auto flex items-center gap-1 text-[9px] font-mono text-primary">
                <Activity className="h-2.5 w-2.5 animate-spin" />
                RUNNING
              </div>
            )}
          </div>

          <div className="flex-1 overflow-y-auto">
            {analysisError && (
              <div className="mx-3 mt-3 px-3 py-2 rounded border border-bear/30 bg-bear/5 text-[10px] font-mono text-bear">
                {analysisError}
              </div>
            )}
            {signals.length === 0 && !loading && !analysisError && (
              <div className="flex flex-col items-center justify-center h-40 text-center px-4">
                <Zap className="h-6 w-6 text-muted-foreground/30 mb-2" />
                <p className="text-[10px] font-mono text-muted-foreground">
                  No signals yet.<br />Select a ticker and run analysis.
                </p>
              </div>
            )}
            {tradeOpened && (
              <div className="mx-3 mt-3 px-3 py-2 rounded border border-bull/30 bg-bull/5 text-[10px] font-mono text-bull flex items-center justify-between">
                <span>✓ Paper position opened</span>
                <a href="/portfolio" className="underline text-bull hover:text-bull/80">View Portfolio →</a>
              </div>
            )}
            {signals.map((signal) => (
              <div
                key={signal.signal_id}
                onClick={() => { setSelectedSignal(signal); setActiveTicker(signal.ticker); }}
                className={cn(
                  "cursor-pointer border-b border-border/50 transition-colors",
                  selectedSignal?.signal_id === signal.signal_id
                    ? "bg-primary/5 border-l-2 border-l-primary"
                    : "hover:bg-white/[0.02]"
                )}
              >
                <SignalCard
                  signal={signal}
                  compact
                  onExecute={() => setTradeOpened(true)}
                  onResolve={(id, outcome) => {
                    setSignals(prev => prev.map(s => s.signal_id === id ? { ...s, status: outcome } : s));
                  }}
                />
              </div>
            ))}
          </div>
        </div>

        {/* RIGHT SIDEBAR — Agents + Pipeline (desktop only) */}
        <div className="hidden xl:flex flex-col w-64 shrink-0">
          <div className="terminal-header shrink-0">
            <span className="terminal-label">AGENT NETWORK</span>
            <span className="ml-auto font-mono text-[9px] text-bull">{healthyAgents}/6 HEALTHY</span>
          </div>

          <div className="flex-1 overflow-y-auto">
            <AgentStatusPanel agents={agents.length > 0 ? agents : PLACEHOLDER_AGENTS} compact />

            {/* Pipeline card */}
            <div className="border-t border-border mt-2 pt-2 px-3 pb-3">
              <div className="terminal-label mb-2">PIPELINE STAGES</div>
              {[
                { n: "1", name: "Parallel Analysis",  detail: "4 agents concurrent" },
                { n: "2", name: "Bull/Bear Debate",   detail: "Researcher debate" },
                { n: "3", name: "Trade Decision",     detail: "TraderAgent (Opus 4)" },
                { n: "4", name: "Risk Check",         detail: "Kelly + exposure" },
                { n: "5", name: "Fund Manager",       detail: "Final approval" },
              ].map(({ n, name, detail }) => (
                <div key={n} className="flex items-start gap-2 mb-2">
                  <div className="h-4 w-4 rounded-full bg-primary/10 border border-primary/20 flex items-center justify-center shrink-0 mt-0.5">
                    <span className="text-[8px] font-bold text-primary">{n}</span>
                  </div>
                  <div>
                    <div className="text-[10px] font-medium text-foreground leading-tight">{name}</div>
                    <div className="text-[9px] text-muted-foreground">{detail}</div>
                  </div>
                </div>
              ))}
            </div>

            {/* Agent Scanner */}
            <div className="border-t border-border">
              <ScannerPanel />
            </div>
          </div>
        </div>
      </div>

      <UpgradeModal
        isOpen={upgradeOpen}
        onClose={() => setUpgradeOpen(false)}
        feature="Unlimited AI Analysis"
        requiredTier="retail"
        reason="Free accounts can run 3 AI analyses per day. Upgrade to Retail for unlimited signals across all asset classes."
      />
    </div>
  );
}

const PLACEHOLDER_AGENTS: AgentStatus[] = [
  { name: "FundamentalAnalyst", role: "P/E, P/B, earnings momentum",  model: "claude-sonnet-4-6", strategies: ["3.2", "3.3"],           status: "HEALTHY", avg_latency_ms: 1200, signals_today: 42, accuracy_7d: 61.5, last_active: new Date().toISOString() },
  { name: "TechnicalAnalyst",   role: "EMA, RSI, momentum, Z-score",  model: "claude-sonnet-4-6", strategies: ["3.1", "3.9", "3.11"],    status: "HEALTHY", avg_latency_ms:  950, signals_today: 67, accuracy_7d: 64.2, last_active: new Date().toISOString() },
  { name: "SentimentAnalyst",   role: "News NLP, social media",       model: "claude-sonnet-4-6", strategies: ["18.3"],                  status: "HEALTHY", avg_latency_ms: 1800, signals_today: 38, accuracy_7d: 58.9, last_active: new Date().toISOString() },
  { name: "MacroAnalyst",       role: "GDP, CPI, Fed, carry",         model: "claude-sonnet-4-6", strategies: ["19.2", "8.2"],           status: "HEALTHY", avg_latency_ms: 2100, signals_today: 25, accuracy_7d: 56.3, last_active: new Date().toISOString() },
  { name: "RiskManager",        role: "Kelly, drawdown, correlation",  model: "claude-sonnet-4-6", strategies: ["3.18", "6.5"],          status: "HEALTHY", avg_latency_ms:  800, signals_today: 88, accuracy_7d: 72.1, last_active: new Date().toISOString() },
  { name: "TraderAgent",        role: "Final decision & sizing",       model: "claude-opus-4-6",   strategies: ["3.20"],                  status: "HEALTHY", avg_latency_ms: 3800, signals_today: 55, accuracy_7d: 66.8, last_active: new Date().toISOString() },
];
