"use client";

import { ArrowUp, ArrowDown } from "lucide-react";
import type { Signal } from "@/lib/api";
import { formatPrice } from "@/lib/utils";
import { cn } from "@/lib/utils";

interface SignalOverlayProps {
  signal: Signal | null;
  ticker: string;
}

interface PriceLevel {
  label: string;
  price: number;
  color: string;
  bgClass: string;
  borderClass: string;
  opacity?: number;
}

function buildLevels(signal: Signal): PriceLevel[] {
  const levels: PriceLevel[] = [
    {
      label: "ENTRY",
      price: signal.entry_price,
      color: "text-primary",
      bgClass: "bg-primary/15",
      borderClass: "border-primary/40",
    },
    {
      label: "SL",
      price: signal.stop_loss,
      color: "text-bear",
      bgClass: "bg-bear/15",
      borderClass: "border-bear/40",
    },
    {
      label: "TP1",
      price: signal.take_profit_1,
      color: "text-bull",
      bgClass: "bg-bull/15",
      borderClass: "border-bull/40",
    },
    {
      label: "TP2",
      price: signal.take_profit_2,
      color: "text-bull",
      bgClass: "bg-bull/10",
      borderClass: "border-bull/30",
      opacity: 0.8,
    },
    {
      label: "TP3",
      price: signal.take_profit_3,
      color: "text-bull",
      bgClass: "bg-bull/5",
      borderClass: "border-bull/20",
      opacity: 0.6,
    },
  ];

  // Filter out zero/missing TP3 and sort highest price first
  return levels
    .filter((l) => l.price > 0)
    .sort((a, b) => b.price - a.price);
}

export function SignalOverlay({ signal, ticker }: SignalOverlayProps) {
  if (!signal || signal.ticker !== ticker) return null;

  const isLong = signal.direction === "LONG";
  const levels = buildLevels(signal);
  const currentPrice = signal.current_price ?? signal.entry_price;
  const rrRatio = signal.risk_reward_ratio ?? 0;

  // Find where current price sits relative to levels for positioning the marker
  const prices = levels.map((l) => l.price);
  const maxPrice = Math.max(...prices, currentPrice);
  const minPrice = Math.min(...prices, currentPrice);
  const priceRange = maxPrice - minPrice || 1;

  function priceToPct(price: number): number {
    // Map price to 0-100%, where 0% = top (highest price), 100% = bottom (lowest price)
    return ((maxPrice - price) / priceRange) * 100;
  }

  return (
    <div className="absolute inset-0 pointer-events-none z-10 flex">
      {/* Signal summary badge — top-left */}
      <div className="absolute top-3 left-3 pointer-events-auto">
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
              "text-[11px] font-mono font-bold",
              isLong ? "text-bull" : "text-bear"
            )}
          >
            {signal.direction}
          </span>
          <span className="text-[11px] font-mono text-muted-foreground">
            ENTRY{" "}
            <span className="text-foreground font-semibold">
              {formatPrice(signal.entry_price, signal.ticker)}
            </span>
          </span>
          {rrRatio > 0 && (
            <span className="text-[11px] font-mono text-muted-foreground">
              R:R{" "}
              <span className="text-primary font-semibold">
                {rrRatio.toFixed(1)}:1
              </span>
            </span>
          )}
          <span className="text-[11px] font-mono text-muted-foreground">
            CONF{" "}
            <span className="text-primary font-semibold">
              {Math.round(signal.confidence_score)}%
            </span>
          </span>
        </div>
      </div>

      {/* Vertical signal map strip — right side */}
      <div className="absolute top-12 bottom-8 right-3 w-[72px] pointer-events-auto">
        <div className="relative h-full w-full rounded border border-border/40 bg-background/70 backdrop-blur-sm overflow-hidden">
          {/* Direction indicator at the very top */}
          <div
            className={cn(
              "absolute top-0 left-0 right-0 flex items-center justify-center py-1 border-b",
              isLong
                ? "bg-bull/10 border-bull/20"
                : "bg-bear/10 border-bear/20"
            )}
          >
            {isLong ? (
              <ArrowUp className="h-3 w-3 text-bull" />
            ) : (
              <ArrowDown className="h-3 w-3 text-bear" />
            )}
            <span
              className={cn(
                "text-[8px] font-mono font-bold ml-0.5",
                isLong ? "text-bull" : "text-bear"
              )}
            >
              {signal.direction}
            </span>
          </div>

          {/* Price levels positioned vertically */}
          <div className="absolute top-7 bottom-1 left-0 right-0">
            {levels.map((level) => {
              const topPct = priceToPct(level.price);
              // Clamp between 0-90% to keep labels visible
              const clampedTop = Math.max(0, Math.min(90, topPct));

              return (
                <div
                  key={level.label}
                  className="absolute left-0 right-0 flex items-center"
                  style={{
                    top: `${clampedTop}%`,
                    opacity: level.opacity ?? 1,
                  }}
                >
                  <div
                    className={cn(
                      "w-full px-1 py-0.5 border-l-2",
                      level.bgClass,
                      level.borderClass
                    )}
                  >
                    <div
                      className={cn(
                        "text-[7px] font-mono font-bold leading-none",
                        level.color
                      )}
                    >
                      {level.label}
                    </div>
                    <div className="text-[8px] font-mono text-foreground/80 leading-tight mt-px">
                      {formatPrice(level.price, signal.ticker)}
                    </div>
                  </div>
                </div>
              );
            })}

            {/* Current price marker */}
            {currentPrice > 0 && (
              <div
                className="absolute left-0 right-0 flex items-center"
                style={{
                  top: `${Math.max(0, Math.min(90, priceToPct(currentPrice)))}%`,
                }}
              >
                <div className="w-full flex items-center px-1">
                  <div className="relative flex items-center gap-0.5">
                    <span className="h-1.5 w-1.5 rounded-full bg-primary animate-pulse" />
                    <span className="text-[7px] font-mono font-bold text-primary leading-none">
                      NOW
                    </span>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
