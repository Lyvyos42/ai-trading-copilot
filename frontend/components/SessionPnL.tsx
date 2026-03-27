"use client";

import { DollarSign, TrendingUp, TrendingDown, BarChart2 } from "lucide-react";
import { cn } from "@/lib/utils";

interface SessionPnLProps {
  pnl: number;
  pnlPct: number;
  tradeCount: number;
  analysisCount: number;
}

export function SessionPnL({ pnl, pnlPct, tradeCount, analysisCount }: SessionPnLProps) {
  const isPositive = pnl >= 0;
  const PnLIcon = isPositive ? TrendingUp : TrendingDown;

  return (
    <div className="rounded-lg border border-border bg-background p-4">
      <div className="flex items-center gap-2 mb-3">
        <DollarSign className="h-3.5 w-3.5 text-primary" />
        <span className="text-[14px] font-mono font-bold text-muted-foreground tracking-widest">SESSION P&L</span>
      </div>

      <div className="flex items-baseline gap-2 mb-3">
        <PnLIcon className={cn("h-5 w-5", isPositive ? "text-bull" : "text-bear")} />
        <span className={cn("text-2xl font-mono font-bold", isPositive ? "text-bull" : "text-bear")}>
          ${Math.abs(pnl).toFixed(2)}
        </span>
        <span className={cn("text-sm font-mono", isPositive ? "text-bull" : "text-bear")}>
          ({pnlPct >= 0 ? "+" : ""}{pnlPct.toFixed(2)}%)
        </span>
      </div>

      <div className="flex items-center gap-4">
        <div className="flex items-center gap-1.5">
          <BarChart2 className="h-3 w-3 text-muted-foreground" />
          <span className="text-[13px] font-mono text-muted-foreground">
            Trades: <span className="text-foreground font-bold">{tradeCount}</span>
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="text-[13px] font-mono text-muted-foreground">
            Analyses: <span className="text-foreground font-bold">{analysisCount}</span>
          </span>
        </div>
      </div>
    </div>
  );
}
