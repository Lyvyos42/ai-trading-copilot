"use client";

import { useState, useEffect } from "react";
import { BarChart2, Play, TrendingUp, TrendingDown } from "lucide-react";
import { runBacktest, listStrategies } from "@/lib/api";
import { formatPct } from "@/lib/utils";

interface BacktestResult {
  total_return_pct: number;
  annual_return_pct: number;
  sharpe_ratio: number;
  max_drawdown_pct: number;
  win_rate_pct: number;
  total_trades: number;
  calmar_ratio: number;
  equity_curve: number[];
  sample_trades: { trade_num: number; direction: string; return_pct: number; hold_days: number; outcome: string }[];
}

// Pure SVG equity curve — no recharts, Bloomberg terminal style
function EquityCurve({ data, positive }: { data: number[]; positive: boolean }) {
  if (data.length < 2) return null;
  const W = 700; const H = 160;
  const padL = 52; const padR = 12; const padT = 8; const padB = 24;
  const innerW = W - padL - padR;
  const innerH = H - padT - padB;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;

  const px = (i: number) => padL + (i / (data.length - 1)) * innerW;
  const py = (v: number) => padT + innerH - ((v - min) / range) * innerH;

  const points = data.map((v, i) => `${px(i)},${py(v)}`).join(" ");
  const areaClose = `${px(data.length - 1)},${padT + innerH} ${padL},${padT + innerH}`;
  const color = positive ? "#22c55e" : "#e63946";

  // Y-axis ticks
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((t) => ({
    y: padT + innerH - t * innerH,
    val: min + t * range,
  }));

  // X-axis labels (start / quarters / end)
  const xLabels = [0, Math.floor(data.length * 0.25), Math.floor(data.length * 0.5), Math.floor(data.length * 0.75), data.length - 1];

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ height: H }}>
      {/* Grid lines */}
      {ticks.map((t, i) => (
        <line key={i} x1={padL} y1={t.y} x2={W - padR} y2={t.y} stroke="hsl(0 0% 12%)" strokeWidth="1" />
      ))}

      {/* Area fill */}
      <polygon
        points={`${padL},${py(data[0])} ${points} ${areaClose}`}
        fill={color}
        opacity={0.08}
      />

      {/* Line */}
      <polyline points={points} fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />

      {/* Start/end dots */}
      <circle cx={px(0)} cy={py(data[0])} r="3" fill={color} opacity={0.6} />
      <circle cx={px(data.length - 1)} cy={py(data[data.length - 1])} r="4" fill={color} />

      {/* Y-axis labels */}
      {ticks.map((t, i) => (
        <text key={i} x={padL - 6} y={t.y + 4} textAnchor="end" fontSize="9" fill="hsl(0 0% 40%)" fontFamily="'JetBrains Mono', monospace">
          ${(t.val / 1000).toFixed(0)}k
        </text>
      ))}

      {/* X-axis labels */}
      {xLabels.map((idx, i) => (
        <text key={i} x={px(idx)} y={H - 4} textAnchor="middle" fontSize="9" fill="hsl(0 0% 40%)" fontFamily="'JetBrains Mono', monospace">
          {idx === 0 ? "START" : `M${idx}`}
        </text>
      ))}
    </svg>
  );
}

// Drawdown curve derived from equity
function DrawdownCurve({ equity }: { equity: number[] }) {
  if (equity.length < 2) return null;
  const W = 700; const H = 60;
  const padL = 52; const padR = 12; const padT = 4; const padB = 4;
  const innerW = W - padL - padR;
  const innerH = H - padT - padB;

  let peak = equity[0];
  const dd = equity.map((v) => { if (v > peak) peak = v; return (v - peak) / peak; });
  const min = Math.min(...dd);

  const px = (i: number) => padL + (i / (equity.length - 1)) * innerW;
  const py = (v: number) => padT + (v / (min || -0.01)) * innerH;
  const points = dd.map((v, i) => `${px(i)},${py(v)}`).join(" ");
  const areaClose = `${px(dd.length - 1)},${padT} ${padL},${padT}`;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ height: H }}>
      <polygon points={`${padL},${padT} ${points} ${areaClose}`} fill="#e63946" opacity={0.12} />
      <polyline points={points} fill="none" stroke="#e63946" strokeWidth="1" opacity={0.6} />
      <text x={padL - 6} y={padT + innerH / 2 + 4} textAnchor="end" fontSize="9" fill="hsl(0 0% 40%)" fontFamily="'JetBrains Mono', monospace">
        DD
      </text>
    </svg>
  );
}

const PERIODS = ["1Y", "2Y", "3Y", "5Y"];

export default function BacktestPage() {
  const [strategies, setStrategies] = useState<{ name: string; ref: string; description: string }[]>([]);
  const [selected, setSelected]     = useState("price_momentum");
  const [ticker, setTicker]         = useState("SPY");
  const [period, setPeriod]         = useState("1Y");
  const [result, setResult]         = useState<BacktestResult | null>(null);
  const [loading, setLoading]       = useState(false);

  useEffect(() => {
    listStrategies().then((d) => setStrategies(d.strategies));
  }, []);

  async function handleRun() {
    setLoading(true);
    try {
      const res = await runBacktest(selected, ticker, period);
      setResult(res as BacktestResult);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  const isPositive = result ? result.total_return_pct >= 0 : true;

  const metrics = result
    ? [
        { label: "TOTAL RETURN",  value: formatPct(result.total_return_pct),  color: result.total_return_pct >= 0 ? "text-bull" : "text-bear" },
        { label: "ANNUAL RETURN", value: formatPct(result.annual_return_pct),  color: "text-bull" },
        { label: "SHARPE RATIO",  value: result.sharpe_ratio.toFixed(2),       color: result.sharpe_ratio >= 1 ? "text-bull" : "text-warn" },
        { label: "MAX DRAWDOWN",  value: `-${result.max_drawdown_pct.toFixed(1)}%`, color: "text-bear" },
        { label: "WIN RATE",      value: formatPct(result.win_rate_pct),       color: result.win_rate_pct >= 50 ? "text-bull" : "text-bear" },
        { label: "TOTAL TRADES",  value: String(result.total_trades),          color: "text-foreground" },
        { label: "CALMAR RATIO",  value: result.calmar_ratio.toFixed(2),       color: result.calmar_ratio >= 1 ? "text-bull" : "text-warn" },
      ]
    : [];

  return (
    <div className="max-w-7xl mx-auto px-4 py-6 space-y-4">

      {/* Header bar */}
      <div className="terminal-panel">
        <div className="terminal-header">
          <BarChart2 className="h-3 w-3 text-primary" />
          <span className="terminal-label">Strategy Backtester — 151 Trading Strategies Framework</span>
          {result && (
            <div className={`ml-auto flex items-center gap-1.5 px-2 py-0.5 border font-mono text-xs font-bold ${isPositive ? "border-bull/40 bg-bull/10 text-bull" : "border-bear/40 bg-bear/10 text-bear"}`}>
              {isPositive ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
              {formatPct(result.total_return_pct)}
            </div>
          )}
        </div>
      </div>

      <div className="grid lg:grid-cols-[260px_1fr] gap-4">

        {/* Config panel */}
        <div className="space-y-4">
          <div className="terminal-panel">
            <div className="terminal-header">
              <span className="terminal-label">Configuration</span>
            </div>
            <div className="p-4 space-y-4">
              <div>
                <div className="terminal-label mb-1.5">Strategy</div>
                <select
                  value={selected}
                  onChange={(e) => setSelected(e.target.value)}
                  className="w-full px-2 py-1.5 bg-background border border-border/50 text-xs font-mono text-foreground focus:outline-none focus:border-primary/50"
                >
                  {strategies.map((s) => (
                    <option key={s.name} value={s.name}>
                      [{s.ref}] {s.name.replace(/_/g, " ")}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <div className="terminal-label mb-1.5">Ticker</div>
                <div className="flex items-center border border-border/50 bg-background focus-within:border-primary/50">
                  <span className="pl-2 terminal-label text-primary shrink-0">›</span>
                  <input
                    value={ticker}
                    onChange={(e) => setTicker(e.target.value.toUpperCase())}
                    className="flex-1 px-2 py-1.5 bg-transparent text-xs font-mono text-foreground focus:outline-none"
                  />
                </div>
              </div>

              <div>
                <div className="terminal-label mb-1.5">Period</div>
                <div className="grid grid-cols-4 gap-1">
                  {PERIODS.map((p) => (
                    <button
                      key={p}
                      onClick={() => setPeriod(p)}
                      className={`py-1 text-xs font-mono font-semibold border transition-colors ${period === p ? "border-primary/50 bg-primary/10 text-primary" : "border-border/40 text-muted-foreground hover:border-primary/30"}`}
                    >
                      {p}
                    </button>
                  ))}
                </div>
              </div>

              <button
                className="w-full py-2 text-xs font-mono font-semibold border border-primary/50 bg-primary/10 text-primary hover:bg-primary/20 disabled:opacity-40 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
                onClick={handleRun}
                disabled={loading}
              >
                <Play className="h-3 w-3" />
                {loading ? "RUNNING···" : "RUN BACKTEST"}
              </button>
            </div>
          </div>

          {/* Metrics panel */}
          {result && (
            <div className="terminal-panel">
              <div className="terminal-header">
                <span className="terminal-label">Performance Metrics</span>
              </div>
              <div className="divide-y divide-border/30">
                {metrics.map(({ label, value, color }) => (
                  <div key={label} className="flex justify-between items-center px-4 py-2">
                    <span className="terminal-label">{label}</span>
                    <span className={`text-xs font-mono font-bold ${color}`}>{value}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Chart area */}
        <div className="space-y-4">
          {result ? (
            <>
              {/* Equity curve */}
              <div className="terminal-panel">
                <div className="terminal-header">
                  <span className="terminal-label">Equity Curve</span>
                  <span className="ml-2 font-mono text-[10px] text-foreground">{ticker} / {selected.replace(/_/g," ")} / {period}</span>
                </div>
                <div className="p-3">
                  <EquityCurve data={result.equity_curve} positive={isPositive} />
                </div>
                <div className="px-3 pb-3">
                  <DrawdownCurve equity={result.equity_curve} />
                  <div className="terminal-label mt-1">DRAWDOWN</div>
                </div>
              </div>

              {/* Sample trades table */}
              <div className="terminal-panel">
                <div className="terminal-header">
                  <span className="terminal-label">Sample Trades</span>
                  <span className="ml-auto terminal-label">{result.sample_trades.length} TRADES SHOWN</span>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-border/50">
                        {["#", "Direction", "Return", "Hold Days", "Outcome"].map((h) => (
                          <th key={h} className="text-left px-4 py-2 terminal-label">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {result.sample_trades.map((t) => (
                        <tr key={t.trade_num} className="border-b border-border/20 hover:bg-muted/20 transition-colors">
                          <td className="px-4 py-2 font-mono text-muted-foreground">{String(t.trade_num).padStart(2, "0")}</td>
                          <td className={`px-4 py-2 font-mono font-bold ${t.direction === "LONG" ? "text-bull" : "text-bear"}`}>
                            {t.direction}
                          </td>
                          <td className={`px-4 py-2 font-mono font-semibold ${t.return_pct >= 0 ? "text-bull" : "text-bear"}`}>
                            {formatPct(t.return_pct)}
                          </td>
                          <td className="px-4 py-2 font-mono text-muted-foreground">{t.hold_days}d</td>
                          <td className="px-4 py-2">
                            <span className={`text-[10px] font-mono font-bold px-1.5 py-0.5 border ${t.outcome === "WIN" ? "border-bull/30 bg-bull/10 text-bull" : "border-bear/30 bg-bear/10 text-bear"}`}>
                              {t.outcome}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div className="px-4 py-2 border-t border-border/30">
                  <span className="terminal-label">NOTE: SIMULATED RESULTS — CONNECT QUANTCONNECT LEAN FOR PRODUCTION BACKTESTS</span>
                </div>
              </div>
            </>
          ) : (
            <div className="terminal-panel" style={{ minHeight: 400 }}>
              <div className="flex flex-col items-center justify-center h-96 gap-3">
                <div className="text-primary/15 font-mono text-5xl">[ ]</div>
                <span className="terminal-label">CONFIGURE A STRATEGY AND HIT RUN BACKTEST</span>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
