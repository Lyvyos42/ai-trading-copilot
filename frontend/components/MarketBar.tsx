"use client";

import { useEffect, useState, useRef } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Tick {
  symbol:    string;
  price:     number;
  change:    number;
  changePct: number;
}

// Seed prices — shown instantly on first render and used as fallback if backend is unavailable.
// Also clamps jitter so the bar never drifts far from real prices between refreshes.
const SEED_TICKS: Tick[] = [
  { symbol: "NVDA",     price: 116.85,  change: -0.38,   changePct: -0.32 },
  { symbol: "TSLA",     price: 192.97,  change: -1.47,   changePct: -0.76 },
  { symbol: "AAPL",     price: 225.59,  change:  0.90,   changePct:  0.40 },
  { symbol: "BTC",      price: 82911,   change: -312,    changePct: -0.38 },
  { symbol: "ETH",      price: 2818,    change:   0.6,   changePct:  0.02 },
  { symbol: "EUR/USD",  price: 1.0855,  change:  0.0009, changePct:  0.08 },
  { symbol: "GBP/USD",  price: 1.2988,  change: -0.0040, changePct: -0.31 },
  { symbol: "USD/JPY",  price: 148.65,  change:  0.15,   changePct:  0.10 },
  { symbol: "GOLD",     price: 3097.0,  change: -5.3,    changePct: -0.17 },
  { symbol: "SILVER",   price: 34.37,   change: -0.13,   changePct: -0.38 },
  { symbol: "OIL(WTI)", price: 68.33,   change: -0.07,   changePct: -0.10 },
  { symbol: "^VIX",     price: 19.88,   change:  0.03,   changePct:  0.15 },
  { symbol: "DXY",      price: 103.54,  change: -0.27,   changePct: -0.26 },
  { symbol: "US10Y",    price: 4.293,   change:  0.004,  changePct:  0.09 },
  { symbol: "SPY",      price: 558.88,  change: -0.11,   changePct: -0.02 },
  { symbol: "QQQ",      price: 472.96,  change:  0.03,   changePct:  0.01 },
];

function fmt(tick: Tick) {
  if (tick.symbol === "US10Y")                          return tick.price.toFixed(3) + "%";
  if (tick.price > 10000)                              return tick.price.toLocaleString("en-US", { maximumFractionDigits: 0 });
  if (tick.price > 1000)                               return tick.price.toLocaleString("en-US", { maximumFractionDigits: 0 });
  if (tick.symbol === "USD/JPY")                       return tick.price.toFixed(2);
  if (tick.symbol === "EUR/USD" || tick.symbol === "GBP/USD" || tick.symbol === "DXY")
                                                        return tick.price.toFixed(4);
  return tick.price.toFixed(2);
}

function fmtChg(tick: Tick) {
  const sign = tick.changePct >= 0 ? "+" : "";
  return `${sign}${tick.changePct.toFixed(2)}%`;
}

export function MarketBar() {
  // Start with seeds — renders immediately without waiting for the backend
  const [ticks,      setTicks]      = useState<Tick[]>(SEED_TICKS);
  const realPrices = useRef<Tick[]>(SEED_TICKS); // latest real prices to clamp jitter around

  // Fetch real prices from the backend, refresh every 5 minutes
  useEffect(() => {
    async function fetchQuotes() {
      try {
        const res = await fetch(`${API}/api/v1/market/quotes`);
        if (!res.ok) return;
        const data: Tick[] = await res.json();
        if (!data || data.length === 0) return;

        // Merge: real prices for symbols we got back, keep seeds for any that failed
        const map = new Map(data.map(t => [t.symbol, t]));
        const merged = SEED_TICKS.map(seed => map.get(seed.symbol) ?? seed);
        realPrices.current = merged;
        setTicks(merged);
      } catch {
        // Backend unavailable (cold start etc.) — keep showing seeds + jitter
      }
    }

    fetchQuotes();
    const id = setInterval(fetchQuotes, 90 * 1000); // refresh every 90s
    return () => clearInterval(id);
  }, []);

  // Micro-jitter every 3s to make the bar feel alive between real-price refreshes.
  // Prices are clamped to ±0.5% of the latest real price so they can't drift far.
  useEffect(() => {
    const id = setInterval(() => {
      setTicks(prev =>
        prev.map((t, i) => {
          const real  = realPrices.current[i]?.price ?? t.price;
          const jitter = (Math.random() - 0.5) * real * 0.0008;
          const lo    = real * 0.995;
          const hi    = real * 1.005;
          const newPrice = +(Math.max(lo, Math.min(hi, t.price + jitter)));
          const newChg   = +(newPrice - real);
          const newPct   = +(newChg / real * 100);
          const dp = real > 1000 ? 0 : real > 10 ? 2 : real > 1 ? 4 : 5;
          return {
            ...t,
            price:     +newPrice.toFixed(dp),
            change:    +newChg.toFixed(dp),
            changePct: +newPct.toFixed(2),
          };
        })
      );
    }, 3000);
    return () => clearInterval(id);
  }, []);

  const doubled = [...ticks, ...ticks];

  return (
    <div className="market-bar border-b border-border bg-[hsl(0_0%_2%)]">
      <div className="shrink-0 px-3 flex items-center gap-2 border-r border-border/50 h-full">
        <span className="live-dot" />
        <span className="font-mono text-[9px] font-bold text-muted-foreground tracking-widest">MARKETS</span>
      </div>

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
      setTime(new Date().toLocaleTimeString("en-US", { hour12: false, timeZoneName: "short" }));
    }
    update();
    const id = setInterval(update, 1000);
    return () => clearInterval(id);
  }, []);
  return <span className="font-mono text-[9px] text-muted-foreground whitespace-nowrap">{time}</span>;
}
