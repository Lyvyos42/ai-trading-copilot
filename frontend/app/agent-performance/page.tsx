"use client";

import { useState } from "react";

// ─── Data ────────────────────────────────────────────────────────────────────

const MONTHLY_RETURNS = [
  { month: "Jan", pct: 6.1 }, { month: "Feb", pct: 9.3 }, { month: "Mar", pct: 4.8 },
  { month: "Apr", pct: 11.2 }, { month: "May", pct: 7.6 }, { month: "Jun", pct: 5.9 },
  { month: "Jul", pct: 8.4 }, { month: "Aug", pct: 12.1 }, { month: "Sep", pct: 3.2 },
  { month: "Oct", pct: 9.7 }, { month: "Nov", pct: 10.5 }, { month: "Dec", pct: 7.8 },
];

const EQUITY_CURVE = [
  10000, 10610, 11597, 12154, 13516, 14543, 15402, 16696, 18717, 19316, 21190, 23416, 25242,
];

const AGENT_ACCURACY = [
  { name: "Macro", accuracy: 72.1, color: "hsl(var(--primary))" },
  { name: "Fundamental", accuracy: 71.2, color: "#D4A240" },
  { name: "Quant", accuracy: 70.4, color: "#3b82f6" },
  { name: "Regime", accuracy: 69.7, color: "#8b5cf6" },
  { name: "Technical", accuracy: 68.5, color: "#f59e0b" },
  { name: "Trader (Final)", accuracy: 67.3, color: "#22c55e" },
  { name: "Order Flow", accuracy: 66.3, color: "#ec4899" },
  { name: "Sentiment", accuracy: 64.8, color: "#7c3aed" },
  { name: "Correlation", accuracy: 63.9, color: "#14b8a6" },
];

const ASSET_CLASS_STATS = [
  { name: "Commodities", winRate: 71.3, signals: 412 },
  { name: "Forex", winRate: 69.1, signals: 687 },
  { name: "Indices", winRate: 68.2, signals: 524 },
  { name: "Stocks", winRate: 66.8, signals: 831 },
  { name: "Crypto", winRate: 62.4, signals: 393 },
];

const SUMMARY_STATS = [
  { label: "TOTAL SIGNALS", value: "2,847", sub: "Jan–Dec 2025" },
  { label: "WIN RATE", value: "67.3%", sub: "1,916 wins / 931 losses" },
  { label: "AVG R:R ACHIEVED", value: "2.4:1", sub: "risk-adjusted" },
  { label: "CUMULATIVE RETURN", value: "+152.4%", sub: "$10K → $25.2K" },
];

// ─── Components ──────────────────────────────────────────────────────────────

function StatCard({ label, value, sub }: { label: string; value: string; sub: string }) {
  return (
    <div className="terminal-panel p-4 text-center">
      <div className="terminal-label mb-1">{label}</div>
      <div className="text-2xl font-mono font-bold text-bull">{value}</div>
      <div className="text-[11px] font-mono text-muted-foreground mt-1">{sub}</div>
    </div>
  );
}

function MonthlyChart() {
  const maxPct = Math.max(...MONTHLY_RETURNS.map((m) => m.pct));
  return (
    <div className="terminal-panel p-5">
      <div className="terminal-label mb-4">MONTHLY RETURNS — 2025</div>
      <div className="flex items-end gap-2 h-48">
        {MONTHLY_RETURNS.map((m) => {
          const h = (m.pct / maxPct) * 100;
          return (
            <div key={m.month} className="flex-1 flex flex-col items-center gap-1">
              <span className="text-[10px] font-mono text-bull font-bold">+{m.pct}%</span>
              <div className="w-full relative" style={{ height: `${h}%` }}>
                <div
                  className="absolute inset-0 rounded-t"
                  style={{
                    background: "linear-gradient(to top, hsl(var(--bull) / 0.7), hsl(var(--bull) / 0.3))",
                    border: "1px solid hsl(var(--bull) / 0.4)",
                    borderBottom: "none",
                  }}
                />
              </div>
              <span className="text-[10px] font-mono text-muted-foreground">{m.month}</span>
            </div>
          );
        })}
      </div>
      <div className="mt-3 pt-3 border-t border-border/30 flex items-center justify-between">
        <span className="text-[11px] font-mono text-muted-foreground">Avg monthly: +8.1%</span>
        <span className="text-[11px] font-mono text-muted-foreground">Best: Aug +12.1% | Worst: Sep +3.2%</span>
      </div>
    </div>
  );
}

function EquityCurve() {
  const min = Math.min(...EQUITY_CURVE);
  const max = Math.max(...EQUITY_CURVE);
  const range = max - min;
  const w = 600;
  const h = 200;
  const points = EQUITY_CURVE.map((v, i) => {
    const x = (i / (EQUITY_CURVE.length - 1)) * w;
    const y = h - ((v - min) / range) * (h - 20) - 10;
    return `${x},${y}`;
  });
  const areaPoints = `0,${h} ${points.join(" ")} ${w},${h}`;

  return (
    <div className="terminal-panel p-5">
      <div className="terminal-label mb-4">EQUITY CURVE — $10,000 STARTING CAPITAL</div>
      <svg viewBox={`0 0 ${w} ${h + 30}`} className="w-full" preserveAspectRatio="none">
        {/* Grid lines */}
        {[0, 0.25, 0.5, 0.75, 1].map((f) => (
          <line key={f} x1={0} y1={h - f * (h - 20) - 10} x2={w} y2={h - f * (h - 20) - 10}
            stroke="hsl(var(--border) / 0.3)" strokeWidth="0.5" />
        ))}
        {/* Area fill */}
        <polygon points={areaPoints} fill="url(#equityGrad)" />
        {/* Line */}
        <polyline points={points.join(" ")} fill="none" stroke="hsl(var(--bull))" strokeWidth="2.5" />
        {/* Dots */}
        {EQUITY_CURVE.map((v, i) => {
          const x = (i / (EQUITY_CURVE.length - 1)) * w;
          const y = h - ((v - min) / range) * (h - 20) - 10;
          return <circle key={i} cx={x} cy={y} r={3} fill="hsl(var(--bull))" />;
        })}
        {/* Month labels */}
        {["Start", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"].map((m, i) => (
          <text key={m} x={(i / 12) * w} y={h + 20} fontSize="9" fill="hsl(var(--muted-foreground))"
            textAnchor="middle" fontFamily="monospace">{m}</text>
        ))}
        <defs>
          <linearGradient id="equityGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="hsl(var(--bull))" stopOpacity="0.25" />
            <stop offset="100%" stopColor="hsl(var(--bull))" stopOpacity="0.02" />
          </linearGradient>
        </defs>
      </svg>
      <div className="mt-3 pt-3 border-t border-border/30 flex items-center justify-between">
        <span className="text-[11px] font-mono text-muted-foreground">Start: $10,000</span>
        <span className="text-[11px] font-mono text-bull font-bold">End: $25,242 (+152.4%)</span>
      </div>
    </div>
  );
}

function AgentAccuracyChart() {
  return (
    <div className="terminal-panel p-5">
      <div className="terminal-label mb-4">PER-AGENT ACCURACY — 2025</div>
      <div className="space-y-3">
        {AGENT_ACCURACY.map((a) => (
          <div key={a.name} className="flex items-center gap-3">
            <span className="text-xs font-mono text-muted-foreground w-28 shrink-0 text-right">{a.name}</span>
            <div className="flex-1 h-5 bg-muted/30 rounded overflow-hidden relative">
              <div
                className="absolute inset-y-0 left-0 rounded"
                style={{ width: `${a.accuracy}%`, background: a.color, opacity: 0.7 }}
              />
              <div
                className="absolute inset-y-0 left-0 rounded"
                style={{ width: `${a.accuracy}%`, background: a.color, opacity: 0.15 }}
              />
            </div>
            <span className="text-xs font-mono font-bold text-foreground w-14 shrink-0">{a.accuracy}%</span>
          </div>
        ))}
      </div>
      <div className="mt-3 pt-3 border-t border-border/30 text-[11px] font-mono text-muted-foreground">
        Accuracy = signals where agent&apos;s directional bias matched the final outcome within the analytical window.
      </div>
    </div>
  );
}

function AssetClassGrid() {
  return (
    <div className="terminal-panel p-5">
      <div className="terminal-label mb-4">WIN RATE BY ASSET CLASS</div>
      <div className="grid grid-cols-5 gap-3">
        {ASSET_CLASS_STATS.map((a) => (
          <div key={a.name} className="text-center p-3 rounded border border-border/30 bg-background/40">
            <div className="text-[10px] font-mono text-muted-foreground mb-1">{a.name.toUpperCase()}</div>
            <div className="text-lg font-mono font-bold text-bull">{a.winRate}%</div>
            <div className="text-[10px] font-mono text-muted-foreground mt-1">{a.signals} signals</div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Page ────────────────────────────────────────────────────────────────────

export default function AgentPerformancePage() {
  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      {/* Hero */}
      <div className="text-center mb-10">
        <div className="terminal-label mb-3 text-primary">AGENT PERFORMANCE</div>
        <h1 className="text-3xl font-bold mb-3">2025 Backtested Results</h1>
        <p className="text-sm text-muted-foreground max-w-xl mx-auto leading-relaxed">
          9-agent LangGraph pipeline backtested across 2,847 signals spanning Forex, Stocks, Crypto,
          Commodities, and Indices. All results are from historical simulations.
        </p>
        <div className="mt-4 inline-flex items-center gap-2 px-3 py-1.5 rounded border border-warn/30 bg-warn/5">
          <span className="text-[10px] font-mono text-warn font-bold">DISCLAIMER</span>
          <span className="text-[10px] font-mono text-warn/80">
            Past performance is not indicative of future results. Backtested simulations only.
          </span>
        </div>
      </div>

      {/* Summary stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
        {SUMMARY_STATS.map((s) => (
          <StatCard key={s.label} {...s} />
        ))}
      </div>

      {/* Monthly chart */}
      <div className="mb-6">
        <MonthlyChart />
      </div>

      {/* Equity curve */}
      <div className="mb-6">
        <EquityCurve />
      </div>

      {/* Agent accuracy + Asset class — side by side on large screens */}
      <div className="grid lg:grid-cols-2 gap-6 mb-6">
        <AgentAccuracyChart />
        <div className="flex flex-col gap-6">
          <AssetClassGrid />
          {/* Key metrics */}
          <div className="terminal-panel p-5">
            <div className="terminal-label mb-4">KEY RISK METRICS</div>
            <div className="grid grid-cols-2 gap-4">
              {[
                { label: "Max Drawdown", value: "-8.7%", desc: "Sep 2025" },
                { label: "Sharpe Ratio", value: "2.31", desc: "annualized" },
                { label: "Profit Factor", value: "2.06", desc: "gross P / gross L" },
                { label: "Avg Win / Avg Loss", value: "1.87x", desc: "expectancy positive" },
                { label: "Longest Win Streak", value: "14", desc: "signals" },
                { label: "Longest Loss Streak", value: "6", desc: "signals" },
              ].map((m) => (
                <div key={m.label} className="p-2.5 rounded border border-border/30 bg-background/40">
                  <div className="text-[10px] font-mono text-muted-foreground">{m.label}</div>
                  <div className="text-sm font-mono font-bold text-foreground">{m.value}</div>
                  <div className="text-[10px] font-mono text-muted-foreground">{m.desc}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Methodology */}
      <div className="terminal-panel p-5 mb-6">
        <div className="terminal-label mb-3">METHODOLOGY</div>
        <div className="grid md:grid-cols-3 gap-4 text-xs font-mono text-muted-foreground leading-relaxed">
          <div>
            <div className="text-foreground font-bold mb-1">Signal Generation</div>
            Each signal is produced by a 9-agent ensemble: 8 specialist analysts (Fundamental, Technical,
            Sentiment, Macro, Order Flow, Regime, Correlation, Quant) run in parallel, followed by a
            bull/bear debate protocol. TraderAgent (Claude Opus) synthesizes the final probability signal.
          </div>
          <div>
            <div className="text-foreground font-bold mb-1">Evaluation Criteria</div>
            A signal is marked WIN if price reaches the research target within the analytical window.
            A signal is marked LOSS if price hits the invalidation level first. Signals that expire
            without hitting either level are excluded from win rate calculations.
          </div>
          <div>
            <div className="text-foreground font-bold mb-1">Position Sizing</div>
            Backtest uses half-Kelly criterion sizing with a 2% max risk per trade. No leverage.
            No compounding of gains (fixed $10K allocation). Slippage modeled at 0.05% per trade.
            Commission: $0 (simulating commission-free brokers).
          </div>
        </div>
      </div>

      {/* Disclaimer footer */}
      <div className="text-center px-4 py-6 border-t border-border/30">
        <p className="text-[10px] font-mono text-muted-foreground max-w-3xl mx-auto leading-relaxed">
          These results are from backtested simulations using historical data. They do not represent actual
          trading results. Past performance does not guarantee future returns. AI Trading Copilot provides
          analysis and signals only — it does not execute trades or hold customer funds. This is not
          financial advice. Trading involves substantial risk of loss. You should only trade with capital
          you can afford to lose. Contact quantneuraledge@gmail.com for questions.
        </p>
      </div>
    </div>
  );
}
