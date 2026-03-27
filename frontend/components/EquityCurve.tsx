"use client";

import type { EquityCurvePoint } from "@/lib/api";

interface EquityCurveProps {
  data: EquityCurvePoint[];
}

export function EquityCurve({ data }: EquityCurveProps) {
  if (!data.length) {
    return (
      <div className="panel p-6 flex items-center justify-center h-[300px]">
        <span className="text-[hsl(var(--muted-foreground))] font-mono text-xs">NO RESOLVED SIGNALS YET</span>
      </div>
    );
  }

  const W = 800;
  const H = 280;
  const PAD = { top: 20, right: 20, bottom: 30, left: 60 };
  const plotW = W - PAD.left - PAD.right;
  const plotH = H - PAD.top - PAD.bottom;

  const values = data.map((d) => d.cumulative_pnl_pct);
  const minY = Math.min(0, ...values);
  const maxY = Math.max(0, ...values);
  const rangeY = maxY - minY || 1;

  const scaleX = (i: number) => PAD.left + (i / (data.length - 1 || 1)) * plotW;
  const scaleY = (v: number) => PAD.top + plotH - ((v - minY) / rangeY) * plotH;

  const pathD = data
    .map((d, i) => `${i === 0 ? "M" : "L"} ${scaleX(i).toFixed(1)} ${scaleY(d.cumulative_pnl_pct).toFixed(1)}`)
    .join(" ");

  const areaD = `${pathD} L ${scaleX(data.length - 1).toFixed(1)} ${scaleY(0).toFixed(1)} L ${scaleX(0).toFixed(1)} ${scaleY(0).toFixed(1)} Z`;

  const lastVal = values[values.length - 1];
  const isPositive = lastVal >= 0;
  const strokeColor = isPositive ? "hsl(142, 65%, 42%)" : "hsl(0, 68%, 52%)";
  const fillId = isPositive ? "eq-grad-bull" : "eq-grad-bear";

  const yTicks: number[] = [];
  const step = rangeY / 4;
  for (let i = 0; i <= 4; i++) {
    yTicks.push(minY + step * i);
  }

  const zeroY = scaleY(0);

  return (
    <div className="panel p-4">
      <div className="flex items-center gap-2 mb-3">
        <span className="text-[14px] font-mono font-bold text-[hsl(var(--muted-foreground))] tracking-widest">EQUITY CURVE</span>
        <span className={`text-sm font-mono font-bold ${isPositive ? "text-bull" : "text-bear"}`}>
          {lastVal >= 0 ? "+" : ""}{lastVal.toFixed(2)}%
        </span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" preserveAspectRatio="xMidYMid meet">
        <defs>
          <linearGradient id="eq-grad-bull" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="hsl(142, 65%, 42%)" stopOpacity="0.3" />
            <stop offset="100%" stopColor="hsl(142, 65%, 42%)" stopOpacity="0" />
          </linearGradient>
          <linearGradient id="eq-grad-bear" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="hsl(0, 68%, 52%)" stopOpacity="0" />
            <stop offset="100%" stopColor="hsl(0, 68%, 52%)" stopOpacity="0.3" />
          </linearGradient>
        </defs>

        {yTicks.map((tick, i) => (
          <g key={i}>
            <line x1={PAD.left} y1={scaleY(tick)} x2={W - PAD.right} y2={scaleY(tick)} stroke="hsl(0,0%,13%)" strokeWidth="0.5" />
            <text x={PAD.left - 8} y={scaleY(tick) + 3} fill="hsl(0,0%,42%)" fontSize="9" fontFamily="monospace" textAnchor="end">
              {tick.toFixed(1)}%
            </text>
          </g>
        ))}

        <line x1={PAD.left} y1={zeroY} x2={W - PAD.right} y2={zeroY} stroke="hsl(0,0%,20%)" strokeWidth="1" strokeDasharray="4,4" />
        <path d={areaD} fill={`url(#${fillId})`} />
        <path d={pathD} fill="none" stroke={strokeColor} strokeWidth="1.5" strokeLinejoin="round" />
        <circle cx={scaleX(data.length - 1)} cy={scaleY(lastVal)} r="3" fill={strokeColor} />
      </svg>
    </div>
  );
}
