"use client";

import { useState, useEffect } from "react";
import { BarChart2, TrendingUp, TrendingDown, Play } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { runBacktest, listStrategies } from "@/lib/api";
import { formatPct } from "@/lib/utils";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";

export default function BacktestPage() {
  const [strategies, setStrategies] = useState<{ name: string; ref: string; description: string }[]>([]);
  const [selected, setSelected] = useState("price_momentum");
  const [ticker, setTicker] = useState("SPY");
  const [period, setPeriod] = useState("1Y");
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    listStrategies().then((d) => setStrategies(d.strategies));
  }, []);

  async function handleRun() {
    setLoading(true);
    try {
      const res = await runBacktest(selected, ticker, period);
      setResult(res as Record<string, unknown>);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  const equityCurve = (result?.equity_curve as number[] | undefined)?.map((v, i) => ({
    month: i === 0 ? "Start" : `M${i}`,
    value: Math.round(v),
  })) || [];

  return (
    <div className="max-w-7xl mx-auto px-4 py-6">
      <div className="mb-6">
        <h1 className="text-2xl font-bold mb-1">Strategy Backtester</h1>
        <p className="text-sm text-muted-foreground">
          Simulate historical performance of any strategy from the 151 Trading Strategies framework.
        </p>
      </div>

      <div className="grid lg:grid-cols-[280px_1fr] gap-6">
        {/* Controls */}
        <div className="space-y-4">
          <Card className="border-border/50">
            <CardHeader className="pb-2">
              <CardTitle>Configuration</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div>
                <label className="text-xs text-muted-foreground block mb-1">Strategy</label>
                <select
                  value={selected}
                  onChange={(e) => setSelected(e.target.value)}
                  className="w-full px-2 py-1.5 rounded-md border border-border/50 bg-background text-sm focus:outline-none focus:border-primary/50"
                >
                  {strategies.map((s) => (
                    <option key={s.name} value={s.name}>
                      [{s.ref}] {s.name.replace(/_/g, " ")}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-xs text-muted-foreground block mb-1">Ticker</label>
                <input
                  value={ticker}
                  onChange={(e) => setTicker(e.target.value.toUpperCase())}
                  className="w-full px-2 py-1.5 rounded-md border border-border/50 bg-background text-sm focus:outline-none focus:border-primary/50"
                />
              </div>
              <div>
                <label className="text-xs text-muted-foreground block mb-1">Period</label>
                <div className="flex gap-1">
                  {["1Y", "2Y", "3Y", "5Y"].map((p) => (
                    <button
                      key={p}
                      onClick={() => setPeriod(p)}
                      className={`flex-1 py-1 text-xs rounded-md border transition-colors ${period === p ? "bg-primary/10 border-primary/40 text-primary" : "border-border/50 text-muted-foreground hover:border-primary/30"}`}
                    >
                      {p}
                    </button>
                  ))}
                </div>
              </div>
              <Button className="w-full" size="sm" onClick={handleRun} disabled={loading}>
                <Play className="h-3.5 w-3.5 mr-1.5" />
                {loading ? "Running..." : "Run Backtest"}
              </Button>
            </CardContent>
          </Card>

          {result && (
            <Card className="border-border/50">
              <CardHeader className="pb-2">
                <CardTitle>Performance</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {[
                  { label: "Total Return", value: formatPct(result.total_return_pct as number), positive: (result.total_return_pct as number) >= 0 },
                  { label: "Annual Return", value: formatPct(result.annual_return_pct as number), positive: true },
                  { label: "Sharpe Ratio", value: (result.sharpe_ratio as number).toFixed(2) },
                  { label: "Max Drawdown", value: `-${(result.max_drawdown_pct as number).toFixed(1)}%`, positive: false },
                  { label: "Win Rate", value: formatPct(result.win_rate_pct as number) },
                  { label: "Total Trades", value: String(result.total_trades) },
                  { label: "Calmar Ratio", value: (result.calmar_ratio as number).toFixed(2) },
                ].map(({ label, value, positive }) => (
                  <div key={label} className="flex justify-between text-xs">
                    <span className="text-muted-foreground">{label}</span>
                    <span className={`font-mono font-semibold ${positive === true ? "text-bull" : positive === false ? "text-bear" : "text-foreground"}`}>
                      {value}
                    </span>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}
        </div>

        {/* Chart area */}
        <div className="space-y-4">
          {result ? (
            <>
              <Card className="border-border/50">
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between">
                    <CardTitle>Equity Curve — {ticker} / {selected.replace(/_/g, " ")} / {period}</CardTitle>
                    <Badge variant={((result.total_return_pct as number) >= 0) ? "bull" : "bear"}>
                      {formatPct(result.total_return_pct as number)}
                    </Badge>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="h-64">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={equityCurve}>
                        <CartesianGrid strokeDasharray="3 3" stroke="hsl(216 34% 17%)" />
                        <XAxis dataKey="month" tick={{ fontSize: 11, fill: "hsl(215 16% 57%)" }} />
                        <YAxis tick={{ fontSize: 11, fill: "hsl(215 16% 57%)" }} tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} />
                        <Tooltip
                          contentStyle={{ background: "hsl(224 71% 6%)", border: "1px solid hsl(216 34% 17%)", borderRadius: "6px", fontSize: "12px" }}
                          formatter={(v: number) => [`$${v.toLocaleString()}`, "Equity"]}
                        />
                        <Line type="monotone" dataKey="value" stroke="#3b82f6" strokeWidth={2} dot={false} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </CardContent>
              </Card>

              {/* Sample trades */}
              <Card className="border-border/50">
                <CardHeader className="pb-2">
                  <CardTitle>Sample Trades</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="border-b border-border/50">
                          {["#", "Direction", "Return", "Hold Days", "Outcome"].map((h) => (
                            <th key={h} className="text-left py-2 px-2 text-muted-foreground font-medium">{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {((result.sample_trades as Array<Record<string, unknown>>) || []).map((t) => (
                          <tr key={t.trade_num as number} className="border-b border-border/20 hover:bg-accent/20">
                            <td className="py-2 px-2 text-muted-foreground">{t.trade_num as number}</td>
                            <td className="py-2 px-2">
                              <span className={t.direction === "LONG" ? "text-bull" : "text-bear"}>
                                {t.direction as string}
                              </span>
                            </td>
                            <td className={`py-2 px-2 font-mono font-semibold ${(t.return_pct as number) >= 0 ? "text-bull" : "text-bear"}`}>
                              {formatPct(t.return_pct as number)}
                            </td>
                            <td className="py-2 px-2 text-muted-foreground">{t.hold_days as number}d</td>
                            <td className="py-2 px-2">
                              <Badge variant={t.outcome === "WIN" ? "bull" : "bear"} className="text-[10px]">
                                {t.outcome as string}
                              </Badge>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <p className="text-[10px] text-muted-foreground mt-3 text-center">
                    Note: Simulated results. Connect QuantConnect LEAN for production backtests.
                  </p>
                </CardContent>
              </Card>
            </>
          ) : (
            <Card className="border-border/50 border-dashed h-96 flex items-center justify-center">
              <div className="text-center text-muted-foreground">
                <BarChart2 className="h-10 w-10 mx-auto mb-3 opacity-20" />
                <p className="text-sm">Configure a strategy and click Run Backtest</p>
              </div>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
