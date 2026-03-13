"use client";

import { useEffect, useRef } from "react";
import type { Signal } from "@/lib/api";

// Local interface mirroring the subset of lightweight-charts API we use
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

interface CandleBar {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
}

interface TradingChartProps {
  signal?: Signal | null;
}

export function TradingChart({ signal }: TradingChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<LWChart | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function init() {
      if (!containerRef.current) return;

      const lc = await import("lightweight-charts");
      if (cancelled || !containerRef.current) return;

      // Measure actual width — fall back to 600 if container is not yet laid out
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

      // Build seeded mock OHLCV — deterministic so it matches the signal price range
      const now = Math.floor(Date.now() / 1000);
      const DAY = 86400;
      const basePrice = signal?.entry_price || 175;
      const candleData: CandleBar[] = [];

      let price = basePrice * 0.85;
      for (let i = 120; i >= 0; i--) {
        const open = price;
        const change = (Math.sin(i * 7.3) * 0.008) + ((Math.random() - 0.48) * 0.018);
        const close = open * (1 + change);
        const high = Math.max(open, close) * (1 + Math.abs(Math.sin(i)) * 0.008);
        const low = Math.min(open, close) * (1 - Math.abs(Math.cos(i)) * 0.008);
        candleData.push({
          time: now - i * DAY,
          open: +open.toFixed(2),
          high: +high.toFixed(2),
          low: +low.toFixed(2),
          close: +close.toFixed(2),
        });
        price = close;
      }

      const candleSeries = chart.addCandlestickSeries({
        upColor: "#22c55e",
        downColor: "#ef4444",
        borderUpColor: "#22c55e",
        borderDownColor: "#ef4444",
        wickUpColor: "#22c55e",
        wickDownColor: "#ef4444",
      });

      candleSeries.setData(candleData);

      // Overlay signal price levels
      if (signal) {
        [
          { price: signal.entry_price, color: "#3b82f6", title: "Entry", lineStyle: lc.LineStyle.Solid },
          { price: signal.stop_loss, color: "#ef4444", title: "SL", lineStyle: lc.LineStyle.Dashed },
          { price: signal.take_profit_1, color: "#22c55e", title: "TP1", lineStyle: lc.LineStyle.Dotted },
          { price: signal.take_profit_2, color: "#16a34a", title: "TP2", lineStyle: lc.LineStyle.Dotted },
          { price: signal.take_profit_3, color: "#15803d", title: "TP3", lineStyle: lc.LineStyle.Dotted },
        ].forEach((l) =>
          candleSeries.createPriceLine({ ...l, lineWidth: 1, axisLabelVisible: true })
        );
      }

      chart.timeScale().fitContent();

      // Re-apply width after layout settles
      requestAnimationFrame(() => {
        if (containerRef.current && chartRef.current) {
          chartRef.current.applyOptions({ width: containerRef.current.offsetWidth });
        }
      });
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
      if (chartRef.current) {
        chartRef.current.remove();
        chartRef.current = null;
      }
    };
  }, [signal?.signal_id]);

  return (
    <div className="w-full rounded-lg overflow-hidden border border-border/50 bg-card">
      <div ref={containerRef} style={{ width: "100%", height: "380px" }} />
    </div>
  );
}
