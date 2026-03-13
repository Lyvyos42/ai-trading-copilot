"use client";

import { useState } from "react";
import { Zap, Search, Filter } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { SignalCard } from "@/components/SignalCard";
import { generateSignal, type Signal } from "@/lib/api";

const ASSET_CLASSES = ["stocks", "etfs", "crypto", "fx", "commodities", "fixed_income"];
const POPULAR_TICKERS: Record<string, string[]> = {
  stocks: ["AAPL", "NVDA", "MSFT", "TSLA", "AMZN", "GOOGL", "META", "JPM"],
  etfs: ["SPY", "QQQ", "IWM", "GLD", "TLT", "XLK", "XLE", "VIX"],
  crypto: ["BTC", "ETH", "SOL", "XRP", "DOGE"],
  fx: ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD"],
  commodities: ["GLD", "OIL", "WHEAT", "COPPER"],
  fixed_income: ["TLT", "IEF", "HYG", "LQD"],
};

export default function SignalsPage() {
  const [signals, setSignals] = useState<Signal[]>([]);
  const [loading, setLoading] = useState<string | null>(null);
  const [assetClass, setAssetClass] = useState("stocks");
  const [customTicker, setCustomTicker] = useState("");
  const [error, setError] = useState("");

  async function handleGenerate(ticker: string) {
    setError("");
    setLoading(ticker);
    try {
      const signal = await generateSignal(ticker, assetClass);
      setSignals((prev) => [signal, ...prev]);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to generate signal");
    } finally {
      setLoading(null);
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
    <div className="max-w-7xl mx-auto px-4 py-6">
      <div className="mb-6">
        <h1 className="text-2xl font-bold mb-1">Signal Generator</h1>
        <p className="text-muted-foreground text-sm">
          Trigger the 6-agent pipeline on any ticker. Results include full reasoning chain from all agents.
        </p>
      </div>

      {/* Controls */}
      <Card className="border-border/50 mb-6">
        <CardContent className="p-4 space-y-4">
          {/* Asset class selector */}
          <div className="flex gap-2 flex-wrap">
            {ASSET_CLASSES.map((ac) => (
              <button
                key={ac}
                onClick={() => setAssetClass(ac)}
                className={`px-3 py-1 rounded-full text-xs font-medium border transition-colors ${
                  assetClass === ac ? "bg-primary/10 border-primary/40 text-primary" : "border-border/50 text-muted-foreground hover:border-primary/30"
                }`}
              >
                {ac}
              </button>
            ))}
          </div>

          {/* Quick ticker buttons */}
          <div className="flex gap-2 flex-wrap">
            {(POPULAR_TICKERS[assetClass] || []).map((ticker) => (
              <button
                key={ticker}
                onClick={() => handleGenerate(ticker)}
                disabled={loading !== null}
                className={`px-3 py-1.5 rounded-md text-xs font-mono font-semibold border transition-all ${
                  loading === ticker
                    ? "bg-primary/20 border-primary text-primary animate-pulse"
                    : "border-border/50 text-muted-foreground hover:border-primary/40 hover:text-foreground"
                }`}
              >
                {loading === ticker ? "..." : ticker}
              </button>
            ))}
          </div>

          {/* Custom ticker form */}
          <form onSubmit={handleCustomSubmit} className="flex gap-2">
            <div className="relative flex-1 max-w-xs">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
              <input
                type="text"
                value={customTicker}
                onChange={(e) => setCustomTicker(e.target.value.toUpperCase())}
                placeholder="Custom ticker..."
                className="w-full pl-8 pr-3 py-2 rounded-md border border-border/50 bg-background text-sm focus:outline-none focus:border-primary/50 placeholder:text-muted-foreground"
              />
            </div>
            <Button type="submit" size="sm" disabled={!customTicker.trim() || loading !== null}>
              <Zap className="h-3.5 w-3.5 mr-1" />
              Analyze
            </Button>
          </form>

          {error && <div className="text-xs text-red-400 bg-red-400/10 px-3 py-2 rounded-md">{error}</div>}
        </CardContent>
      </Card>

      {/* Signal list */}
      {loading && (
        <Card className="border-primary/30 border-dashed mb-4">
          <CardContent className="p-6 text-center">
            <div className="flex items-center justify-center gap-2 text-sm text-primary mb-2">
              <Zap className="h-4 w-4 animate-pulse" />
              Running multi-agent pipeline for {loading}...
            </div>
            <div className="flex justify-center gap-3 text-xs text-muted-foreground">
              {["Fundamental", "Technical", "Sentiment", "Macro"].map((a) => (
                <span key={a} className="flex items-center gap-1">
                  <span className="h-1.5 w-1.5 rounded-full bg-primary animate-pulse-slow" />
                  {a}
                </span>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      <div className="space-y-3">
        {signals.length === 0 && !loading && (
          <div className="text-center py-16 text-muted-foreground">
            <Zap className="h-8 w-8 mx-auto mb-3 opacity-20" />
            <p className="text-sm">Select a ticker to run the agent pipeline</p>
          </div>
        )}
        {signals.map((signal) => (
          <SignalCard key={signal.signal_id} signal={signal} />
        ))}
      </div>
    </div>
  );
}
