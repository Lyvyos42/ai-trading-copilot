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
}

export function TradingChart({ ticker, signal }: TradingChartProps) {
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
        const res = await fetch(`${API}/api/v1/market/ohlcv/${encodeURIComponent(ticker)}`);
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
      // Clear the container
      if (containerRef.current) containerRef.current.innerHTML = "";

      const lc = await import("lightweight-charts");
      if (cancelled || !containerRef.current) return;

      const width = containerRef.current.offsetWidth || 600;

      const chart = lc.createChart(containerRef.current, {
        layout: {
          background: { type: lc.ColorType.Solid, color: "transparent" },
          textColor: "#64748b",
        },
        grid: {
          vertLines: { color: "#1e293b" },
          horzLines: { color: "#1e293b" },
        },
        crosshair: {
          vertLine: { color: "rgba(59,130,246,0.5)" },
          horzLine: { color: "rgba(59,130,246,0.5)" },
        },
        rightPriceScale: { borderColor: "#1e293b" },
        timeScale: { borderColor: "#1e293b", timeVisible: true },
        width,
        height: 380,
      }) as unknown as LWChart;

      chartRef.current = chart;

      const candleSeries = chart.addCandlestickSeries({
        upColor: "#22c55e", downColor: "#ef4444",
        borderUpColor: "#22c55e", borderDownColor: "#ef4444",
        wickUpColor: "#22c55e", wickDownColor: "#ef4444",
      });

      candleSeries.setData(candles);

      // Overlay signal price lines if present
      if (signal && signal.ticker === ticker) {
        [
          { price: signal.entry_price,    color: "#3b82f6", title: "Entry", lineStyle: lc.LineStyle.Solid },
          { price: signal.stop_loss,      color: "#ef4444", title: "SL",    lineStyle: lc.LineStyle.Dashed },
          { price: signal.take_profit_1,  color: "#22c55e", title: "TP1",   lineStyle: lc.LineStyle.Dotted },
          { price: signal.take_profit_2,  color: "#16a34a", title: "TP2",   lineStyle: lc.LineStyle.Dotted },
          { price: signal.take_profit_3,  color: "#15803d", title: "TP3",   lineStyle: lc.LineStyle.Dotted },
        ].forEach((l) => candleSeries.createPriceLine({ ...l, lineWidth: 1, axisLabelVisible: true }));
      }

      chart.timeScale().fitContent();

      requestAnimationFrame(() => {
        if (containerRef.current && chartRef.current) {
          chartRef.current.applyOptions({ width: containerRef.current.offsetWidth });
        }
      });

      setLoading(false);
    }

    init();

    const handleResize = () => {
      if (containerRef.current && chartRef.current) {
        chartRef.current.applyOptions({ width: containerRef.current.offsetWidth });
      }
    };
    window.addEventListener("resize", handleResize);

    return () => {
      cancelled = true;
      window.removeEventListener("resize", handleResize);
      if (chartRef.current) { chartRef.current.remove(); chartRef.current = null; }
    };
  }, [ticker]); // re-run whenever ticker changes

  return (
    <div className="w-full rounded-lg overflow-hidden border border-border/50 bg-card relative">
      {loading && (
        <div className="absolute inset-0 flex items-center justify-center bg-card/80 z-10">
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <span className="h-3 w-3 rounded-full border-2 border-primary/30 border-t-primary animate-spin" />
            Loading {ticker}…
          </div>
        </div>
      )}
      <div ref={containerRef} style={{ width: "100%", height: "380px" }} />
    </div>
  );
}
