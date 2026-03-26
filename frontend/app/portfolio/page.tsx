"use client";

import { useEffect, useState, useCallback } from "react";
import { TrendingUp, TrendingDown, DollarSign, BarChart2, Trophy, AlertCircle, RefreshCw, X } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { getPortfolioSummary, getPositions, closePosition, type PortfolioSummary } from "@/lib/api";
import { formatPrice, formatPct, formatPnl, timeAgo } from "@/lib/utils";
import { cn } from "@/lib/utils";

interface Position {
  id: string;
  ticker: string;
  asset_class: string;
  direction: string;
  entry_price: number;
  current_price: number;
  quantity: number;
  stop_loss: number;
  take_profit_1: number;
  unrealized_pnl: number;
  unrealized_pnl_pct: number;
  status: string;
  opened_at: string;
  is_paper: boolean;
}

export default function PortfolioPage() {
  const [summary, setSummary]     = useState<PortfolioSummary | null>(null);
  const [positions, setPositions] = useState<Position[]>([]);
  const [loading, setLoading]     = useState(false);
  const [closing, setClosing]     = useState<string | null>(null);
  const [error, setError]         = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [pos, sum] = await Promise.all([getPositions(), getPortfolioSummary()]);
      setPositions(pos as Position[]);
      setSummary(sum);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load portfolio — sign in to view your positions");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleClose = async (posId: string) => {
    setClosing(posId);
    try {
      await closePosition(posId);
      await load(); // refresh after closing
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to close position");
    } finally {
      setClosing(null);
    }
  };

  const totalUnrealizedPnl = positions.reduce((a, p) => a + p.unrealized_pnl, 0);

  const stats = [
    {
      label: "Paper Equity",
      value: formatPrice(summary?.equity || 100000),
      icon: DollarSign,
      sub: "Paper account — $100k base",
    },
    {
      label: "Realized P&L",
      value: formatPnl(summary?.total_realized_pnl || 0),
      icon: Trophy,
      sub: `${summary?.total_trades || 0} closed trades`,
      positive: (summary?.total_realized_pnl || 0) >= 0,
    },
    {
      label: "Unrealized P&L",
      value: formatPnl(totalUnrealizedPnl),
      icon: BarChart2,
      sub: `${positions.length} open position${positions.length !== 1 ? "s" : ""}`,
      positive: totalUnrealizedPnl >= 0,
    },
    {
      label: "Win Rate",
      value: `${summary?.win_rate_pct || 0}%`,
      icon: Trophy,
      sub: "Closed trades",
    },
  ];

  return (
    <div className="max-w-7xl mx-auto px-4 py-6">

      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-lg sm:text-2xl font-bold mb-1 font-mono">PORTFOLIO</h1>
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground font-mono">
            <AlertCircle className="h-3 w-3" />
            Paper trading — no real funds. Open positions via AI signals on the Terminal.
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="secondary" className="text-xs font-mono">PAPER MODE</Badge>
          <button
            onClick={load}
            disabled={loading}
            className="p-1.5 rounded border border-border/50 text-muted-foreground hover:text-foreground hover:border-border transition-colors"
          >
            <RefreshCw className={cn("h-3.5 w-3.5", loading && "animate-spin")} />
          </button>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="mb-4 px-4 py-3 rounded border border-bear/30 bg-bear/5 text-xs font-mono text-bear flex items-center justify-between">
          <span>{error}</span>
          <button onClick={() => setError(null)}><X className="h-3 w-3" /></button>
        </div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
        {stats.map(({ label, value, icon: Icon, sub, positive }) => (
          <Card key={label} className="border-border/50">
            <CardContent className="p-4">
              <div className="flex justify-between mb-1">
                <span className="text-xs text-muted-foreground font-mono">{label}</span>
                <Icon className="h-3.5 w-3.5 text-muted-foreground" />
              </div>
              <div className={cn(
                "text-xl font-bold font-mono",
                positive === true ? "text-bull" : positive === false ? "text-bear" : "text-foreground"
              )}>
                {value}
              </div>
              <div className="text-[10px] text-muted-foreground mt-0.5 font-mono">{sub}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Positions table */}
      <Card className="border-border/50">
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 font-mono text-sm">
            OPEN POSITIONS
            <Badge variant="secondary" className="font-mono text-xs">{positions.length}</Badge>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {positions.length === 0 && !loading ? (
            <div className="flex flex-col items-center justify-center py-16 gap-3 text-center">
              <div className="text-primary/20 font-mono text-4xl">[ ]</div>
              <p className="text-xs font-mono text-muted-foreground">
                No open positions.<br />
                Generate a signal on the Terminal and click <span className="text-primary">PAPER TRADE</span> to open one.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border/50">
                    {["TICKER", "DIR", "ENTRY", "CURRENT", "QTY", "P&L", "P&L %", "SL", "TP1", "OPENED", ""].map((h) => (
                      <th key={h} className="text-left text-[10px] text-muted-foreground font-mono font-medium py-2 px-3">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {positions.map((pos) => {
                    const isLong  = pos.direction === "LONG";
                    const profit  = pos.unrealized_pnl >= 0;
                    const isClosing = closing === pos.id;
                    return (
                      <tr key={pos.id} className="border-b border-border/20 hover:bg-accent/30 transition-colors">
                        <td className="py-3 px-3 font-mono font-bold text-xs">{pos.ticker}</td>
                        <td className="py-3 px-3">
                          <span className={cn("flex items-center gap-1 text-xs font-mono font-semibold", isLong ? "text-bull" : "text-bear")}>
                            {isLong ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
                            {pos.direction}
                          </span>
                        </td>
                        <td className="py-3 px-3 font-mono text-xs text-muted-foreground">{formatPrice(pos.entry_price)}</td>
                        <td className="py-3 px-3 font-mono text-xs">{formatPrice(pos.current_price)}</td>
                        <td className="py-3 px-3 text-xs text-muted-foreground font-mono">{pos.quantity}</td>
                        <td className={cn("py-3 px-3 font-mono text-xs font-bold", profit ? "text-bull" : "text-bear")}>
                          {formatPnl(pos.unrealized_pnl)}
                        </td>
                        <td className={cn("py-3 px-3 text-xs font-mono font-semibold", profit ? "text-bull" : "text-bear")}>
                          {formatPct(pos.unrealized_pnl_pct)}
                        </td>
                        <td className="py-3 px-3 font-mono text-xs text-bear/70">{formatPrice(pos.stop_loss)}</td>
                        <td className="py-3 px-3 font-mono text-xs text-bull/70">{formatPrice(pos.take_profit_1)}</td>
                        <td className="py-3 px-3 text-[10px] text-muted-foreground font-mono">{timeAgo(pos.opened_at)}</td>
                        <td className="py-3 px-3">
                          <button
                            onClick={() => handleClose(pos.id)}
                            disabled={isClosing}
                            className="text-[10px] font-mono text-muted-foreground hover:text-bear border border-border/50 hover:border-bear/40 rounded px-2 py-0.5 transition-colors disabled:opacity-50"
                          >
                            {isClosing ? "…" : "CLOSE"}
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* How it works */}
      <div className="mt-4 p-4 rounded border border-border/30 bg-white/[0.01]">
        <div className="text-[10px] font-mono text-muted-foreground space-y-1">
          <div className="text-primary font-semibold mb-2">HOW PAPER TRADING WORKS</div>
          <div>1. Go to <span className="text-foreground">Terminal</span> → select a ticker → click <span className="text-primary">RUN AI ANALYSIS</span></div>
          <div>2. A signal card appears in the feed → click <span className="text-primary">PAPER TRADE</span> to open a position</div>
          <div>3. Your position tracks P&amp;L here in real time (simulated price drift)</div>
          <div>4. Click <span className="text-bear">CLOSE</span> to lock in realized P&amp;L</div>
        </div>
      </div>

    </div>
  );
}
