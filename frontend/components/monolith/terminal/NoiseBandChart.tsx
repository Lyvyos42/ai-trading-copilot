"use client";

/**
 * Noise-area chart: the session's price against the band built from the
 * average absolute move from the 09:30 New York open (last 14 sessions).
 * Drawn as plain SVG so the marks stay crisp at terminal density.
 *
 * Reading order: price (white, gold while a position is open) against the
 * gold noise area; VWAP dashed orange; the part of the session that has not
 * happened yet shows the band only, dashed.
 */
import { useEffect, useMemo, useRef, useState } from "react";
import { minuteToClock, type NoiseBandsResponse } from "@/lib/terminal-api";
import { fmt } from "@/components/monolith/primitives";

const GOLD = "#E6A532";
const GOLD_DIM = "#B88428";
const ORANGE = "#FF8C42";
const INK = "#E0E0E0";
const MUTED = "#8F8F8F";

function useSize<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [size, setSize] = useState<{ w: number; h: number } | null>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect;
      setSize({ w: Math.round(width), h: Math.round(height) });
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, size] as const;
}

export function NoiseBandChart({ data }: { data: NoiseBandsResponse }) {
  const [ref, size] = useSize<HTMLDivElement>();
  const [cursor, setCursor] = useState<number | null>(null);
  const decimals = data.symbol === "USTEC" ? 1 : 2;
  const now = data.now_minute;
  const pts = data.points;

  const geo = useMemo(() => {
    if (!size || size.w < 120 || size.h < 120) return null;
    const narrow = size.w < 560;
    const padL = 6;
    const padR = narrow ? 62 : 74;
    const padT = 18;
    const padB = 22;
    const pw = size.w - padL - padR;
    const ph = size.h - padT - padB;

    let lo = Infinity;
    let hi = -Infinity;
    for (const p of pts) {
      lo = Math.min(lo, p.lower, p.price ?? Infinity);
      hi = Math.max(hi, p.upper, p.price ?? -Infinity);
    }
    const pad = (hi - lo) * 0.06;
    lo -= pad;
    hi += pad;

    const x = (m: number) => padL + (m / 390) * pw;
    const y = (v: number) => padT + (1 - (v - lo) / (hi - lo)) * ph;
    const line = (sel: (i: number) => number | null, from: number, to: number) => {
      let d = "";
      for (let i = from; i <= to; i++) {
        const v = sel(i);
        if (v == null) continue;
        d += `${d ? "L" : "M"}${x(i).toFixed(1)} ${y(v).toFixed(1)}`;
      }
      return d;
    };

    let area = "";
    for (let i = 0; i <= 390; i++) area += `${i ? "L" : "M"}${x(i).toFixed(1)} ${y(pts[i].upper).toFixed(1)}`;
    for (let i = 390; i >= 0; i--) area += `L${x(i).toFixed(1)} ${y(pts[i].lower).toFixed(1)}`;
    area += "Z";

    // Stretches where a position was open, for the gold overlay.
    const held: [number, number][] = [];
    let start: number | null = null;
    for (const e of data.events) {
      if (e.kind === "ENTRY_LONG" || e.kind === "ENTRY_SHORT") start = e.minute;
      else if (start != null) {
        held.push([start, e.minute]);
        start = null;
      }
    }
    if (start != null) held.push([start, now]);

    return {
      narrow, padL, padR, padT, padB, pw, ph, x, y, area, held,
      upperPast: line((i) => pts[i].upper, 0, now),
      upperNext: line((i) => pts[i].upper, now, 390),
      lowerPast: line((i) => pts[i].lower, 0, now),
      lowerNext: line((i) => pts[i].lower, now, 390),
      price: line((i) => pts[i].price, 0, now),
      vwap: line((i) => pts[i].vwap, 0, now),
      heldPaths: held.map(([a, b]) => line((i) => pts[i].price, a, b)),
    };
  }, [size, pts, data.events, now]);

  const at = cursor ?? now;
  const p = pts[at];
  const last = pts[now];
  const st = data.state;

  const summary =
    `${data.symbol} noise-area chart, demo data. Open ${fmt(data.open, decimals)}. ` +
    `At ${minuteToClock(now)} New York the price is ${fmt(last.price ?? 0, decimals)}, ` +
    `upper band ${fmt(last.upper, decimals)}, lower band ${fmt(last.lower, decimals)}, ` +
    `VWAP ${fmt(last.vwap ?? 0, decimals)}. ` +
    (st.position === "FLAT"
      ? "No position: the price was inside the noise area at every half-hour check."
      : `${st.position} since ${minuteToClock(st.since_minute ?? 0)}, stop ${fmt(st.stop ?? 0, decimals)}.`);

  // Right-axis tags, pushed apart so they never overlap.
  const tags = useMemo(() => {
    if (!geo) return [];
    const stopOnBand = st.stop != null && st.stop_basis === "BAND";
    const raw: { key: string; v: number; text: string; fill: string; ink: string; stroke?: string }[] = [
      { key: "px", v: last.price ?? data.open, text: fmt(last.price ?? data.open, decimals), fill: GOLD, ink: "#000" },
      {
        key: "up",
        v: last.upper,
        text: fmt(last.upper, decimals),
        fill: "#000",
        ink: GOLD,
        stroke: stopOnBand ? GOLD : GOLD_DIM,
      },
      { key: "lo", v: last.lower, text: fmt(last.lower, decimals), fill: "#000", ink: GOLD, stroke: GOLD_DIM },
      { key: "vw", v: last.vwap ?? data.open, text: fmt(last.vwap ?? data.open, decimals), fill: "#000", ink: ORANGE, stroke: ORANGE },
    ];
    const placed = raw.map((t) => ({ ...t, y: geo.y(t.v) })).sort((a, b) => a.y - b.y);
    for (let i = 1; i < placed.length; i++) {
      if (placed[i].y - placed[i - 1].y < 15) placed[i].y = placed[i - 1].y + 15;
    }
    return placed;
  }, [geo, last, st, data.open, decimals]);

  const xTicks = geo?.narrow ? [0, 90, 210, 330, 390] : [0, 30, 90, 150, 210, 270, 330, 390];

  const move = (clientX: number, rect: DOMRect) => {
    if (!geo) return;
    const m = Math.round(((clientX - rect.left - geo.padL) / geo.pw) * 390);
    setCursor(Math.max(0, Math.min(now, m)));
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      {/* Readout: follows the cursor, rests on the latest minute */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-b border-border bg-surface-0 px-3 py-1.5">
        <span className="m-num text-[11px] font-bold text-foreground">
          {minuteToClock(at)}
          <span className="ml-1 font-normal text-muted-foreground">NY</span>
        </span>
        <Key swatch={<i className="block h-[2px] w-3" style={{ background: INK }} />} label="Price" value={fmt(p.price ?? 0, decimals)} />
        <Key
          swatch={<i className="block h-2 w-3 border" style={{ borderColor: GOLD_DIM, background: "rgba(230,165,50,0.14)" }} />}
          label="Noise area"
          value={`${fmt(p.lower, decimals)} - ${fmt(p.upper, decimals)}`}
        />
        <Key
          swatch={<i className="block h-0 w-3 border-t border-dashed" style={{ borderColor: ORANGE }} />}
          label="VWAP"
          value={fmt(p.vwap ?? 0, decimals)}
        />
      </div>

      <div
        ref={ref}
        role="group"
        tabIndex={0}
        aria-label={`${summary} Use the left and right arrow keys to read other minutes.`}
        className="m-gridbg relative min-h-0 flex-1 cursor-crosshair touch-pan-y select-none"
        onPointerMove={(e) => move(e.clientX, e.currentTarget.getBoundingClientRect())}
        onPointerDown={(e) => move(e.clientX, e.currentTarget.getBoundingClientRect())}
        onPointerLeave={() => setCursor(null)}
        onBlur={() => setCursor(null)}
        onKeyDown={(e) => {
          const stepBy = e.shiftKey ? 10 : 1;
          if (e.key === "ArrowLeft") setCursor(Math.max(0, at - stepBy));
          else if (e.key === "ArrowRight") setCursor(Math.min(now, at + stepBy));
          else if (e.key === "Home") setCursor(0);
          else if (e.key === "End") setCursor(now);
          else if (e.key === "Escape") setCursor(null);
          else return;
          e.preventDefault();
        }}
      >
        <div className="pointer-events-none absolute inset-0 bg-gradient-to-t from-primary/5 to-transparent opacity-40" />
        {geo && size && (
          <svg width={size.w} height={size.h} className="absolute inset-0 block" aria-hidden="true">
            {/* noise area */}
            <path d={geo.area} fill={GOLD} fillOpacity={0.07} />
            <path d={geo.upperPast} fill="none" stroke={GOLD_DIM} strokeWidth={1} />
            <path d={geo.lowerPast} fill="none" stroke={GOLD_DIM} strokeWidth={1} />
            <path d={geo.upperNext} fill="none" stroke={GOLD_DIM} strokeWidth={1} strokeDasharray="3 4" />
            <path d={geo.lowerNext} fill="none" stroke={GOLD_DIM} strokeWidth={1} strokeDasharray="3 4" />

            {/* open */}
            <line x1={geo.padL} x2={geo.padL + geo.pw} y1={geo.y(data.open)} y2={geo.y(data.open)} stroke="#3a3a3a" strokeDasharray="1 5" />
            <text x={geo.padL + geo.pw - 6} y={geo.y(data.open) - 5} textAnchor="end" fill={MUTED} fontSize={10} className="m-num" letterSpacing="0.08em">
              OPEN {fmt(data.open, decimals)}
            </text>

            {/* half-hour checks */}
            {Array.from({ length: 12 }, (_, i) => (i + 1) * 30).map((m) => (
              <line
                key={m}
                x1={geo.x(m)}
                x2={geo.x(m)}
                y1={geo.padT + geo.ph}
                y2={geo.padT + geo.ph + (m <= now ? 5 : 3)}
                stroke={m <= now ? GOLD : "#555"}
              />
            ))}

            {/* vwap + price */}
            <path d={geo.vwap} fill="none" stroke={ORANGE} strokeWidth={1} strokeDasharray="4 3" />
            <path d={geo.price} fill="none" stroke={INK} strokeWidth={1.25} strokeLinejoin="round" />
            {geo.heldPaths.map((d, i) => (
              <path key={i} d={d} fill="none" stroke={GOLD} strokeWidth={1.75} strokeLinejoin="round" className="m-glow" />
            ))}

            {/* entries and exits */}
            {data.events.map((e) => {
              const ex = geo.x(e.minute);
              const ey = geo.y(e.price);
              const isEntry = e.kind === "ENTRY_LONG" || e.kind === "ENTRY_SHORT";
              const up = e.kind === "ENTRY_LONG";
              const label = isEntry ? `${up ? "LONG" : "SHORT"} ${minuteToClock(e.minute)}` : `OUT ${minuteToClock(e.minute)}`;
              return (
                <g key={`${e.kind}-${e.minute}`}>
                  <line x1={ex} x2={ex} y1={geo.padT} y2={geo.padT + geo.ph} stroke={GOLD} strokeOpacity={0.25} />
                  {isEntry ? (
                    <path
                      d={up ? `M${ex} ${ey + 5}l-5 9h10z` : `M${ex} ${ey - 5}l-5 -9h10z`}
                      fill={GOLD}
                    />
                  ) : (
                    <rect x={ex - 4} y={ey - 4} width={8} height={8} fill="#000" stroke={GOLD} />
                  )}
                  <text
                    x={ex + 8}
                    y={up ? ey + 16 : ey - 8}
                    fill={GOLD}
                    fontSize={10}
                    fontWeight={700}
                    className="m-num"
                    letterSpacing="0.08em"
                  >
                    {label}
                  </text>
                </g>
              );
            })}

            {/* now */}
            <line x1={geo.x(now)} x2={geo.x(now)} y1={geo.padT - 4} y2={geo.padT + geo.ph} stroke={GOLD} strokeOpacity={0.5} strokeDasharray="2 3" />
            <text x={geo.x(now) + 5} y={geo.padT + 5} fill={GOLD} fontSize={10} fontWeight={700} className="m-num" letterSpacing="0.08em">
              NOW
            </text>
            <circle cx={geo.x(now)} cy={geo.y(last.price ?? data.open)} r={3} fill={GOLD} />

            {/* cursor */}
            {cursor != null && (
              <g>
                <line x1={geo.x(cursor)} x2={geo.x(cursor)} y1={geo.padT} y2={geo.padT + geo.ph} stroke={INK} strokeOpacity={0.5} />
                {p.price != null && <circle cx={geo.x(cursor)} cy={geo.y(p.price)} r={3} fill="#000" stroke={INK} />}
              </g>
            )}

            {/* x axis */}
            <line x1={geo.padL} x2={geo.padL + geo.pw} y1={geo.padT + geo.ph} y2={geo.padT + geo.ph} stroke="#252525" />
            {xTicks.map((m) => (
              <text
                key={m}
                x={geo.x(m)}
                y={size.h - 6}
                fill={MUTED}
                fontSize={10}
                className="m-num"
                textAnchor={m === 0 ? "start" : m === 390 ? "end" : "middle"}
              >
                {minuteToClock(m)}
              </text>
            ))}

            {/* right-axis tags */}
            <line x1={geo.padL + geo.pw} x2={geo.padL + geo.pw} y1={geo.padT} y2={geo.padT + geo.ph} stroke="#252525" />
            {tags.map((t) => (
              <g key={t.key}>
                <rect x={geo.padL + geo.pw + 3} y={t.y - 7} width={geo.padR - 6} height={14} fill={t.fill} stroke={t.stroke ?? "none"} />
                <text
                  x={geo.padL + geo.pw + geo.padR / 2}
                  y={t.y + 3.5}
                  fill={t.ink}
                  fontSize={10}
                  fontWeight={700}
                  textAnchor="middle"
                  className="m-num"
                >
                  {t.text}
                </text>
              </g>
            ))}
          </svg>
        )}
      </div>
    </div>
  );
}

function Key({ swatch, label, value }: { swatch: React.ReactNode; label: string; value: string }) {
  return (
    <span className="flex items-center gap-1.5">
      <span className="flex w-3 items-center justify-center" aria-hidden="true">
        {swatch}
      </span>
      <span className="m-label">{label}</span>
      <span className="m-num text-[11px] font-bold text-foreground">{value}</span>
    </span>
  );
}
