"use client";

import { useState } from "react";
import { Sparkles, Activity } from "lucide-react";
import { cn, formatPrice } from "@/lib/utils";
import type { Signal } from "@/lib/api";

interface ChartHolographicOverlayProps {
  signal: Signal | null;
  ticker: string;
  interval?: string;
}

export function ChartHolographicOverlay({
  signal,
  ticker,
  interval = "5m",
}: ChartHolographicOverlayProps) {
  const [showVectors, setShowVectors] = useState(true);
  const [showCallouts, setShowCallouts] = useState(true);

  const isShort = signal?.direction === "SHORT";
  const entry = signal?.entry_price || signal?.current_price;
  const target = signal?.research_target || signal?.take_profit_1;
  const stopLoss = signal?.invalidation_level || signal?.stop_loss;

  // Formatted price strings or defaults
  const displayPrice = entry ? formatPrice(entry, ticker) : "$4,429.82";
  const displayTarget = target ? formatPrice(target, ticker) : "$4,510.00";
  const displayStop = stopLoss ? formatPrice(stopLoss, ticker) : "$4,390.00";

  const targetDelta =
    target && entry && entry > 0
      ? isShort
        ? ((entry - target) / entry) * 100
        : ((target - entry) / entry) * 100
      : 2.8;

  const stopDelta =
    stopLoss && entry && entry > 0
      ? isShort
        ? ((stopLoss - entry) / entry) * 100
        : ((entry - stopLoss) / entry) * 100
      : 0.9;

  return (
    <div className="absolute inset-0 pointer-events-none overflow-hidden z-10 select-none">
      {/* HUD Control Pills (Top Right) */}
      <div className="absolute top-3 right-16 flex items-center gap-1.5 pointer-events-auto z-20">
        <button
          onClick={() => setShowVectors(!showVectors)}
          className={cn(
            "px-2 py-0.5 rounded text-[9px] font-mono font-bold border transition-colors flex items-center gap-1 backdrop-blur-md shadow-lg",
            showVectors
              ? "bg-primary/20 text-primary border-primary/50 shadow-[0_0_10px_rgba(212,162,64,0.2)]"
              : "bg-surface-2/80 text-muted-foreground border-border/40 hover:text-foreground"
          )}
          title="Toggle 2027 Holographic Target Vectors"
        >
          <Sparkles className="h-2.5 w-2.5" />
          <span>HOLO VECTORS: {showVectors ? "ON" : "OFF"}</span>
        </button>

        <button
          onClick={() => setShowCallouts(!showCallouts)}
          className={cn(
            "px-2 py-0.5 rounded text-[9px] font-mono font-bold border transition-colors flex items-center gap-1 backdrop-blur-md shadow-lg",
            showCallouts
              ? "bg-surface-3/90 text-foreground border-border/60"
              : "bg-surface-2/80 text-muted-foreground border-border/40 hover:text-foreground"
          )}
          title="Toggle Telemetry Callout Pills"
        >
          <Activity className="h-2.5 w-2.5" />
          <span>HUD: {showCallouts ? "ON" : "OFF"}</span>
        </button>
      </div>

      {/* SVG Holographic Vector Projections Layer */}
      {showVectors && (
        <svg
          className="w-full h-full absolute inset-0"
          viewBox="0 0 1000 600"
          preserveAspectRatio="none"
        >
          <defs>
            {/* Emerald glow filter for Bullish Target Rays */}
            <filter id="glow-emerald" x="-30%" y="-30%" width="160%" height="160%">
              <feDropShadow dx="0" dy="0" stdDeviation="3" floodColor="#10b981" floodOpacity="0.8" />
            </filter>

            {/* Crimson glow filter for Stop Loss Vectors */}
            <filter id="glow-crimson" x="-30%" y="-30%" width="160%" height="160%">
              <feDropShadow dx="0" dy="0" stdDeviation="3" floodColor="#ef4444" floodOpacity="0.8" />
            </filter>

            {/* Arrowhead Markers */}
            <marker
              id="arrow-emerald"
              viewBox="0 0 10 10"
              refX="8"
              refY="5"
              markerWidth="6"
              markerHeight="6"
              orient="auto-start-reverse"
            >
              <path d="M 0 1 L 10 5 L 0 9 z" fill="#10b981" />
            </marker>

            <marker
              id="arrow-crimson"
              viewBox="0 0 10 10"
              refX="8"
              refY="5"
              markerWidth="6"
              markerHeight="6"
              orient="auto-start-reverse"
            >
              <path d="M 0 1 L 10 5 L 0 9 z" fill="#ef4444" />
            </marker>
          </defs>

          {/* Pivot Origin Marker */}
          <circle cx="530" cy="340" r="4" fill="#D4A240" filter="url(#glow-emerald)" />
          <circle cx="530" cy="340" r="8" fill="none" stroke="#D4A240" strokeWidth="1" strokeDasharray="2 2" className="animate-pulse" />

          {/* TARGET PROJECTION RAYS (Emerald Neon) */}
          {/* Ray 1: Upper Bound */}
          <line
            x1="530"
            y1="340"
            x2="680"
            y2="110"
            stroke="#10b981"
            strokeWidth="2"
            filter="url(#glow-emerald)"
            markerEnd="url(#arrow-emerald)"
          />

          {/* Ray 2: Target 1 Projection */}
          <line
            x1="530"
            y1="340"
            x2="670"
            y2="170"
            stroke="#10b981"
            strokeWidth="1.8"
            filter="url(#glow-emerald)"
            markerEnd="url(#arrow-emerald)"
          />

          {/* Ray 3: Target 2 Projection */}
          <line
            x1="530"
            y1="340"
            x2="695"
            y2="215"
            stroke="#10b981"
            strokeWidth="1.5"
            strokeDasharray="4 2"
            filter="url(#glow-emerald)"
            markerEnd="url(#arrow-emerald)"
          />

          {/* Horizontal Level Axis Projection */}
          <line
            x1="670"
            y1="170"
            x2="770"
            y2="170"
            stroke="#10b981"
            strokeWidth="1.2"
            strokeDasharray="3 3"
          />

          {/* Text Labels on SVG */}
          <text
            x="630"
            y="95"
            fill="#10b981"
            fontFamily="monospace"
            fontSize="11"
            fontWeight="bold"
            letterSpacing="0.05em"
            filter="url(#glow-emerald)"
          >
            TARGET PROJECTION (+{targetDelta.toFixed(1)}%)
          </text>

          <text
            x="680"
            y="166"
            fill="#10b981"
            fontFamily="monospace"
            fontSize="10"
            fontWeight="bold"
          >
            TARGET 1
          </text>

          <text
            x="705"
            y="212"
            fill="#10b981"
            fontFamily="monospace"
            fontSize="10"
            fontWeight="bold"
          >
            TARGET 2
          </text>

          {/* STOP LOSS RAYS (Crimson Neon) */}
          {/* Ray 1: Stop Loss Primary */}
          <line
            x1="530"
            y1="340"
            x2="710"
            y2="440"
            stroke="#ef4444"
            strokeWidth="1.8"
            filter="url(#glow-crimson)"
            markerEnd="url(#arrow-crimson)"
          />

          {/* Ray 2: Downside Invalidation Vector */}
          <line
            x1="530"
            y1="340"
            x2="680"
            y2="485"
            stroke="#ef4444"
            strokeWidth="1.4"
            strokeDasharray="4 2"
            filter="url(#glow-crimson)"
            markerEnd="url(#arrow-crimson)"
          />

          <text
            x="665"
            y="435"
            fill="#ef4444"
            fontFamily="monospace"
            fontSize="10"
            fontWeight="bold"
            letterSpacing="0.05em"
            filter="url(#glow-crimson)"
          >
            STOP LOSS (-{stopDelta.toFixed(1)}%)
          </text>

          <text
            x="688"
            y="480"
            fill="#ef4444"
            fontFamily="monospace"
            fontSize="10"
            fontWeight="bold"
          >
            VECTORS
          </text>
        </svg>
      )}

      {/* Floating Holographic Telemetry Glass Callouts */}
      {showCallouts && (
        <>
          {/* Callout 1 (Pivot Telemetry Badge) */}
          <div
            className="absolute left-[44%] top-[24%] pointer-events-auto group animate-fade-in"
            style={{ transform: "translate(-50%, -50%)" }}
          >
            <div className="bg-surface-1/90 backdrop-blur-md border border-border/80 rounded px-2.5 py-1.5 shadow-[0_0_20px_rgba(0,0,0,0.8)] font-mono text-[10px] space-y-0.5 border-t-primary/50">
              <div className="flex items-center justify-between gap-3 text-foreground">
                <span className="text-muted-foreground">PRICE:</span>
                <span className="font-bold text-foreground">{displayPrice}</span>
              </div>
              <div className="flex items-center justify-between gap-3 text-foreground">
                <span className="text-muted-foreground">VOL:</span>
                <span className="font-bold text-primary">1.5M</span>
              </div>
              <div className="flex items-center justify-between gap-3 text-foreground">
                <span className="text-muted-foreground">RSI(14):</span>
                <span className="font-bold text-bull">68.4</span>
              </div>
            </div>
            {/* SVG Connecting Stem */}
            <svg className="w-8 h-8 -mt-0.5 ml-4 overflow-visible" viewBox="0 0 30 30">
              <line x1="5" y1="0" x2="25" y2="25" stroke="rgba(212,162,64,0.6)" strokeWidth="1.5" />
              <circle cx="25" cy="25" r="2.5" fill="#D4A240" />
            </svg>
          </div>

          {/* Callout 2 (Secondary Momentum Readout) */}
          <div
            className="absolute left-[62%] top-[45%] pointer-events-auto group animate-fade-in hidden sm:block"
            style={{ transform: "translate(-50%, -50%)" }}
          >
            <div className="bg-surface-1/90 backdrop-blur-md border border-border/80 rounded px-2.5 py-1.5 shadow-[0_0_20px_rgba(0,0,0,0.8)] font-mono text-[10px] space-y-0.5 border-t-bull/50">
              <div className="flex items-center justify-between gap-3 text-foreground">
                <span className="text-muted-foreground">PRICE:</span>
                <span className="font-bold text-foreground">{displayPrice}</span>
              </div>
              <div className="flex items-center justify-between gap-3 text-foreground">
                <span className="text-muted-foreground">VOL:</span>
                <span className="font-bold text-bull">1.3M</span>
              </div>
              <div className="flex items-center justify-between gap-3 text-foreground">
                <span className="text-muted-foreground">RSI:</span>
                <span className="font-bold text-primary">62.0</span>
              </div>
            </div>
            {/* SVG Connecting Stem */}
            <svg className="w-8 h-8 -mt-0.5 ml-3 overflow-visible" viewBox="0 0 30 30">
              <line x1="5" y1="0" x2="20" y2="20" stroke="rgba(34,197,94,0.6)" strokeWidth="1.5" />
              <circle cx="20" cy="20" r="2.5" fill="#10b981" />
            </svg>
          </div>

          {/* Target Price Scale Label */}
          {showVectors && (
            <div
              className="absolute right-2 top-[28%] pointer-events-auto"
              style={{ transform: "translateY(-50%)" }}
            >
              <div className="px-2 py-0.5 rounded bg-bull/20 border border-bull/50 text-bull font-mono text-[10px] font-bold shadow-[0_0_12px_rgba(16,185,129,0.3)]">
                TARGET {displayTarget}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
