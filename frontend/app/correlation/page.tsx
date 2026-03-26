"use client";

import { useState, useEffect } from "react";
import { cn } from "@/lib/utils";
import { getCorrelationMatrix, getCorrelationPair, wakeBackend, type CorrelationMatrix, type CorrelationPair } from "@/lib/api";

const PERIODS = [
  { label: "30D", value: 30 },
  { label: "60D", value: 60 },
  { label: "90D", value: 90 },
  { label: "180D", value: 180 },
];

function corrColor(v: number): string {
  // -1 = red, 0 = neutral dark, +1 = green
  if (v >= 0) {
    const g = Math.round(v * 180);
    return `rgba(0, ${g + 60}, ${Math.round(v * 80)}, ${0.15 + v * 0.55})`;
  } else {
    const r = Math.round(Math.abs(v) * 200);
    return `rgba(${r + 50}, 0, ${Math.round(Math.abs(v) * 40)}, ${0.15 + Math.abs(v) * 0.55})`;
  }
}

function corrTextColor(v: number): string {
  const abs = Math.abs(v);
  if (abs > 0.6) return "rgba(255,255,255,0.95)";
  return "rgba(255,255,255,0.6)";
}

export default function CorrelationPage() {
  const [data, setData] = useState<CorrelationMatrix | null>(null);
  const [period, setPeriod] = useState(90);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedPair, setSelectedPair] = useState<{ t1: string; t2: string } | null>(null);
  const [pairData, setPairData] = useState<CorrelationPair | null>(null);
  const [pairLoading, setPairLoading] = useState(false);

  useEffect(() => { wakeBackend(); }, []);

  useEffect(() => {
    setLoading(true);
    setError(null);
    getCorrelationMatrix(undefined, period)
      .then(setData)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [period]);

  useEffect(() => {
    if (!selectedPair) { setPairData(null); return; }
    setPairLoading(true);
    getCorrelationPair(selectedPair.t1, selectedPair.t2, period)
      .then(setPairData)
      .catch(() => setPairData(null))
      .finally(() => setPairLoading(false));
  }, [selectedPair, period]);

  return (
    <div className="min-h-screen pt-24 pb-12 px-4 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-lg font-mono font-bold text-foreground">Correlation Map</h1>
          <p className="text-xs font-mono text-muted-foreground mt-0.5">
            Rolling correlation matrix — cross-asset relationships
          </p>
        </div>
        <div className="flex items-center gap-1">
          {PERIODS.map((p) => (
            <button
              key={p.value}
              onClick={() => setPeriod(p.value)}
              className={cn(
                "text-[10px] font-mono font-bold px-2.5 py-1 rounded border transition-colors",
                period === p.value
                  ? "bg-primary/10 border-primary/50 text-primary"
                  : "border-border/40 text-muted-foreground hover:text-foreground"
              )}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {/* Color scale legend */}
      <div className="flex items-center gap-2 mb-4">
        <span className="text-[9px] font-mono text-muted-foreground">CORRELATION:</span>
        <div className="flex items-center gap-0.5">
          <span className="text-[9px] font-mono text-bear">-1.0</span>
          <div className="w-32 h-2 rounded overflow-hidden flex">
            {Array.from({ length: 20 }, (_, i) => {
              const v = -1 + (i / 19) * 2;
              return <div key={i} className="flex-1" style={{ backgroundColor: corrColor(v) }} />;
            })}
          </div>
          <span className="text-[9px] font-mono text-bull">+1.0</span>
        </div>
      </div>

      {loading ? (
        <div className="panel p-12 flex items-center justify-center">
          <div className="live-dot" />
        </div>
      ) : error ? (
        <div className="panel p-6 text-center">
          <span className="text-bear font-mono text-xs">{error}</span>
        </div>
      ) : data ? (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {/* Heatmap */}
          <div className="panel p-4 lg:col-span-2">
            <div className="flex items-center gap-2 mb-3">
              <span className="text-[10px] font-mono font-bold text-muted-foreground tracking-widest">CORRELATION MATRIX</span>
              {data.data_points > 0 && (
                <span className="text-[9px] font-mono text-muted-foreground">({data.data_points} data points)</span>
              )}
            </div>
            <div className="overflow-x-auto -mx-4 px-4" style={{ minWidth: 0 }}>
            <div className="min-w-[380px]">
            <CorrelationHeatmap
              tickers={data.tickers}
              matrix={data.matrix}
              onCellClick={(t1, t2) => setSelectedPair(t1 === t2 ? null : { t1, t2 })}
              selectedPair={selectedPair}
            />
            </div>
            </div>
          </div>

          {/* Pair detail panel */}
          <div className="panel p-4">
            <span className="text-[10px] font-mono font-bold text-muted-foreground tracking-widest">PAIR DETAIL</span>
            {!selectedPair ? (
              <div className="flex items-center justify-center h-[200px]">
                <span className="text-[10px] font-mono text-muted-foreground">Click a cell to compare</span>
              </div>
            ) : pairLoading ? (
              <div className="flex items-center justify-center h-[200px]">
                <div className="live-dot" />
              </div>
            ) : pairData ? (
              <div className="mt-3">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-mono font-bold text-foreground">
                    {pairData.t1} vs {pairData.t2}
                  </span>
                  <span className={cn(
                    "text-[10px] font-mono font-bold px-1.5 py-0.5 rounded border",
                    pairData.correlation >= 0.5 ? "text-bull bg-bull/10 border-bull/20" :
                    pairData.correlation <= -0.5 ? "text-bear bg-bear/10 border-bear/20" :
                    "text-muted-foreground bg-muted border-border/30"
                  )}>
                    r = {pairData.correlation.toFixed(3)}
                  </span>
                </div>
                {pairData.series.length > 0 ? (
                  <PairChart series={pairData.series} t1={pairData.t1} t2={pairData.t2} />
                ) : (
                  <div className="text-[10px] font-mono text-muted-foreground text-center py-8">No data</div>
                )}
              </div>
            ) : (
              <div className="text-[10px] font-mono text-muted-foreground text-center py-8">Failed to load</div>
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}

/* ── Heatmap SVG Component ─────────────────────────────────────── */

function CorrelationHeatmap({
  tickers, matrix, onCellClick, selectedPair,
}: {
  tickers: string[];
  matrix: number[][];
  onCellClick: (t1: string, t2: string) => void;
  selectedPair: { t1: string; t2: string } | null;
}) {
  const n = tickers.length;
  const CELL = 52;
  const LABEL = 70;
  const W = LABEL + n * CELL;
  const H = LABEL + n * CELL;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" preserveAspectRatio="xMidYMid meet">
      {/* Column labels */}
      {tickers.map((t, i) => (
        <text
          key={`col-${i}`}
          x={LABEL + i * CELL + CELL / 2}
          y={LABEL - 6}
          fill="hsl(0,0%,50%)"
          fontSize="9"
          fontFamily="monospace"
          textAnchor="middle"
        >
          {t.replace("-USD", "").replace("=X", "")}
        </text>
      ))}

      {/* Row labels + cells */}
      {tickers.map((rowTicker, i) => (
        <g key={`row-${i}`}>
          <text
            x={LABEL - 6}
            y={LABEL + i * CELL + CELL / 2 + 3}
            fill="hsl(0,0%,50%)"
            fontSize="9"
            fontFamily="monospace"
            textAnchor="end"
          >
            {rowTicker.replace("-USD", "").replace("=X", "")}
          </text>
          {tickers.map((colTicker, j) => {
            const val = matrix[i]?.[j] ?? 0;
            const isSelected = selectedPair &&
              ((selectedPair.t1 === rowTicker && selectedPair.t2 === colTicker) ||
               (selectedPair.t1 === colTicker && selectedPair.t2 === rowTicker));
            return (
              <g
                key={`cell-${i}-${j}`}
                onClick={() => onCellClick(rowTicker, colTicker)}
                style={{ cursor: i === j ? "default" : "pointer" }}
              >
                <rect
                  x={LABEL + j * CELL + 1}
                  y={LABEL + i * CELL + 1}
                  width={CELL - 2}
                  height={CELL - 2}
                  rx="3"
                  fill={corrColor(val)}
                  stroke={isSelected ? "hsl(142, 65%, 50%)" : "transparent"}
                  strokeWidth={isSelected ? 2 : 0}
                />
                <text
                  x={LABEL + j * CELL + CELL / 2}
                  y={LABEL + i * CELL + CELL / 2 + 3.5}
                  fill={corrTextColor(val)}
                  fontSize="10"
                  fontFamily="monospace"
                  fontWeight="bold"
                  textAnchor="middle"
                >
                  {val.toFixed(2)}
                </text>
              </g>
            );
          })}
        </g>
      ))}
    </svg>
  );
}

/* ── Pair Overlay Chart ────────────────────────────────────────── */

function PairChart({ series, t1, t2 }: { series: { date: string; v1: number; v2: number }[]; t1: string; t2: string }) {
  const W = 280;
  const H = 180;
  const PAD = { top: 15, right: 10, bottom: 20, left: 35 };
  const plotW = W - PAD.left - PAD.right;
  const plotH = H - PAD.top - PAD.bottom;

  const allVals = series.flatMap((s) => [s.v1, s.v2]);
  const minV = Math.min(...allVals);
  const maxV = Math.max(...allVals);
  const range = maxV - minV || 1;

  const scaleX = (i: number) => PAD.left + (i / (series.length - 1)) * plotW;
  const scaleY = (v: number) => PAD.top + plotH - ((v - minV) / range) * plotH;

  const line1 = series.map((s, i) => `${scaleX(i)},${scaleY(s.v1)}`).join(" ");
  const line2 = series.map((s, i) => `${scaleX(i)},${scaleY(s.v2)}`).join(" ");

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" preserveAspectRatio="xMidYMid meet">
      {/* 100 baseline */}
      <line
        x1={PAD.left} y1={scaleY(100)} x2={W - PAD.right} y2={scaleY(100)}
        stroke="hsl(0,0%,25%)" strokeWidth="0.5" strokeDasharray="3,3"
      />
      <text x={PAD.left - 4} y={scaleY(100) + 3} fill="hsl(0,0%,40%)" fontSize="7" fontFamily="monospace" textAnchor="end">100</text>

      {/* Y-axis ticks */}
      {[minV, maxV].map((v) => (
        <text key={v} x={PAD.left - 4} y={scaleY(v) + 3} fill="hsl(0,0%,40%)" fontSize="7" fontFamily="monospace" textAnchor="end">
          {v.toFixed(0)}
        </text>
      ))}

      {/* Lines */}
      <polyline points={line1} fill="none" stroke="hsl(142, 65%, 50%)" strokeWidth="1.5" />
      <polyline points={line2} fill="none" stroke="hsl(38, 85%, 55%)" strokeWidth="1.5" />

      {/* Legend */}
      <line x1={PAD.left} y1={H - 4} x2={PAD.left + 12} y2={H - 4} stroke="hsl(142, 65%, 50%)" strokeWidth="1.5" />
      <text x={PAD.left + 16} y={H - 1} fill="hsl(142, 65%, 50%)" fontSize="8" fontFamily="monospace">
        {t1.replace("-USD", "").replace("=X", "")}
      </text>
      <line x1={PAD.left + 70} y1={H - 4} x2={PAD.left + 82} y2={H - 4} stroke="hsl(38, 85%, 55%)" strokeWidth="1.5" />
      <text x={PAD.left + 86} y={H - 1} fill="hsl(38, 85%, 55%)" fontSize="8" fontFamily="monospace">
        {t2.replace("-USD", "").replace("=X", "")}
      </text>
    </svg>
  );
}
