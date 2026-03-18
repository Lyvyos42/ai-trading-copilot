"use client";

import { useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Tick {
  symbol: string;
  price: number;
  change: number;
  changePct: number;
}

// Static seed — approximate prices as of Mar 2026.
// Jitter keeps movement realistic; prices are clamped to ±3% of seed to prevent drift.
const SEED_TICKS: Tick[] = [
  { symbol: "SPY",      price: 558.20, change:  1.95, changePct:  0.35 },
  { symbol: "QQQ",      price: 472.80, change:  2.84, changePct:  0.60 },
  { symbol: "AAPL",     price: 224.50, change: -0.58, changePct: -0.26 },
  { symbol: "NVDA",     price: 877.40, change: 21.90, changePct:  2.56 },
  { symbol: "TSLA",     price: 192.30, change: -3.18, changePct: -1.63 },
  { symbol: "BTC",      price: 83200,  change:  1120, changePct:  1.36 },
  { symbol: "ETH",      price: 2010,   change:  28.4, changePct:  1.43 },
  { symbol: "EUR/USD",  price: 1.0852, change: -0.0009, changePct: -0.08 },
  { symbol: "GBP/USD",  price: 1.2940, change:  0.0031, changePct:  0.24 },
  { symbol: "GOLD",     price: 3045.0, change: 18.5,  changePct:  0.61 },
  { symbol: "OIL(WTI)", price: 68.40,  change: -0.72, changePct: -1.04 },
  { symbol: "^VIX",     price: 19.85,  change:  0.42, changePct:  2.16 },
  { symbol: "DXY",      price: 103.80, change: -0.22, changePct: -0.21 },
  { symbol: "US10Y",    price: 4.285,  change:  0.018, changePct:  0.42 },
];

function fmt(tick: Tick) {
  if (tick.symbol.includes("/") || tick.symbol === "DXY") {
    return tick.price.toFixed(4);
  }
  if (tick.symbol === "US10Y") return tick.price.toFixed(3) + "%";
  if (tick.price > 1000) return tick.price.toLocaleString("en-US", { maximumFractionDigits: 0 });
  return tick.price.toFixed(2);
}

function fmtChg(tick: Tick) {
  const sign = tick.changePct >= 0 ? "+" : "";
  return `${sign}${tick.changePct.toFixed(2)}%`;
}

export function MarketBar() {
  const [ticks, setTicks] = useState<Tick[]>(SEED_TICKS);

  // Periodically jitter prices to simulate live movement.
  // Prices are clamped to ±3% of the seed to prevent long-term drift.
  useEffect(() => {
    const id = setInterval(() => {
      setTicks(prev =>
        prev.map((t, i) => {
          const seed = SEED_TICKS[i].price;
          const jitter = (Math.random() - 0.49) * seed * 0.0008;
          const raw = t.price + jitter;
          const lo = seed * 0.97;
          const hi = seed * 1.03;
          const newPrice = +(Math.max(lo, Math.min(hi, raw))).toFixed(seed < 10 ? 4 : seed < 100 ? 3 : 2);
          const newChg = +(t.change + jitter * 0.3).toFixed(4);
          const newPct = +(newChg / (newPrice - newChg) * 100).toFixed(2);
          return { ...t, price: newPrice, change: newChg, changePct: newPct };
        })
      );
    }, 3000);
    return () => clearInterval(id);
  }, []);

  // Duplicate for seamless loop
  const doubled = [...ticks, ...ticks];

  return (
    <div className="market-bar border-b border-border bg-[hsl(0_0%_2%)]">
      {/* LEFT LABEL */}
      <div className="shrink-0 px-3 flex items-center gap-2 border-r border-border/50 h-full">
        <span className="live-dot" />
        <span className="font-mono text-[9px] font-bold text-muted-foreground tracking-widest">MARKETS</span>
      </div>

      {/* SCROLLING TICKERS */}
      <div className="flex-1 overflow-hidden relative">
        <div className="ticker-track">
          {doubled.map((tick, i) => {
            const up = tick.changePct >= 0;
            return (
              <div key={i} className="inline-flex items-center gap-2 px-4 border-r border-border/30 h-8 shrink-0">
                <span className="font-mono text-[10px] font-bold text-foreground">{tick.symbol}</span>
                <span className="font-mono text-[10px] text-foreground">{fmt(tick)}</span>
                <span className={`font-mono text-[9px] font-semibold ${up ? "text-bull" : "text-bear"}`}>
                  {fmtChg(tick)}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* RIGHT — timestamp */}
      <div className="shrink-0 px-3 border-l border-border/50 h-full flex items-center">
        <ClockDisplay />
      </div>
    </div>
  );
}

function ClockDisplay() {
  const [time, setTime] = useState("");
  useEffect(() => {
    function update() {
      const now = new Date();
      setTime(now.toLocaleTimeString("en-US", { hour12: false, timeZoneName: "short" }));
    }
    update();
    const id = setInterval(update, 1000);
    return () => clearInterval(id);
  }, []);
  return <span className="font-mono text-[9px] text-muted-foreground whitespace-nowrap">{time}</span>;
}
