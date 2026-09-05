"use client";

import { ArrowUp, ArrowDown } from "lucide-react";
import type { Signal } from "@/lib/api";
import { formatPrice } from "@/lib/utils";
import { cn } from "@/lib/utils";

interface SignalOverlayProps {
  signal: Signal | null;
  ticker: string;
}

export function SignalOverlay({ signal, ticker }: SignalOverlayProps) {
  if (!signal || signal.ticker !== ticker) return null;

  const isLong = signal.direction === "LONG";
  const rrRatio = signal.risk_reward_ratio ?? 0;

  return (
    <div className="absolute inset-0 pointer-events-none z-10">
      <div className="absolute bottom-3 left-3 pointer-events-auto">
        <div
          className={cn(
            "flex items-center gap-2 px-3 py-1.5 rounded border backdrop-blur-sm",
            "bg-background/80",
            isLong ? "border-bull/40" : "border-bear/40"
          )}
        >
          {isLong ? (
            <ArrowUp className="h-3.5 w-3.5 text-bull" />
          ) : (
            <ArrowDown className="h-3.5 w-3.5 text-bear" />
          )}
          <span
            className={cn(
              "text-[12px] font-mono font-bold",
              isLong ? "text-bull" : "text-bear"
            )}
          >
            {signal.direction}
          </span>
          <span className="text-[12px] font-mono text-muted-foreground">
            ENTRY{" "}
            <span className="text-foreground font-semibold">
              {formatPrice(signal.entry_price, signal.ticker)}
            </span>
          </span>
          <span className="text-[12px] font-mono text-muted-foreground">
            SL{" "}
            <span className="text-bear font-semibold">
              {formatPrice(signal.stop_loss, signal.ticker)}
            </span>
          </span>
          <span className="text-[12px] font-mono text-muted-foreground">
            TP{" "}
            <span className="text-bull font-semibold">
              {formatPrice(signal.take_profit_1, signal.ticker)}
            </span>
          </span>
          {rrRatio > 0 && (
            <span className="text-[12px] font-mono text-muted-foreground">
              R:R{" "}
              <span className="text-primary font-semibold">
                {rrRatio.toFixed(1)}:1
              </span>
            </span>
          )}
          <span className="text-[12px] font-mono text-muted-foreground">
            CONF{" "}
            <span className="text-primary font-semibold">
              {Math.round(signal.confidence_score)}%
            </span>
          </span>
        </div>
      </div>
    </div>
  );
}
