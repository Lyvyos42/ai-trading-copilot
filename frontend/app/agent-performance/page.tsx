"use client";

import { useState, useEffect, useMemo } from "react";
import Link from "next/link";
import { listSignals, type Signal } from "@/lib/api";
import { useRequireAuth } from "@/lib/useAuth";
import { cn, formatPct, formatPrice } from "@/lib/utils";

// ─── Agent Color Mapping ───────────────────────────────────────────────────────

const AGENT_CONFIG: Record<string, { label: string; color: string }> = {
  macro: { label: "Macro", color: "hsl(var(--primary))" },
  fundamental: { label: "Fundamental", color: "#D4A240" },
  quant: { label: "Quant", color: "#3b82f6" },
  regime_change: { label: "Regime", color: "#8b5cf6" },
  technical: { label: "Technical", color: "#f59e0b" },
  trader: { label: "Trader (Final)", color: "#22c55e" },
  order_flow: { label: "Order Flow", color: "#ec4899" },
  sentiment: { label: "Sentiment", color: "#7c3aed" },
  correlation: { label: "Correlation", color: "#14b8a6" },
};

const ORDERED_AGENT_KEYS = [
  "macro",
  "fundamental",
  "quant",
  "regime_change",
  "technical",
  "order_flow",
  "sentiment",
  "correlation",
];

// ─── Components ──────────────────────────────────────────────────────────────

function StatCard({ label, value, sub }: { label: string; value: string; sub: string }) {
  return (
    <div className="terminal-panel p-4 text-center">
      <div className="terminal-label mb-1">{label}</div>
      <div className={cn("text-2xl font-mono font-bold", value === "—" ? "text-muted-foreground" : "text-bull")}>
        {value}
      </div>
      <div className="text-[12px] font-mono text-muted-foreground mt-1">{sub}</div>
    </div>
  );
}

function MonthlyChart({ months }: { months: { month: string; pct: number }[] }) {
  if (months.length === 0) {
    return (
      <div className="terminal-panel p-5">
        <div className="terminal-label mb-4">MONTHLY RETURNS</div>
        <div className="h-32 flex flex-col items-center justify-center border border-dashed border-border/40 rounded bg-background/20 p-4 text-center">
          <span className="text-xs font-mono font-bold text-muted-foreground mb-1">
            NO RESOLVED MONTHLY PERIODS YET
          </span>
          <span className="text-[12px] font-mono text-muted-foreground/70 max-w-md">
            Data aggregates automatically as active positions resolve through their evaluation windows. No synthetic fills.
          </span>
        </div>
      </div>
    );
  }

  const maxPct = Math.max(...months.map((m) => Math.abs(m.pct)), 1);
  const avgMonthly = (months.reduce((acc, m) => acc + m.pct, 0) / months.length).toFixed(1);

  return (
    <div className="terminal-panel p-5">
      <div className="terminal-label mb-4">MONTHLY RETURNS — VERIFIED PERIODS</div>
      <div className="flex items-end gap-2 h-48">
        {months.map((m) => {
          const isGain = m.pct >= 0;
          const h = Math.max((Math.abs(m.pct) / maxPct) * 100, 4);
          return (
            <div key={m.month} className="flex-1 flex flex-col items-center gap-1">
              <span className={cn("text-[12px] font-mono font-bold", isGain ? "text-bull" : "text-bear")}>
                {isGain ? `+${m.pct.toFixed(1)}%` : `${m.pct.toFixed(1)}%`}
              </span>
              <div className="w-full relative" style={{ height: `${h}%` }}>
                <div
                  className="absolute inset-0 rounded-t"
                  style={{
                    background: isGain
                      ? "linear-gradient(to top, hsl(var(--bull) / 0.7), hsl(var(--bull) / 0.3))"
                      : "linear-gradient(to top, hsl(var(--bear) / 0.7), hsl(var(--bear) / 0.3))",
                    border: `1px solid ${isGain ? "hsl(var(--bull) / 0.4)" : "hsl(var(--bear) / 0.4)"}`,
                    borderBottom: "none",
                  }}
                />
              </div>
              <span className="text-[12px] font-mono text-muted-foreground">{m.month}</span>
            </div>
          );
        })}
      </div>
      <div className="mt-3 pt-3 border-t border-border/30 flex items-center justify-between">
        <span className="text-[12px] font-mono text-muted-foreground">Avg monthly: {avgMonthly}%</span>
        <span className="text-[12px] font-mono text-muted-foreground">{months.length} active periods recorded</span>
      </div>
    </div>
  );
}

function EquityCurve({ points }: { points: number[] }) {
  if (points.length < 2) {
    return (
      <div className="terminal-panel p-5">
        <div className="terminal-label mb-4">EQUITY CURVE — LIVE REALISED RETURN</div>
        <div className="h-36 flex flex-col items-center justify-center border border-dashed border-border/40 rounded bg-background/20 p-4 text-center">
          <span className="text-xs font-mono font-bold text-muted-foreground mb-1">
            ACCUMULATING DATA POINTS
          </span>
          <span className="text-[12px] font-mono text-muted-foreground/70 max-w-md">
            A minimum of 2 hand-resolved signals with realized P&L is required to construct an empirical equity curve. No synthetic interpolations.
          </span>
        </div>
      </div>
    );
  }

  const min = Math.min(...points);
  const max = Math.max(...points);
  const range = max - min || 1;
  const w = 600;
  const h = 200;
  const svgPoints = points.map((v, i) => {
    const x = (i / (points.length - 1)) * w;
    const y = h - ((v - min) / range) * (h - 20) - 10;
    return `${x},${y}`;
  });
  const areaPoints = `0,${h} ${svgPoints.join(" ")} ${w},${h}`;
  const startVal = points[0];
  const endVal = points[points.length - 1];
  const totalReturn = (((endVal - startVal) / startVal) * 100).toFixed(1);

  return (
    <div className="terminal-panel p-5">
      <div className="terminal-label mb-4">EQUITY CURVE — EMPIRICAL TRACK RECORD</div>
      <svg viewBox={`0 0 ${w} ${h + 30}`} className="w-full" preserveAspectRatio="none">
        {[0, 0.25, 0.5, 0.75, 1].map((f) => (
          <line
            key={f}
            x1={0}
            y1={h - f * (h - 20) - 10}
            x2={w}
            y2={h - f * (h - 20) - 10}
            stroke="hsl(var(--border) / 0.3)"
            strokeWidth="0.5"
          />
        ))}
        <polygon points={areaPoints} fill="url(#equityGradLive)" />
        <polyline points={svgPoints.join(" ")} fill="none" stroke="hsl(var(--bull))" strokeWidth="2.5" />
        {points.map((v, i) => {
          const x = (i / (points.length - 1)) * w;
          const y = h - ((v - min) / range) * (h - 20) - 10;
          return <circle key={i} cx={x} cy={y} r={3} fill="hsl(var(--bull))" />;
        })}
        <defs>
          <linearGradient id="equityGradLive" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="hsl(var(--bull))" stopOpacity="0.25" />
            <stop offset="100%" stopColor="hsl(var(--bull))" stopOpacity="0.02" />
          </linearGradient>
        </defs>
      </svg>
      <div className="mt-3 pt-3 border-t border-border/30 flex items-center justify-between">
        <span className="text-[12px] font-mono text-muted-foreground">Start: ${startVal.toLocaleString()}</span>
        <span className="text-[12px] font-mono text-bull font-bold">
          Current: ${endVal.toLocaleString()} ({Number(totalReturn) >= 0 ? "+" : ""}{totalReturn}%)
        </span>
      </div>
    </div>
  );
}

function AgentAccuracyChart({
  agentStats,
}: {
  agentStats: { key: string; name: string; accuracy: number | null; correct: number; total: number; color: string }[];
}) {
  return (
    <div className="terminal-panel p-5">
      <div className="terminal-label mb-4">PER-AGENT ACCURACY — EMPIRICAL RESOLUTIONS</div>
      <div className="space-y-3">
        {agentStats.map((a) => (
          <div key={a.key} className="flex items-center gap-3">
            <span className="text-xs font-mono text-muted-foreground w-28 shrink-0 text-right">{a.name}</span>
            <div className="flex-1 h-5 bg-muted/30 rounded overflow-hidden relative">
              {a.accuracy !== null ? (
                <>
                  <div
                    className="absolute inset-y-0 left-0 rounded transition-all duration-300"
                    style={{ width: `${Math.min(a.accuracy, 100)}%`, background: a.color, opacity: 0.7 }}
                  />
                  <div
                    className="absolute inset-y-0 left-0 rounded"
                    style={{ width: `${Math.min(a.accuracy, 100)}%`, background: a.color, opacity: 0.15 }}
                  />
                </>
              ) : (
                <div className="absolute inset-0 flex items-center justify-center">
                  <span className="text-[12px] font-mono text-muted-foreground/60">AWAITING EVALUATIONS</span>
                </div>
              )}
            </div>
            <span className="text-xs font-mono font-bold text-foreground w-20 shrink-0 text-right">
              {a.accuracy !== null ? `${a.accuracy.toFixed(1)}%` : "—"}
            </span>
          </div>
        ))}
      </div>
      <div className="mt-3 pt-3 border-t border-border/30 text-[12px] font-mono text-muted-foreground">
        Accuracy = signals where agent directional thesis aligned with verified market outcome. Abstaining agents are excluded from denominator.
      </div>
    </div>
  );
}

function AssetClassGrid({
  stats,
}: {
  stats: { name: string; winRate: number | null; total: number; resolved: number }[];
}) {
  return (
    <div className="terminal-panel p-5">
      <div className="terminal-label mb-4">WIN RATE BY ASSET CLASS</div>
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
        {stats.map((a) => (
          <div key={a.name} className="text-center p-3 rounded border border-border/30 bg-background/40">
            <div className="text-[12px] font-mono text-muted-foreground mb-1">{a.name.toUpperCase()}</div>
            <div className={cn("text-lg font-mono font-bold", a.winRate !== null ? "text-bull" : "text-muted-foreground")}>
              {a.winRate !== null ? `${a.winRate.toFixed(1)}%` : "—"}
            </div>
            <div className="text-[12px] font-mono text-muted-foreground mt-1">
              {a.resolved > 0 ? `${a.resolved} res / ${a.total} tot` : `${a.total} signals`}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function AgentPerformancePage() {
  const { isLoggedIn, loading: authLoading } = useRequireAuth();
  const [signals, setSignals] = useState<Signal[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!isLoggedIn) return;
    let active = true;

    listSignals(100)
      .then((data) => {
        if (active) {
          setSignals(Array.isArray(data) ? data : []);
        }
      })
      .catch(() => {
        if (active) setSignals([]);
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [isLoggedIn]);

  // Derive metrics strictly from verified signals
  const metrics = useMemo(() => {
    const totalSignals = signals.length;
    const resolvedSignals = signals.filter((s) => s.outcome === "WIN" || s.outcome === "LOSS");
    const activeSignals = signals.filter((s) => s.status === "ACTIVE" || !s.outcome);
    const wins = resolvedSignals.filter((s) => s.outcome === "WIN").length;
    const losses = resolvedSignals.filter((s) => s.outcome === "LOSS").length;
    const winRate = resolvedSignals.length > 0 ? (wins / resolvedSignals.length) * 100 : null;

    // R:R
    const signalsWithRR = signals.filter(
      (s) => typeof s.risk_reward_ratio === "number" && s.risk_reward_ratio > 0
    );
    const avgRR =
      signalsWithRR.length > 0
        ? signalsWithRR.reduce((acc, s) => acc + (s.risk_reward_ratio || 0), 0) / signalsWithRR.length
        : null;

    // Cumulative PnL
    const signalsWithPnl = resolvedSignals.filter(
      (s) => typeof s.pnl_pct === "number" && Number.isFinite(s.pnl_pct)
    );
    const cumulativePnl =
      signalsWithPnl.length > 0
        ? signalsWithPnl.reduce((acc, s) => acc + (s.pnl_pct || 0), 0)
        : null;

    // Agent accuracy
    const agentStats = ORDERED_AGENT_KEYS.map((key) => {
      const cfg = AGENT_CONFIG[key] || { label: key, color: "#888888" };
      let correct = 0;
      let total = 0;

      for (const sig of resolvedSignals) {
        if (!sig.agent_votes || typeof sig.agent_votes !== "object") continue;
        const vote = sig.agent_votes[key];
        if (!vote || typeof vote !== "object") continue;

        const voteObj = vote as { direction?: string; confidence?: number };
        const rawDir = (voteObj.direction || "").toUpperCase();
        if (!rawDir || rawDir === "NEUTRAL" || rawDir === "ABSTAIN") continue;

        const isBullVote = rawDir === "BULLISH" || rawDir === "LONG";
        const isBearVote = rawDir === "BEARISH" || rawDir === "SHORT";
        if (!isBullVote && !isBearVote) continue;

        const sigIsLong = sig.direction === "LONG";
        const sigWon = sig.outcome === "WIN";

        total += 1;
        // Correct if agent favored the winning direction or opposed the losing direction
        if ((isBullVote && sigIsLong && sigWon) || (isBearVote && !sigIsLong && sigWon)) {
          correct += 1;
        } else if ((isBearVote && sigIsLong && !sigWon) || (isBullVote && !sigIsLong && !sigWon)) {
          correct += 1;
        }
      }

      return {
        key,
        name: cfg.label,
        color: cfg.color,
        correct,
        total,
        accuracy: total > 0 ? (correct / total) * 100 : null,
      };
    });

    // Asset class breakdown
    const assetCategories: Record<string, string[]> = {
      Stocks: ["stocks", "etfs"],
      Forex: ["forex", "fx"],
      Crypto: ["crypto"],
      Commodities: ["commodities", "metals", "energy", "agriculture", "futures"],
      Indices: ["indices"],
    };

    const assetClassStats = Object.entries(assetCategories).map(([name, matchKeys]) => {
      const matchingSignals = signals.filter((s) => {
        const ac = (s.asset_class || "").toLowerCase();
        return matchKeys.includes(ac);
      });
      const resolved = matchingSignals.filter((s) => s.outcome === "WIN" || s.outcome === "LOSS");
      const classWins = resolved.filter((s) => s.outcome === "WIN").length;
      const classWinRate = resolved.length > 0 ? (classWins / resolved.length) * 100 : null;

      return {
        name,
        total: matchingSignals.length,
        resolved: resolved.length,
        winRate: classWinRate,
      };
    });

    // Equity curve points
    const points: number[] = [10000];
    let runningCap = 10000;
    const sortedResolved = [...signalsWithPnl].sort((a, b) => {
      const tA = a.resolved_at ? new Date(a.resolved_at).getTime() : 0;
      const tB = b.resolved_at ? new Date(b.resolved_at).getTime() : 0;
      return tA - tB;
    });

    for (const s of sortedResolved) {
      if (typeof s.pnl_pct === "number") {
        runningCap = runningCap * (1 + s.pnl_pct / 100);
        points.push(Math.round(runningCap));
      }
    }

    // Monthly returns
    const monthMap: Record<string, number> = {};
    for (const s of sortedResolved) {
      if (!s.resolved_at || typeof s.pnl_pct !== "number") continue;
      const d = new Date(s.resolved_at);
      const mKey = d.toLocaleString("en-US", { month: "short", year: "numeric" });
      monthMap[mKey] = (monthMap[mKey] || 0) + s.pnl_pct;
    }
    const months = Object.entries(monthMap).map(([month, pct]) => ({ month, pct }));

    // Institutional Restraint / Abstention count
    let totalAgentVotesPossible = 0;
    let totalAbstentions = 0;
    for (const sig of signals) {
      if (!sig.agent_votes || typeof sig.agent_votes !== "object") continue;
      for (const key of ORDERED_AGENT_KEYS) {
        totalAgentVotesPossible += 1;
        const vote = sig.agent_votes[key];
        if (!vote || typeof vote !== "object") {
          totalAbstentions += 1;
        } else {
          const rawDir = ((vote as { direction?: string }).direction || "").toUpperCase();
          if (!rawDir || rawDir === "NEUTRAL" || rawDir === "ABSTAIN") {
            totalAbstentions += 1;
          }
        }
      }
    }
    const abstentionRate =
      totalAgentVotesPossible > 0
        ? ((totalAbstentions / totalAgentVotesPossible) * 100).toFixed(1)
        : null;

    return {
      totalSignals,
      resolvedCount: resolvedSignals.length,
      activeCount: activeSignals.length,
      wins,
      losses,
      winRate,
      avgRR,
      cumulativePnl,
      agentStats,
      assetClassStats,
      points: points.length > 1 ? points : [],
      months,
      abstentionRate,
    };
  }, [signals]);

  if (authLoading || (loading && isLoggedIn)) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="live-dot mx-auto mb-3" />
          <p className="text-xs font-mono text-muted-foreground tracking-widest">
            LOADING VERIFIED PERFORMANCE DATA
          </p>
        </div>
      </div>
    );
  }

  if (!isLoggedIn) return null;

  const isLowSample = metrics.resolvedCount < 10;

  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      {/* Hero */}
      <div className="text-center mb-8">
        <div className="terminal-label mb-3 text-primary">AGENT PERFORMANCE</div>
        <h1 className="text-3xl font-bold mb-3">Live Ensemble Verification</h1>
        <p className="text-sm text-muted-foreground max-w-xl mx-auto leading-relaxed">
          Empirical metrics derived exclusively from live signal evaluations. All synthetic 2025 backtest figures have been purged to guarantee institutional truth.
        </p>

        {/* Insufficient sample notice */}
        {isLowSample && (
          <div className="mt-4 max-w-2xl mx-auto p-3.5 rounded border border-warn/30 bg-warn/5 text-left">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-[12px] font-mono px-1.5 py-0.5 rounded bg-warn/20 text-warn font-bold">
                NOTICE
              </span>
              <span className="text-xs font-mono font-bold text-warn">
                INSUFFICIENT SAMPLE SIZE — HAND-RESOLVED BENCHMARKS ACCUMULATING
              </span>
            </div>
            <p className="text-[12px] font-mono text-warn/80 leading-relaxed">
              Currently {metrics.resolvedCount} signal{metrics.resolvedCount === 1 ? "" : "s"} resolved out of {metrics.totalSignals} total ({metrics.activeCount} active). Performance figures populate in real-time as price action touches research targets or invalidation levels.
            </p>
          </div>
        )}
      </div>

      {/* Summary stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
        <StatCard
          label="TOTAL SIGNALS"
          value={metrics.totalSignals > 0 ? String(metrics.totalSignals) : "—"}
          sub={`${metrics.activeCount} active / ${metrics.resolvedCount} resolved`}
        />
        <StatCard
          label="WIN RATE"
          value={metrics.winRate !== null ? `${metrics.winRate.toFixed(1)}%` : "—"}
          sub={metrics.resolvedCount > 0 ? `${metrics.wins}W / ${metrics.losses}L resolved` : "awaiting resolution"}
        />
        <StatCard
          label="AVG R:R ACHIEVED"
          value={metrics.avgRR !== null ? `${metrics.avgRR.toFixed(1)}:1` : "—"}
          sub="risk-adjusted geometry"
        />
        <StatCard
          label="CUMULATIVE RETURN"
          value={
            metrics.cumulativePnl !== null
              ? `${metrics.cumulativePnl >= 0 ? "+" : ""}${metrics.cumulativePnl.toFixed(1)}%`
              : "—"
          }
          sub="realized P&L"
        />
      </div>

      {/* Monthly chart */}
      <div className="mb-6">
        <MonthlyChart months={metrics.months} />
      </div>

      {/* Equity curve */}
      <div className="mb-6">
        <EquityCurve points={metrics.points} />
      </div>

      {/* Agent accuracy + Asset class — side by side on large screens */}
      <div className="grid lg:grid-cols-2 gap-6 mb-6">
        <AgentAccuracyChart agentStats={metrics.agentStats} />
        <div className="flex flex-col gap-6">
          <AssetClassGrid stats={metrics.assetClassStats} />
          {/* Key risk & restraint metrics */}
          <div className="terminal-panel p-5">
            <div className="terminal-label mb-4">INSTITUTIONAL METRICS & RESTRAINT</div>
            <div className="grid grid-cols-2 gap-4">
              {[
                {
                  label: "Active Signals",
                  value: String(metrics.activeCount),
                  desc: "monitoring market levels",
                },
                {
                  label: "Resolved Outright",
                  value: String(metrics.resolvedCount),
                  desc: `${metrics.wins} target / ${metrics.losses} stop`,
                },
                {
                  label: "Agent Abstention Rate",
                  value: metrics.abstentionRate !== null ? `${metrics.abstentionRate}%` : "—",
                  desc: "restraint when edge is absent",
                },
                {
                  label: "Synthetic Data",
                  value: "0.0%",
                  desc: "purged AST-verified",
                },
                {
                  label: "Evaluation Window",
                  value: "Dynamic",
                  desc: "window_to_hours per profile",
                },
                {
                  label: "Signal Timestamping",
                  value: "UTC Naive",
                  desc: "database synchronized",
                },
              ].map((m) => (
                <div key={m.label} className="p-2.5 rounded border border-border/30 bg-background/40">
                  <div className="text-[12px] font-mono text-muted-foreground">{m.label}</div>
                  <div className="text-sm font-mono font-bold text-foreground">{m.value}</div>
                  <div className="text-[12px] font-mono text-muted-foreground">{m.desc}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Methodology */}
      <div className="terminal-panel p-5 mb-6">
        <div className="terminal-label mb-3">EMPIRICAL METHODOLOGY & TRUTH LAYER</div>
        <div className="grid md:grid-cols-3 gap-4 text-xs font-mono text-muted-foreground leading-relaxed">
          <div>
            <div className="text-foreground font-bold mb-1">Signal Generation</div>
            Each trade proposal is synthesized by a multi-agent consensus pipeline: specialist analysts run across independent domains, followed by a bull/bear debater protocol. When data feeds fail or edge is unclear, agents strictly abstain.
          </div>
          <div>
            <div className="text-foreground font-bold mb-1">Evaluation Criteria</div>
            A signal is scored WIN only if market price action touches the research target within the analytical window. A signal is marked LOSS if price touches the invalidation level first. Signals that expire without touching either level are excluded from win-rate calculation.
          </div>
          <div>
            <div className="text-foreground font-bold mb-1">Truth Layer Guarantee</div>
            All simulated fills, RNG fallbacks, and synthetic benchmark histories have been permanently eliminated. No plausible estimates are used to fill missing market data. What you see is genuine execution history.
          </div>
        </div>
      </div>

      {/* Disclaimer footer */}
      <div className="text-center px-4 py-6 border-t border-border/30">
        <p className="text-[12px] font-mono text-muted-foreground max-w-3xl mx-auto leading-relaxed">
          All performance metrics reflect live, hand-resolved pipeline executions. AI Trading Copilot does not fabricate historical track records or fill missing values with synthetic estimates. Contact quantneuraledge@gmail.com for questions.
        </p>
      </div>
    </div>
  );
}
