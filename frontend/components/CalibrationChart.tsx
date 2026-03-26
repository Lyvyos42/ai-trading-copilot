"use client";

import type { CalibrationBucket } from "@/lib/api";

interface CalibrationChartProps {
  data: CalibrationBucket[];
}

export function CalibrationChart({ data }: CalibrationChartProps) {
  if (!data.length) {
    return (
      <div className="panel p-6 flex items-center justify-center h-[260px]">
        <span className="text-[hsl(var(--muted-foreground))] font-mono text-xs">NO CALIBRATION DATA YET</span>
      </div>
    );
  }

  const W = 400;
  const H = 260;
  const PAD = { top: 20, right: 20, bottom: 30, left: 50 };
  const plotW = W - PAD.left - PAD.right;
  const plotH = H - PAD.top - PAD.bottom;

  const scaleX = (v: number) => PAD.left + (v / 100) * plotW;
  const scaleY = (v: number) => PAD.top + plotH - (v / 100) * plotH;

  return (
    <div className="panel p-4">
      <div className="flex items-center gap-2 mb-3">
        <span className="text-[10px] font-mono font-bold text-[hsl(var(--muted-foreground))] tracking-widest">CONFIDENCE CALIBRATION</span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" preserveAspectRatio="xMidYMid meet">
        <line x1={scaleX(0)} y1={scaleY(0)} x2={scaleX(100)} y2={scaleY(100)} stroke="hsl(0,0%,20%)" strokeWidth="1" strokeDasharray="4,4" />

        <text x={W / 2} y={H - 4} fill="hsl(0,0%,42%)" fontSize="9" fontFamily="monospace" textAnchor="middle">CONFIDENCE %</text>
        <text x={12} y={H / 2} fill="hsl(0,0%,42%)" fontSize="9" fontFamily="monospace" textAnchor="middle" transform={`rotate(-90, 12, ${H / 2})`}>WIN RATE %</text>

        {[0, 25, 50, 75, 100].map((v) => (
          <g key={v}>
            <line x1={PAD.left} y1={scaleY(v)} x2={W - PAD.right} y2={scaleY(v)} stroke="hsl(0,0%,10%)" strokeWidth="0.5" />
            <text x={PAD.left - 6} y={scaleY(v) + 3} fill="hsl(0,0%,42%)" fontSize="8" fontFamily="monospace" textAnchor="end">{v}</text>
          </g>
        ))}

        {data.map((bucket, i) => {
          const cx = scaleX(bucket.confidence_midpoint);
          const cy = scaleY(bucket.actual_win_rate_pct);
          const r = Math.max(4, Math.min(12, bucket.total * 1.5));
          const isAboveLine = bucket.actual_win_rate_pct >= bucket.confidence_midpoint;
          return (
            <g key={i}>
              <circle
                cx={cx} cy={cy} r={r}
                fill={isAboveLine ? "hsl(142, 65%, 42%, 0.3)" : "hsl(0, 68%, 52%, 0.3)"}
                stroke={isAboveLine ? "hsl(142, 65%, 42%)" : "hsl(0, 68%, 52%)"}
                strokeWidth="1"
              />
              <text x={cx} y={cy - r - 4} fill="hsl(0,0%,60%)" fontSize="8" fontFamily="monospace" textAnchor="middle">
                {bucket.actual_win_rate_pct.toFixed(0)}%
              </text>
            </g>
          );
        })}
      </svg>
      <p className="text-[9px] font-mono text-[hsl(var(--muted-foreground))] mt-1">
        Dots above the diagonal = model is underconfident (good). Below = overconfident.
      </p>
    </div>
  );
}
