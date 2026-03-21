"use client";

import { useState, useRef, useCallback } from "react";
import { Zap, Lock, X } from "lucide-react";
import { SignalCard } from "@/components/SignalCard";
import { generateSignal, API_URL, type Signal } from "@/lib/api";
import { useAuth } from "@/lib/useAuth";
import { UpgradeModal } from "@/components/UpgradeModal";

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
  const [upgradeOpen, setUpgradeOpen] = useState(false);

  const { isLoggedIn } = useAuth();
  const cancelRef = useRef(false);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastTickerRef = useRef<string>("");

  const cancelAnalysis = useCallback(() => {
    cancelRef.current = true;
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    setLoading(null);
    setWaking(false);
    setError("Analysis cancelled.");
  }, []);

  async function handleGenerate(ticker: string) {
    if (!isLoggedIn) { window.location.href = "/login"; return; }
    cancelRef.current = false;
    lastTickerRef.current = ticker;
    setError("");
    setWaking(false);
    setLoading(ticker);

    // Hard 75s timeout — auto-cancel if backend never responds
    timeoutRef.current = setTimeout(() => {
      if (cancelRef.current) return;
      cancelRef.current = true;
      setLoading(null);
      setWaking(false);
      setError("Backend took too long to respond. Render free tier may be sleeping — please retry.");
    }, 75_000);

    // Pre-warm: ping /health to detect cold start
    try {
      const warmRes = await fetch(`${API_URL}/health`, { signal: AbortSignal.timeout(5_000) });
      if (!warmRes.ok) setWaking(true);
    } catch {
      setWaking(true);
    }

    if (cancelRef.current) return;

    try {
      const signal = await generateSignal(ticker, TICKER_ASSET_CLASS[assetClass] ?? assetClass);
      if (!cancelRef.current) setSignals((prev) => [signal, ...prev]);
    } catch (e: unknown) {
      if (!cancelRef.current) {
        const msg = e instanceof Error ? e.message : "Failed to generate signal";
        const isColdStart = msg.toLowerCase().includes("fetch") || msg.toLowerCase().includes("network");
        setError(isColdStart
          ? "Backend is waking up (Render free tier, ~60s). Wait a moment and try again."
          : `${msg}`
        );
      }
    } finally {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
      if (!cancelRef.current) { setLoading(null); setWaking(false); }
    }
  }

  const handleCustomSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (customTicker.trim()) {
      // Cancel any in-progress run before starting new one
      if (loading) cancelAnalysis();
      setTimeout(() => {
        handleGenerate(customTicker.trim().toUpperCase());
        setCustomTicker("");
      }, 0);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 py-6 space-y-4">

      {/* Visitor gate banner */}
      {!isLoggedIn && (
        <div className="p-4 border border-primary/30 bg-primary/5 rounded-lg space-y-3">
          <div className="flex items-center gap-2">
            <Lock className="h-4 w-4 text-primary shrink-0" />
            <span className="text-xs font-mono font-bold text-primary">SIGN IN TO USE AI SIGNAL GENERATOR</span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-[10px] font-mono">
            <div className="p-3 rounded border border-border/40 bg-background/40">
              <div className="text-muted-foreground font-bold mb-2">FREE ACCOUNT</div>
              <ul className="space-y-1 text-muted-foreground">
                <li>• 5 AI signals / day</li>
                <li>• Stocks &amp; ETFs only</li>
                <li>• Paper trading portfolio</li>
                <li>• Market intel &amp; news</li>
              </ul>
            </div>
            <div className="p-3 rounded border border-primary/40 bg-primary/5">
              <div className="text-primary font-bold mb-2">RETAIL — $49/mo</div>
              <ul className="space-y-1 text-muted-foreground">
                <li>• Unlimited signals</li>
                <li>• All 8 asset classes</li>
                <li>• All 80+ strategies</li>
                <li>• Bull/Bear agent debate</li>
              </ul>
            </div>
            <div className="p-3 rounded border border-yellow-400/30 bg-yellow-400/5">
              <div className="text-yellow-400 font-bold mb-2">PRO — $199/mo</div>
              <ul className="space-y-1 text-muted-foreground">
                <li>• Everything in Retail</li>
                <li>• Custom agent tuning</li>
                <li>• API &amp; webhook access</li>
                <li>• Priority support</li>
              </ul>
            </div>
          </div>
          <div className="flex gap-2">
            <a href="/login" className="px-4 py-1.5 text-[10px] font-mono font-bold border border-primary/50 bg-primary/10 text-primary hover:bg-primary/20 transition-colors rounded">
              SIGN IN FREE
            </a>
            <a href="/pricing" className="px-4 py-1.5 text-[10px] font-mono font-bold border border-border/50 text-muted-foreground hover:text-foreground transition-colors rounded">
              SEE PRICING
            </a>
          </div>
        </div>
      )}

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
              disabled={!customTicker.trim()}
              className="px-3 py-1.5 text-xs font-mono font-semibold border border-primary/50 bg-primary/10 text-primary hover:bg-primary/20 disabled:opacity-40 disabled:cursor-not-allowed transition-colors flex items-center gap-1.5"
            >
              <Zap className="h-3 w-3" />
              ANALYZE
            </button>
          </form>

          {error && (
            <div className="flex items-center gap-3 text-xs font-mono text-bear bg-bear/10 border border-bear/20 px-3 py-2">
              <span className="flex-1">ERR — {error}</span>
              {lastTickerRef.current && (
                <button
                  onClick={() => handleGenerate(lastTickerRef.current)}
                  className="shrink-0 px-2 py-0.5 text-[10px] font-bold border border-bear/40 hover:bg-bear/20 transition-colors rounded"
                >
                  RETRY
                </button>
              )}
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
                <span className="mx-auto text-[9px] font-mono text-warn/70">Render cold start — auto-retrying (~26s max)…</span>
              </>
            ) : (
              <>
                <span className="terminal-label text-primary">PIPELINE RUNNING</span>
                <span className="ml-2 terminal-label text-foreground font-mono">{loading}</span>
              </>
            )}
            <button
              onClick={cancelAnalysis}
              className="ml-auto flex items-center gap-1 text-[9px] font-mono text-muted-foreground hover:text-bear border border-border/40 hover:border-bear/40 px-2 py-0.5 rounded transition-colors"
            >
              <X className="h-2.5 w-2.5" /> CANCEL
            </button>
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

      <UpgradeModal
        isOpen={upgradeOpen}
        onClose={() => setUpgradeOpen(false)}
        feature="Unlimited AI Signals"
        requiredTier="retail"
        reason="Free accounts can run 3 AI analyses per day. Upgrade to Retail for unlimited signals across all asset classes."
      />
    </div>
  );
}
