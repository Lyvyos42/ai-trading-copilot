"use client";

import { cn } from "@/lib/utils";
import type { MonthlyReturn } from "@/lib/api";

interface MonthlyHeatmapProps {
  data: MonthlyReturn[];
}

const MONTH_LABELS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export function MonthlyHeatmap({ data }: MonthlyHeatmapProps) {
  if (!data.length) {
    return (
      <div className="panel p-6 flex items-center justify-center h-[200px]">
        <span className="text-[hsl(var(--muted-foreground))] font-mono text-xs">NO MONTHLY DATA YET</span>
      </div>
    );
  }

  const byYear: Record<string, Record<number, MonthlyReturn>> = {};
  for (const m of data) {
    const [year, month] = m.month.split("-");
    if (!byYear[year]) byYear[year] = {};
    byYear[year][parseInt(month) - 1] = m;
  }

  const years = Object.keys(byYear).sort();

  function cellColor(pnl: number): string {
    if (pnl > 5) return "bg-[hsl(var(--bull)/0.2)] text-bull";
    if (pnl > 0) return "bg-[hsl(var(--bull)/0.1)] text-bull";
    if (pnl === 0) return "bg-[hsl(var(--muted))] text-[hsl(var(--muted-foreground))]";
    if (pnl > -5) return "bg-[hsl(var(--bear)/0.1)] text-bear";
    return "bg-[hsl(var(--bear)/0.2)] text-bear";
  }

  return (
    <div className="panel p-4">
      <div className="flex items-center gap-2 mb-3">
        <span className="text-[14px] font-mono font-bold text-[hsl(var(--muted-foreground))] tracking-widest">MONTHLY RETURNS</span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr>
              <th className="text-[13px] font-mono text-[hsl(var(--muted-foreground))] px-1 py-1 text-left">YEAR</th>
              {MONTH_LABELS.map((m) => (
                <th key={m} className="text-[13px] font-mono text-[hsl(var(--muted-foreground))] px-1 py-1 text-center w-[60px]">{m}</th>
              ))}
              <th className="text-[13px] font-mono text-[hsl(var(--muted-foreground))] px-1 py-1 text-center">YTD</th>
            </tr>
          </thead>
          <tbody>
            {years.map((year) => {
              const yearData = byYear[year];
              const ytd = Object.values(yearData).reduce((sum, m) => sum + m.total_pnl_pct, 0);
              return (
                <tr key={year}>
                  <td className="text-[14px] font-mono font-bold text-[hsl(var(--foreground))] px-1 py-0.5">{year}</td>
                  {Array.from({ length: 12 }, (_, i) => {
                    const m = yearData[i];
                    return (
                      <td key={i} className="px-0.5 py-0.5">
                        {m ? (
                          <div className={cn("text-center text-[14px] font-mono font-bold rounded px-1 py-1", cellColor(m.total_pnl_pct))}>
                            {m.total_pnl_pct >= 0 ? "+" : ""}{m.total_pnl_pct.toFixed(1)}%
                          </div>
                        ) : (
                          <div className="text-center text-[14px] font-mono text-[hsl(var(--muted-foreground)/0.3)] px-1 py-1">—</div>
                        )}
                      </td>
                    );
                  })}
                  <td className="px-0.5 py-0.5">
                    <div className={cn("text-center text-[14px] font-mono font-bold rounded px-1 py-1", cellColor(ytd))}>
                      {ytd >= 0 ? "+" : ""}{ytd.toFixed(1)}%
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
