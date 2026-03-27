"use client";

import { useEffect, useRef, useState } from "react";
import type { Signal } from "@/lib/api";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface LWChart {
  addCandlestickSeries: (opts: object) => LWSeries;
  timeScale: () => { fitContent: () => void };
  applyOptions: (opts: object) => void;
  remove: () => void;
}
interface LWSeries {
  setData: (data: CandleBar[]) => void;
  createPriceLine: (opts: object) => void;
}
interface CandleBar { time: number; open: number; high: number; low: number; close: number; }

interface TradingChartProps {
  ticker: string;
  signal?: Signal | null;
  /** When true the chart fills its parent container height instead of fixed 380px */
  fillContainer?: boolean;
  period?: string;
  interval?: string;
}

export function TradingChart({ ticker, signal, fillContainer, period = "6mo", interval = "1d" }: TradingChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef     = useRef<LWChart | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function init() {
      if (!containerRef.current) return;
      setLoading(true);

      // Fetch real OHLCV from backend
      let candles: CandleBar[] = [];
      try {
        const res = await fetch(`${API}/api/v1/market/ohlcv/${encodeURIComponent(ticker)}?period=${period}&interval=${interval}`);
        if (res.ok) {
          const data = await res.json();
          candles = data.candles ?? [];
        }
      } catch (_) {}

      if (cancelled) return;

      // Destroy previous chart instance
      if (chartRef.current) {
        chartRef.current.remove();
        chartRef.current = null;
      }
      if (containerRef.current) containerRef.current.innerHTML = "";

      const lc = await import("lightweight-charts");
      if (cancelled || !containerRef.current) return;

      const width  = containerRef.current.offsetWidth  || 600;
      const height = containerRef.current.offsetHeight || 380;

      const chart = lc.createChart(containerRef.current, {
        layout: {
          background: { type: lc.ColorType.Solid, color: "transparent" },
          textColor: "rgba(180,180,180,0.6)",
          fontSize: 11,
          fontFamily: "'JetBrains Mono', monospace",
        },
        grid: {
          vertLines: { color: "rgba(255,255,255,0.04)" },
          horzLines: { color: "rgba(255,255,255,0.04)" },
        },
        crosshair: {
          vertLine: { color: "rgba(0,229,122,0.4)", labelBackgroundColor: "#111" },
          horzLine: { color: "rgba(0,229,122,0.4)", labelBackgroundColor: "#111" },
        },
        rightPriceScale: { borderColor: "rgba(255,255,255,0.08)" },
        timeScale:        { borderColor: "rgba(255,255,255,0.08)", timeVisible: true, secondsVisible: false },
        width,
        height,
      }) as unknown as LWChart;

      chartRef.current = chart;

      const candleSeries = chart.addCandlestickSeries({
        upColor:         "#00c55a",
        downColor:       "#e63946",
        borderUpColor:   "#00c55a",
        borderDownColor: "#e63946",
        wickUpColor:     "#00c55a",
        wickDownColor:   "#e63946",
      });

      candleSeries.setData(candles);

      // Overlay signal price lines if present
      if (signal && signal.ticker === ticker) {
        [
          { price: signal.entry_price,   color: "#00e5ff", title: "ENTRY", lineStyle: lc.LineStyle.Solid  },
          { price: signal.stop_loss,     color: "#e63946", title: "SL",    lineStyle: lc.LineStyle.Dashed },
          { price: signal.take_profit_1, color: "#00c55a", title: "TP1",   lineStyle: lc.LineStyle.Dotted },
          { price: signal.take_profit_2, color: "#009940", title: "TP2",   lineStyle: lc.LineStyle.Dotted },
          { price: signal.take_profit_3, color: "#006b2d", title: "TP3",   lineStyle: lc.LineStyle.Dotted },
        ].forEach((l) => candleSeries.createPriceLine({ ...l, lineWidth: 1, axisLabelVisible: true }));
      }

      chart.timeScale().fitContent();
      setLoading(false);
    }

    init();

    const handleResize = () => {
      if (!containerRef.current || !chartRef.current) return;
      const w = containerRef.current.offsetWidth;
      const h = containerRef.current.offsetHeight;
      chartRef.current.applyOptions({ width: w, height: h });
    };
    window.addEventListener("resize", handleResize);

    return () => {
      cancelled = true;
      window.removeEventListener("resize", handleResize);
      if (chartRef.current) { chartRef.current.remove(); chartRef.current = null; }
    };
  }, [ticker, period, interval]); // re-run when ticker or timeframe changes

  return (
    <div className={fillContainer ? "w-full h-full relative" : "w-full relative rounded overflow-hidden border border-border/50 bg-card"}>
      {loading && (
        <div className="absolute inset-0 flex items-center justify-center bg-background/70 z-10">
          <div className="flex items-center gap-2 text-[14px] font-mono text-muted-foreground">
            <span className="h-3 w-3 rounded-full border-2 border-primary/30 border-t-primary animate-spin" />
            LOADING {ticker}…
          </div>
        </div>
      )}
      <div
        ref={containerRef}
        style={{ width: "100%", height: fillContainer ? "100%" : "380px" }}
      />
    </div>
  );
}
