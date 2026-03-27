"use client";

import { useEffect, useState } from "react";
import { Activity, BarChart2, Target, Zap, TrendingUp, TrendingDown } from "lucide-react";
import { cn } from "@/lib/utils";
import { wakeBackend, getPerformanceSummary, getEquityCurve, getByAssetClass, getByAgent, getCalibration, getMonthlyReturns } from "@/lib/api";
import type { PerformanceSummary, EquityCurvePoint, AssetClassPerformance, AgentPerformance, CalibrationBucket, MonthlyReturn } from "@/lib/api";
import { EquityCurve } from "@/components/EquityCurve";
import { MonthlyHeatmap } from "@/components/MonthlyHeatmap";
import { CalibrationChart } from "@/components/CalibrationChart";
import { AgentLeaderboard } from "@/components/AgentLeaderboard";
export default function PerformancePage() {
  const [summary, setSummary] = useState<PerformanceSummary | null>(null);
  const [curve, setCurve] = useState<EquityCurvePoint[]>([]);
  const [assetClasses, setAssetClasses] = useState<AssetClassPerformance[]>([]);
  const [agents, setAgents] = useState<AgentPerformance[]>([]);
  const [calibration, setCalibration] = useState<CalibrationBucket[]>([]);
  const [monthly, setMonthly] = useState<MonthlyReturn[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    wakeBackend();
    Promise.allSettled([
      getPerformanceSummary().then(setSummary),
      getEquityCurve().then((r) => setCurve(r.curve)),
      getByAssetClass().then((r) => setAssetClasses(r.asset_classes)),
      getByAgent().then((r) => setAgents(r.agents)),
      getCalibration().then((r) => setCalibration(r.calibration)),
      getMonthlyReturns().then((r) => setMonthly(r.months)),
    ]).finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="live-dot mx-auto mb-3" />
          <p className="text-[14px] font-mono text-[hsl(var(--muted-foreground))] tracking-widest">LOADING PERFORMANCE DATA</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen p-4 md:p-6 max-w-7xl mx-auto pt-16">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-xl font-bold tracking-tight">Performance Dashboard</h1>
        <p className="text-xs font-mono text-[hsl(var(--muted-foreground))] mt-1">
          Live track record — all signals, all agents, full transparency
        </p>
      </div>

      {/* Summary Cards */}
      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
          <StatCard
            label="TOTAL SIGNALS"
            value={String(summary.total_signals)}
            icon={<Activity className="h-3.5 w-3.5 text-[hsl(var(--primary))]" />}
          />
          <StatCard
            label="WIN RATE"
            value={`${summary.win_rate_pct}%`}
            icon={<Target className="h-3.5 w-3.5 text-bull" />}
            valueColor={summary.win_rate_pct >= 50 ? "text-bull" : "text-bear"}
          />
          <StatCard
            label="AVG P&L"
            value={`${summary.avg_pnl_pct >= 0 ? "+" : ""}${summary.avg_pnl_pct}%`}
            icon={summary.avg_pnl_pct >= 0 ? <TrendingUp className="h-3.5 w-3.5 text-bull" /> : <TrendingDown className="h-3.5 w-3.5 text-bear" />}
            valueColor={summary.avg_pnl_pct >= 0 ? "text-bull" : "text-bear"}
          />
          <StatCard
            label="AVG CONFIDENCE"
            value={`${summary.avg_confidence}`}
            icon={<Zap className="h-3.5 w-3.5 text-[hsl(var(--warn))]" />}
          />
        </div>
      )}

      {/* Active / Resolved badges */}
      {summary && (
        <div className="flex items-center gap-4 mb-6">
          <div className="flex items-center gap-1.5">
            <div className="live-dot" />
            <span className="text-[14px] font-mono text-[hsl(var(--muted-foreground))]">
              {summary.active_signals} ACTIVE
            </span>
          </div>
          <span className="text-[14px] font-mono text-[hsl(var(--muted-foreground))]">
            {summary.wins}W / {summary.losses}L resolved
          </span>
        </div>
      )}

      {/* Equity Curve */}
      <div className="mb-6">
        <EquityCurve data={curve} />
      </div>

      {/* Two-column: Monthly Heatmap + Asset Class Table */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
        <MonthlyHeatmap data={monthly} />

        {/* Asset Class Breakdown */}
        <div className="panel p-4">
          <div className="flex items-center gap-2 mb-3">
            <BarChart2 className="h-3.5 w-3.5 text-[hsl(var(--primary))]" />
            <span className="text-[14px] font-mono font-bold text-[hsl(var(--muted-foreground))] tracking-widest">BY ASSET CLASS</span>
          </div>
          {assetClasses.length === 0 ? (
            <div className="flex items-center justify-center h-[120px]">
              <span className="text-[hsl(var(--muted-foreground))] font-mono text-xs">NO DATA YET</span>
            </div>
          ) : (
            <table className="w-full">
              <thead>
                <tr className="border-b border-[hsl(var(--border))]">
                  <th className="text-[13px] font-mono text-[hsl(var(--muted-foreground))] py-1.5 text-left">CLASS</th>
                  <th className="text-[13px] font-mono text-[hsl(var(--muted-foreground))] py-1.5 text-right">SIGNALS</th>
                  <th className="text-[13px] font-mono text-[hsl(var(--muted-foreground))] py-1.5 text-right">WIN RATE</th>
                  <th className="text-[13px] font-mono text-[hsl(var(--muted-foreground))] py-1.5 text-right">AVG P&L</th>
                </tr>
              </thead>
              <tbody>
                {assetClasses.map((ac) => (
                  <tr key={ac.asset_class} className="border-b border-[hsl(var(--border)/0.5)]">
                    <td className="text-[13px] font-mono font-bold text-[hsl(var(--foreground))] py-1.5 uppercase">{ac.asset_class}</td>
                    <td className="text-[14px] font-mono text-[hsl(var(--muted-foreground))] text-right py-1.5">{ac.total}</td>
                    <td className={cn("text-[13px] font-mono font-bold text-right py-1.5", ac.win_rate_pct >= 50 ? "text-bull" : "text-bear")}>
                      {ac.win_rate_pct.toFixed(1)}%
                    </td>
                    <td className={cn("text-[14px] font-mono text-right py-1.5", ac.avg_pnl_pct >= 0 ? "text-bull" : "text-bear")}>
                      {ac.avg_pnl_pct >= 0 ? "+" : ""}{ac.avg_pnl_pct.toFixed(2)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* Two-column: Agent Leaderboard + Calibration */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <AgentLeaderboard data={agents} />
        <CalibrationChart data={calibration} />
      </div>
    </div>
  );
}

function StatCard({ label, value, icon, valueColor }: { label: string; value: string; icon: React.ReactNode; valueColor?: string }) {
  return (
    <div className="panel p-3">
      <div className="flex items-center gap-1.5 mb-1.5">
        {icon}
        <span className="text-[13px] font-mono font-bold text-[hsl(var(--muted-foreground))] tracking-widest">{label}</span>
      </div>
      <span className={cn("text-lg font-mono font-bold", valueColor || "text-[hsl(var(--foreground))]")}>{value}</span>
    </div>
  );
}
