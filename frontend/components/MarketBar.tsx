"use client";

import { useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Tick {
  symbol: string;
  price: number;
  change: number;
  changePct: number;
}

// Static seed — shows immediately while real data loads
const SEED_TICKS: Tick[] = [
  { symbol: "SPY",      price: 523.40, change:  1.82, changePct:  0.35 },
  { symbol: "QQQ",      price: 441.20, change:  2.64, changePct:  0.60 },
  { symbol: "AAPL",     price: 182.63, change: -0.47, changePct: -0.26 },
  { symbol: "NVDA",     price: 875.39, change: 21.45, changePct:  2.51 },
  { symbol: "TSLA",     price: 193.57, change: -3.22, changePct: -1.64 },
  { symbol: "BTC",      price: 68421,  change: 1234,  changePct:  1.84 },
  { symbol: "ETH",      price: 3487,   change:  42.1, changePct:  1.22 },
  { symbol: "EUR/USD",  price: 1.0845, change: -0.0012, changePct: -0.11 },
  { symbol: "GBP/USD",  price: 1.2712, change:  0.0023, changePct:  0.18 },
  { symbol: "GOLD",     price: 2338.5, change: 12.4,  changePct:  0.53 },
  { symbol: "OIL(WTI)", price: 79.42,  change: -0.68, changePct: -0.85 },
  { symbol: "^VIX",     price: 14.82,  change: -0.31, changePct: -2.05 },
  { symbol: "DXY",      price: 104.32, change:  0.14, changePct:  0.13 },
  { symbol: "US10Y",    price: 4.312,  change:  0.023, changePct:  0.54 },
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

  // Periodically jitter prices to simulate live movement
  useEffect(() => {
    const id = setInterval(() => {
      setTicks(prev =>
        prev.map(t => {
          const jitter = (Math.random() - 0.49) * t.price * 0.0008;
          const newPrice = +(t.price + jitter).toFixed(t.price < 10 ? 4 : 2);
          const newChg = +(t.change + jitter).toFixed(4);
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
