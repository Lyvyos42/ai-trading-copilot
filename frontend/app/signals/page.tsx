"use client";

import { useState } from "react";
import { Zap } from "lucide-react";
import { SignalCard } from "@/components/SignalCard";
import { generateSignal, API_URL, type Signal } from "@/lib/api";

const ASSET_CLASSES = ["stocks", "etfs", "crypto", "forex", "metals", "energy", "indices", "futures", "agriculture"];

const POPULAR_TICKERS: Record<string, string[]> = {
  stocks:      ["AAPL","NVDA","MSFT","TSLA","AMZN","GOOGL","META","JPM","GS","V","NFLX","AMD","PLTR","COIN","LLY"],
  etfs:        ["SPY","QQQ","DIA","IWM","VTI","GLD","TLT","XLK","XLE","XLF","SOXX","ARKK","EEM","GDX"],
  crypto:      ["BTC-USD","ETH-USD","SOL-USD","XRP-USD","BNB-USD","DOGE-USD","AVAX-USD","LINK-USD","MATIC-USD"],
  forex:       ["EURUSD","GBPUSD","USDJPY","AUDUSD","USDCAD","USDCHF","NZDUSD","EURGBP","EURJPY","GBPJPY","USDMXN","USDTRY"],
  metals:      ["XAUUSD","XAGUSD","XPTUSD","XPDUSD","HG=F"],
  energy:      ["USOIL","UKOIL","NATGAS","RB=F","HO=F"],
  indices:     ["US500","US100","US30","US2000","UK100","GER40","FRA40","JPN225","HK50","AUS200"],
  futures:     ["ES=F","NQ=F","YM=F","RTY=F","ZN=F","ZB=F","VX=F"],
  agriculture: ["CORN","WHEAT","SOYBEAN","COFFEE","SUGAR","COTTON","COCOA"],
};

const TICKER_ASSET_CLASS: Record<string, string> = {
  stocks: "stocks", etfs: "etfs", crypto: "crypto",
  forex: "fx", metals: "commodities", energy: "commodities",
  indices: "indices", futures: "futures", agriculture: "commodities",
};

const AGENTS = ["FundamentalAnalyst", "TechnicalAnalyst", "SentimentAnalyst", "MacroAnalyst"];

export default function SignalsPage() {
  const [signals, setSignals]       = useState<Signal[]>([]);
  const [loading, setLoading]       = useState<string | null>(null);
  const [waking, setWaking]         = useState(false);
  const [assetClass, setAssetClass] = useState("stocks");
  const [customTicker, setCustomTicker] = useState("");
  const [error, setError]           = useState("");

  async function handleGenerate(ticker: string) {
    setError("");
    setWaking(false);
    setLoading(ticker);
    // Pre-warm: ping /health — if it fails, the backend is cold starting.
    // apiFetch will auto-retry after 22s, so just show waking indicator.
    try {
      const warmRes = await fetch(`${API_URL}/health`, { signal: AbortSignal.timeout(5_000) });
      if (!warmRes.ok) setWaking(true);
    } catch {
      setWaking(true);
    }
    try {
      const signal = await generateSignal(ticker, assetClass);
      setSignals((prev) => [signal, ...prev]);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Failed to generate signal";
      setError(`${msg} [backend: ${API_URL}]`);
    } finally {
      setLoading(null);
      setWaking(false);
    }
  }

  const handleCustomSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (customTicker.trim()) {
      handleGenerate(customTicker.trim().toUpperCase());
      setCustomTicker("");
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 py-6 space-y-4">

      {/* Page header */}
      <div className="terminal-panel">
        <div className="terminal-header">
          <Zap className="h-3 w-3 text-primary" />
          <span className="terminal-label">Signal Generator — 6-Agent LangGraph Pipeline</span>
          <div className="ml-auto flex items-center gap-1.5">
            <span className="h-1.5 w-1.5 rounded-full bg-primary animate-pulse" />
            <span className="terminal-label text-primary">LIVE</span>
          </div>
        </div>
        <div className="p-4 space-y-4">

          {/* Asset class tabs */}
          <div className="flex gap-1 flex-wrap">
            {ASSET_CLASSES.map((ac) => (
              <button
                key={ac}
                onClick={() => setAssetClass(ac)}
                className={`px-3 py-1 text-[10px] font-mono font-semibold uppercase tracking-wider border transition-colors ${
                  assetClass === ac
                    ? "border-primary/50 bg-primary/10 text-primary"
                    : "border-border/40 text-muted-foreground hover:border-primary/30 hover:text-foreground"
                }`}
              >
                {ac.replace("_", " ")}
              </button>
            ))}
          </div>

          {/* Quick ticker grid */}
          <div>
            <div className="terminal-label mb-2">Quick Pick — {assetClass.replace("_", " ").toUpperCase()}</div>
            <div className="flex gap-1.5 flex-wrap">
              {(POPULAR_TICKERS[assetClass] || []).map((ticker) => (
                <button
                  key={ticker}
                  onClick={() => { setAssetClass(TICKER_ASSET_CLASS[assetClass] ?? assetClass); handleGenerate(ticker); }}
                  disabled={loading !== null}
                  className={`px-2.5 py-1 text-xs font-mono font-semibold border transition-all ${
                    loading === ticker
                      ? "border-primary bg-primary/15 text-primary animate-pulse"
                      : "border-border/40 text-muted-foreground hover:border-primary/40 hover:text-foreground"
                  }`}
                >
                  {loading === ticker ? "···" : ticker.replace("=X","").replace("-USD","").replace("=F","")}
                </button>
              ))}
            </div>
          </div>

          {/* Custom ticker */}
          <form onSubmit={handleCustomSubmit} className="flex gap-2 items-center">
            <div className="terminal-label shrink-0">CUSTOM TICKER</div>
            <div className="relative">
              <span className="absolute left-2.5 top-1/2 -translate-y-1/2 terminal-label">›</span>
              <input
                type="text"
                value={customTicker}
                onChange={(e) => setCustomTicker(e.target.value.toUpperCase())}
                placeholder="e.g. COIN, RIVN, NQ=F"
                className="pl-6 pr-3 py-1.5 bg-background border border-border/50 text-xs font-mono text-foreground focus:outline-none focus:border-primary/50 w-52 placeholder:text-muted-foreground/40"
              />
            </div>
            <button
              type="submit"
              disabled={!customTicker.trim() || loading !== null}
              className="px-3 py-1.5 text-xs font-mono font-semibold border border-primary/50 bg-primary/10 text-primary hover:bg-primary/20 disabled:opacity-40 disabled:cursor-not-allowed transition-colors flex items-center gap-1.5"
            >
              <Zap className="h-3 w-3" />
              ANALYZE
            </button>
          </form>

          {error && (
            <div className="text-xs font-mono text-bear bg-bear/10 border border-bear/20 px-3 py-2">
              ERR — {error}
            </div>
          )}
        </div>
      </div>

      {/* Pipeline running indicator */}
      {loading && (
        <div className={`terminal-panel ${waking ? "border-warn/40" : "border-primary/30"}`}>
          <div className={`terminal-header ${waking ? "bg-warn/5" : "bg-primary/5"}`}>
            {waking ? (
              <>
                <Zap className="h-3 w-3 text-warn animate-pulse" />
                <span className="terminal-label text-warn ml-1">WAKING BACKEND</span>
                <span className="ml-2 terminal-label text-foreground font-mono">{loading}</span>
                <span className="ml-auto text-[9px] font-mono text-warn/70">Render cold start — retrying in ~22s…</span>
              </>
            ) : (
              <>
                <span className="terminal-label text-primary">PIPELINE RUNNING</span>
                <span className="ml-2 terminal-label text-foreground font-mono">{loading}</span>
              </>
            )}
          </div>
          <div className="p-4">
            <div className="flex items-center gap-6">
              {AGENTS.map((agent, i) => (
                <div key={agent} className="flex items-center gap-2">
                  <span className={`h-1.5 w-1.5 rounded-full ${waking ? "bg-warn" : "bg-primary"} animate-pulse`} style={{ animationDelay: `${i * 200}ms` }} />
                  <span className="text-[10px] font-mono text-muted-foreground">{agent.replace("Analyst", "")}</span>
                </div>
              ))}
              <span className="text-[10px] font-mono text-muted-foreground ml-2">→ Debate → TraderAgent → RiskManager</span>
            </div>
          </div>
        </div>
      )}

      {/* Signal output */}
      {signals.length === 0 && !loading ? (
        <div className="terminal-panel">
          <div className="flex flex-col items-center justify-center py-20 gap-3">
            <div className="text-primary/20 font-mono text-4xl">[ ]</div>
            <span className="terminal-label">NO SIGNALS YET — SELECT A TICKER ABOVE</span>
          </div>
        </div>
      ) : (
        <div className="space-y-3">
          {signals.map((signal) => (
            <SignalCard key={signal.signal_id} signal={signal} />
          ))}
        </div>
      )}
    </div>
  );
}
