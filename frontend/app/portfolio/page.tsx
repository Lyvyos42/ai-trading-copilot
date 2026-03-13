"use client";

import { useEffect, useState } from "react";
import { TrendingUp, TrendingDown, DollarSign, BarChart2, Trophy, AlertCircle } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { getPortfolioSummary, type PortfolioSummary } from "@/lib/api";
import { formatPrice, formatPct, formatPnl } from "@/lib/utils";

// Mock positions for display (replace with API call once auth is set up)
const MOCK_POSITIONS = [
  { id: "1", ticker: "AAPL", direction: "LONG", entry_price: 172.50, current_price: 178.20, quantity: 10, unrealized_pnl: 57.0, unrealized_pnl_pct: 3.3, status: "OPEN", opened_at: new Date(Date.now() - 86400000 * 2).toISOString(), is_paper: true },
  { id: "2", ticker: "NVDA", direction: "LONG", entry_price: 485.00, current_price: 512.75, quantity: 5, unrealized_pnl: 138.75, unrealized_pnl_pct: 5.72, status: "OPEN", opened_at: new Date(Date.now() - 86400000).toISOString(), is_paper: true },
  { id: "3", ticker: "TSLA", direction: "SHORT", entry_price: 248.30, current_price: 241.10, quantity: 8, unrealized_pnl: 57.6, unrealized_pnl_pct: 2.9, status: "OPEN", opened_at: new Date(Date.now() - 86400000 * 3).toISOString(), is_paper: true },
  { id: "4", ticker: "SPY", direction: "LONG", entry_price: 520.00, current_price: 516.80, quantity: 3, unrealized_pnl: -9.6, unrealized_pnl_pct: -0.62, status: "OPEN", opened_at: new Date(Date.now() - 3600000 * 5).toISOString(), is_paper: true },
];

export default function PortfolioPage() {
  const [summary, setSummary] = useState<PortfolioSummary | null>(null);

  useEffect(() => {
    getPortfolioSummary().then(setSummary).catch(() => {
      setSummary({ open_positions: 4, total_trades: 12, win_rate_pct: 66.7, total_realized_pnl: 843.50, equity: 100843.50, paper_mode: true });
    });
  }, []);

  const totalUnrealizedPnl = MOCK_POSITIONS.reduce((a, p) => a + p.unrealized_pnl, 0);

  const stats = [
    { label: "Paper Equity", value: formatPrice(summary?.equity || 100000), icon: DollarSign, sub: "Paper account" },
    { label: "Realized P&L", value: formatPnl(summary?.total_realized_pnl || 0), icon: Trophy, sub: `${summary?.total_trades || 0} closed trades`, positive: (summary?.total_realized_pnl || 0) >= 0 },
    { label: "Unrealized P&L", value: formatPnl(totalUnrealizedPnl), icon: BarChart2, sub: `${MOCK_POSITIONS.length} open positions`, positive: totalUnrealizedPnl >= 0 },
    { label: "Win Rate", value: `${summary?.win_rate_pct || 0}%`, icon: BarChart2, sub: "Closed trades" },
  ];

  return (
    <div className="max-w-7xl mx-auto px-4 py-6">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold mb-1">Portfolio</h1>
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <AlertCircle className="h-3 w-3" />
            Paper trading mode — no real funds at risk
          </div>
        </div>
        <Badge variant="secondary" className="text-xs">Paper Mode</Badge>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
        {stats.map(({ label, value, icon: Icon, sub, positive }) => (
          <Card key={label} className="border-border/50">
            <CardContent className="p-4">
              <div className="flex justify-between mb-1">
                <span className="text-xs text-muted-foreground">{label}</span>
                <Icon className="h-3.5 w-3.5 text-muted-foreground" />
              </div>
              <div className={`text-xl font-bold font-mono ${positive === true ? "text-bull" : positive === false ? "text-bear" : ""}`}>
                {value}
              </div>
              <div className="text-[10px] text-muted-foreground mt-0.5">{sub}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Positions table */}
      <Card className="border-border/50">
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2">
            Open Positions
            <Badge variant="secondary">{MOCK_POSITIONS.length}</Badge>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border/50">
                  {["Ticker", "Dir", "Entry", "Current", "Qty", "P&L", "P&L %", "Opened", ""].map((h) => (
                    <th key={h} className="text-left text-xs text-muted-foreground font-medium py-2 px-3">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {MOCK_POSITIONS.map((pos) => {
                  const isLong = pos.direction === "LONG";
                  const profit = pos.unrealized_pnl >= 0;
                  return (
                    <tr key={pos.id} className="border-b border-border/20 hover:bg-accent/30 transition-colors">
                      <td className="py-3 px-3 font-mono font-semibold">{pos.ticker}</td>
                      <td className="py-3 px-3">
                        <span className={`flex items-center gap-1 text-xs font-medium ${isLong ? "text-bull" : "text-bear"}`}>
                          {isLong ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
                          {pos.direction}
                        </span>
                      </td>
                      <td className="py-3 px-3 font-mono text-xs">{formatPrice(pos.entry_price)}</td>
                      <td className="py-3 px-3 font-mono text-xs">{formatPrice(pos.current_price)}</td>
                      <td className="py-3 px-3 text-xs text-muted-foreground">{pos.quantity}</td>
                      <td className={`py-3 px-3 font-mono text-xs font-semibold ${profit ? "text-bull" : "text-bear"}`}>
                        {formatPnl(pos.unrealized_pnl)}
                      </td>
                      <td className={`py-3 px-3 text-xs font-semibold ${profit ? "text-bull" : "text-bear"}`}>
                        {formatPct(pos.unrealized_pnl_pct)}
                      </td>
                      <td className="py-3 px-3 text-xs text-muted-foreground">
                        {new Date(pos.opened_at).toLocaleDateString()}
                      </td>
                      <td className="py-3 px-3">
                        <button className="text-xs text-muted-foreground hover:text-foreground border border-border/50 rounded px-2 py-0.5 hover:border-border transition-colors">
                          Close
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
