"use client";

import { useEffect, useRef, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Candle {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

interface HeatmapData {
  grid: Float32Array;
  rows: number;
  cols: number;
  max: number;
  rowProfile: Float32Array;
  rowMax: number;
  hi: number;
  lo: number;
  step: number;
}

const HEAT_STOPS = [
  { t: 0.00, r: 0,   g: 2,   b: 12,  a: 0.03 },
  { t: 0.06, r: 2,   g: 8,   b: 35,  a: 0.15 },
  { t: 0.14, r: 6,   g: 18,  b: 65,  a: 0.30 },
  { t: 0.24, r: 10,  g: 40,  b: 110, a: 0.45 },
  { t: 0.34, r: 8,   g: 75,  b: 160, a: 0.55 },
  { t: 0.44, r: 0,   g: 130, b: 190, a: 0.62 },
  { t: 0.54, r: 0,   g: 180, b: 200, a: 0.68 },
  { t: 0.64, r: 60,  g: 200, b: 160, a: 0.72 },
  { t: 0.74, r: 200, g: 210, b: 40,  a: 0.78 },
  { t: 0.84, r: 255, g: 160, b: 0,   a: 0.85 },
  { t: 0.93, r: 255, g: 70,  b: 15,  a: 0.90 },
  { t: 1.00, r: 255, g: 30,  b: 10,  a: 0.95 },
];

const BULL_RGB: [number, number, number] = [16, 185, 129];
const BEAR_RGB: [number, number, number] = [239, 68, 68];

const INTERVAL_TO_PERIOD: Record<string, string> = {
  "1m": "1d", "5m": "5d", "15m": "5d", "30m": "1mo",
  "1h": "3mo", "4h": "6mo", "1d": "1y", "1wk": "2y",
};

const MIN_VISIBLE = 15;
const DEFAULT_VISIBLE = 80;

function hash(x: number, y: number): number {
  const s = Math.sin(x * 127.1 + y * 311.7) * 43758.5453123;
  return s - Math.floor(s);
}

function valueNoise(x: number, y: number): number {
  const xi = Math.floor(x), yi = Math.floor(y);
  const xf = x - xi, yf = y - yi;
  const u = xf * xf * (3 - 2 * xf);
  const v = yf * yf * (3 - 2 * yf);
  const a = hash(xi, yi);
  const b = hash(xi + 1, yi);
  const c = hash(xi, yi + 1);
  const d = hash(xi + 1, yi + 1);
  return a * (1 - u) * (1 - v) + b * u * (1 - v) + c * (1 - u) * v + d * u * v;
}

function heatColor(t: number, alphaMul = 1): string {
  t = t < 0 ? 0 : t > 1 ? 1 : t;
  let lo = HEAT_STOPS[0], hi = HEAT_STOPS[HEAT_STOPS.length - 1];
  for (let i = 0; i < HEAT_STOPS.length - 1; i++) {
    if (t >= HEAT_STOPS[i].t && t <= HEAT_STOPS[i + 1].t) {
      lo = HEAT_STOPS[i];
      hi = HEAT_STOPS[i + 1];
      break;
    }
  }
  const span = (hi.t - lo.t) || 1;
  const local = (t - lo.t) / span;
  const r = Math.round(lo.r + (hi.r - lo.r) * local);
  const g = Math.round(lo.g + (hi.g - lo.g) * local);
  const b = Math.round(lo.b + (hi.b - lo.b) * local);
  const a = Math.min(1, Math.max(0, (lo.a + (hi.a - lo.a) * local) * alphaMul));
  return `rgba(${r},${g},${b},${a.toFixed(3)})`;
}

function heatColorRGBA(t: number, alphaMul = 1): [number, number, number, number] {
  t = t < 0 ? 0 : t > 1 ? 1 : t;
  let lo = HEAT_STOPS[0], hi = HEAT_STOPS[HEAT_STOPS.length - 1];
  for (let i = 0; i < HEAT_STOPS.length - 1; i++) {
    if (t >= HEAT_STOPS[i].t && t <= HEAT_STOPS[i + 1].t) {
      lo = HEAT_STOPS[i];
      hi = HEAT_STOPS[i + 1];
      break;
    }
  }
  const span = (hi.t - lo.t) || 1;
  const local = (t - lo.t) / span;
  const r = Math.round(lo.r + (hi.r - lo.r) * local);
  const g = Math.round(lo.g + (hi.g - lo.g) * local);
  const b = Math.round(lo.b + (hi.b - lo.b) * local);
  const a = Math.min(255, Math.max(0, Math.round((lo.a + (hi.a - lo.a) * local) * alphaMul * 255)));
  return [r, g, b, a];
}

function niceStep(range: number, targetLines: number): number {
  const rough = range / targetLines;
  const pow = Math.pow(10, Math.floor(Math.log10(rough)));
  const norm = rough / pow;
  let nice;
  if (norm < 1.5) nice = 1;
  else if (norm < 3) nice = 2;
  else if (norm < 7) nice = 5;
  else nice = 10;
  return nice * pow;
}

function getDecimals(price: number, ticker: string): number {
  const t = ticker.toUpperCase().replace(/[/\-=X]/g, "");
  const jpyPairs = ["USDJPY", "EURJPY", "GBPJPY", "CADJPY", "CHFJPY", "AUDJPY", "NZDJPY"];
  if (jpyPairs.includes(t)) return 3;
  if (t.length === 6 && !t.startsWith("XA") && !t.startsWith("US5") && !t.startsWith("US3")) return 5;
  if (price > 1000) return 1;
  if (price > 100) return 2;
  if (price > 1) return 2;
  if (price > 0.01) return 4;
  return 6;
}

function lerp(current: number, target: number, speed: number): number {
  if (current === 0) return target;
  const diff = target - current;
  if (Math.abs(diff) < Math.abs(target) * 0.00001) return target;
  return current + diff * speed;
}

function drawSphere(
  ctx: CanvasRenderingContext2D, x: number, y: number, r: number,
  rgb: [number, number, number], opacity: number,
) {
  const [cr, cg, cb] = rgb;
  const glow = ctx.createRadialGradient(x, y, 0, x, y, r * 2.3);
  glow.addColorStop(0, `rgba(${cr},${cg},${cb},${(0.22 * opacity).toFixed(3)})`);
  glow.addColorStop(1, `rgba(${cr},${cg},${cb},0)`);
  ctx.fillStyle = glow;
  ctx.beginPath(); ctx.arc(x, y, r * 2.3, 0, Math.PI * 2); ctx.fill();

  const body = ctx.createRadialGradient(x - r * 0.35, y - r * 0.35, r * 0.05, x, y, r * 1.05);
  body.addColorStop(0, `rgba(${Math.min(cr + 90, 255)},${Math.min(cg + 90, 255)},${Math.min(cb + 90, 255)},${opacity})`);
  body.addColorStop(0.45, `rgba(${cr},${cg},${cb},${opacity})`);
  body.addColorStop(1, `rgba(${Math.round(cr * 0.35)},${Math.round(cg * 0.35)},${Math.round(cb * 0.35)},${opacity})`);
  ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2);
  ctx.fillStyle = body; ctx.fill();

  ctx.save();
  ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.clip();
  ctx.beginPath(); ctx.arc(x + r * 0.42, y + r * 0.42, r * 0.9, 0, Math.PI * 2);
  ctx.fillStyle = `rgba(0,0,0,${(0.28 * opacity).toFixed(3)})`;
  ctx.fill();
  ctx.restore();

  ctx.beginPath();
  ctx.ellipse(x - r * 0.32, y - r * 0.35, r * 0.32, r * 0.2, -0.6, 0, Math.PI * 2);
  ctx.fillStyle = `rgba(255,255,255,${(0.55 * opacity).toFixed(3)})`;
  ctx.fill();
}

function drawEmaLine(
  ctx: CanvasRenderingContext2D, candles: Candle[], period: number,
  color: string, idxToX: (i: number) => number, priceToY: (p: number) => number,
) {
  const closes = candles.map(c => c.close);
  const ema: number[] = [];
  const k = 2 / (period + 1);
  ema[0] = closes[0];
  for (let i = 1; i < closes.length; i++) ema[i] = closes[i] * k + ema[i - 1] * (1 - k);
  ctx.beginPath();
  let started = false;
  for (let i = period; i < candles.length; i++) {
    const x = idxToX(i);
    const y = priceToY(ema[i]);
    if (!started) { ctx.moveTo(x, y); started = true; }
    else ctx.lineTo(x, y);
  }
  ctx.strokeStyle = color;
  ctx.lineWidth = 1.2;
  ctx.stroke();
}

function buildHeatmap(candles: Candle[]): HeatmapData | null {
  if (!candles || candles.length < 2) return null;

  let hi = -Infinity, lo = Infinity, maxVol = 0;
  candles.forEach(c => {
    if (c.high > hi) hi = c.high;
    if (c.low < lo) lo = c.low;
    if (c.volume > maxVol) maxVol = c.volume;
  });
  if (maxVol <= 0) maxVol = 1;
  const range = (hi - lo) || (hi * 0.01) || 1;
  const pad = range * 0.12;
  hi += pad; lo -= pad;

  const rows = 120;
  const cols = candles.length;
  const step = (hi - lo) / rows;

  const synth = new Map<number, number>();
  candles.forEach(c => {
    const mid = (c.high + c.low) / 2;
    const key = Math.round(mid / step);
    synth.set(key, (synth.get(key) || 0) + (c.volume || 1));
  });
  const profile = Array.from(synth.entries()).map(([k, v]) => ({ price: k * step, volume: v }));

  let maxProfileVol = 0;
  profile.forEach(p => { if (p.volume > maxProfileVol) maxProfileVol = p.volume; });
  if (maxProfileVol <= 0) maxProfileVol = 1;

  const sigma = step * 9;
  const ambientFloor = maxProfileVol * 0.04;
  const rowProfile = new Float32Array(rows);
  for (let row = 0; row < rows; row++) {
    const price = lo + (row + 0.5) * step;
    let h = ambientFloor;
    for (let p = 0; p < profile.length; p++) {
      const lv = profile[p];
      const d = price - lv.price;
      h += lv.volume * Math.exp(-(d * d) / (2 * sigma * sigma));
    }
    rowProfile[row] = h;
  }
  let rowMax = 0;
  for (let row = 0; row < rows; row++) if (rowProfile[row] > rowMax) rowMax = rowProfile[row];
  if (rowMax <= 0) rowMax = 1;

  const beamSigma = Math.max(range * 0.025, step * 5);
  const grid = new Float32Array(rows * cols);
  let cellMax = 0;
  for (let col = 0; col < cols; col++) {
    const c = candles[col];
    const bodyHi = Math.max(c.open, c.close);
    const bodyLo = Math.min(c.open, c.close);
    const mid = (c.high + c.low) / 2;
    const colVolNorm = maxVol ? c.volume / maxVol : 0.5;
    const colFlicker = 0.88 + hash(col * 3.13, 7.77) * 0.28;
    const beamStrength = 0.3 + colVolNorm * 0.7;

    for (let row = 0; row < rows; row++) {
      const price = lo + (row + 0.5) * step;
      let factor = 0.45;
      if (price >= c.low && price <= c.high) {
        factor = (price >= bodyLo && price <= bodyHi) ? 1.95 : 1.35;
      }
      const bd = price - mid;
      factor += beamStrength * Math.exp(-(bd * bd) / (2 * beamSigma * beamSigma));
      const n = valueNoise(col * 0.35, row * 0.22) * 0.6
        + valueNoise(col * 0.9 + 41.3, row * 0.5 + 17.1) * 0.4;
      factor *= (0.72 + n * 0.56) * colFlicker;
      const v = rowProfile[row] * factor;
      grid[row * cols + col] = v;
      if (v > cellMax) cellMax = v;
    }
  }

  return { grid, rows, cols, max: cellMax || 1, rowProfile, rowMax, hi, lo, step };
}

interface SRLevels {
  support: number[];
  resistance: number[];
  pivot: number;
}

function computeSRLevels(candles: Candle[]): SRLevels | null {
  if (candles.length < 10) return null;
  const recent = candles.slice(-Math.min(candles.length, 100));
  let hi = -Infinity, lo = Infinity;
  const lastClose = recent[recent.length - 1].close;
  recent.forEach(c => { if (c.high > hi) hi = c.high; if (c.low < lo) lo = c.low; });
  const pivot = (hi + lo + lastClose) / 3;
  const r1 = 2 * pivot - lo;
  const s1 = 2 * pivot - hi;
  const r2 = pivot + (hi - lo);
  const s2 = pivot - (hi - lo);
  const r3 = hi + 2 * (pivot - lo);
  const s3 = lo - 2 * (hi - pivot);
  return {
    resistance: [r1, r2, r3].filter(r => r > lastClose),
    support: [s1, s2, s3].filter(s => s < lastClose),
    pivot,
  };
}

const TIMEFRAMES = ["1m", "5m", "15m", "30m", "1h", "4h", "1d"] as const;

const REFRESH_MS: Record<string, number> = {
  "1m": 10_000, "5m": 15_000, "15m": 30_000, "30m": 30_000,
  "1h": 60_000, "4h": 120_000, "1d": 300_000, "1wk": 600_000,
};

interface OrderFlowChartProps {
  ticker: string;
  interval?: string;
  fillContainer?: boolean;
}

export function OrderFlowChart({ ticker, interval: externalInterval = "1d", fillContainer }: OrderFlowChartProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [loading, setLoading] = useState(true);
  const [feedUnavailable, setFeedUnavailable] = useState<string | null>(null);
  const [localInterval, setLocalInterval] = useState(externalInterval);
  useEffect(() => { setLocalInterval(externalInterval); }, [externalInterval]);
  const interval = localInterval;

  const state = useRef({
    candles: [] as Candle[],
    viewStart: 0,
    viewEnd: 0,
    rightPadding: 0,
    priceOffset: 0,
    lastVisibleRange: 0,
    levels: null as SRLevels | null,
    mouseX: -1,
    mouseY: -1,
    isDragging: false,
    dragStartX: 0,
    dragStartY: 0,
    dragViewStart: 0,
    dragViewEnd: 0,
    dragStartPriceOffset: 0,
    dragStartPad: 0,
    animTime: 0,
    heatmap: null as HeatmapData | null,
    lastHeatKey: "",
    ticker: "",
    interval: "",
    // Smooth animation state
    displayPrice: 0,
    displayHigh: 0,
    displayLow: 0,
    displayCandles: [] as Candle[],
    lerpSpeed: 0.12,
    lastHeatHi: 0,
    lastHeatLo: 0,
    heatCanvas: null as HTMLCanvasElement | null,
    momentumVx: 0,
    momentumVy: 0,
    dragHistory: [] as Array<{ x: number; y: number; t: number }>,
  });

  useEffect(() => {
    let cancelled = false;
    let refreshTimer: ReturnType<typeof setInterval> | null = null;
    let fetching = false;

    async function fetchData(isRefresh = false) {
      if (fetching) return;
      fetching = true;
      if (!isRefresh) setLoading(true);
      const period = INTERVAL_TO_PERIOD[interval] || "6mo";
      try {
        const res = await fetch(
          `${API}/api/v1/market/ohlcv/${encodeURIComponent(ticker)}?period=${period}&interval=${interval}`,
        );
        if (res.ok && !cancelled) {
          const data = await res.json();
          if (data.error === "no_data" || !data.candles || data.candles.length === 0) {
            setFeedUnavailable(data.detail || `No market data available for ${ticker}.`);
            state.current.candles = [];
            setLoading(false);
            return;
          }
          setFeedUnavailable(null);
          const candles: Candle[] = (data.candles ?? []).map((c: Record<string, number>) => ({
            time: c.time, open: c.open, high: c.high, low: c.low, close: c.close,
            volume: c.volume ?? 0,
          }));
          const s = state.current;
          s.levels = computeSRLevels(candles);

          // Detect symbol change via price range jump
          const prevHi = s.lastHeatHi;
          const prevLo = s.lastHeatLo;
          let newHi = -Infinity, newLo = Infinity;
          candles.forEach(c => { if (c.high > newHi) newHi = c.high; if (c.low < newLo) newLo = c.low; });
          const oldRange = (prevHi - prevLo) || 1;
          const symbolChanged = prevHi > 0 && (Math.abs(newHi - prevHi) > oldRange * 2);

          if (symbolChanged) {
            s.displayPrice = 0;
            s.displayHigh = 0;
            s.displayLow = 0;
            s.displayCandles = [];
            s.heatmap = null;
            s.priceOffset = 0;
          }
          s.lastHeatHi = newHi;
          s.lastHeatLo = newLo;

          if (isRefresh && s.candles.length > 0 && !symbolChanged) {
            const prevLen = s.candles.length;
            s.candles = candles;
            s.lastHeatKey = "";
            if (candles.length > prevLen) {
              s.viewStart += candles.length - prevLen;
            }
            const visCount = s.viewEnd - s.viewStart + s.rightPadding;
            const dataSlots = visCount - s.rightPadding;
            if (s.viewStart + dataSlots > candles.length) {
              s.viewStart = Math.max(0, candles.length - dataSlots);
            }
          } else {
            s.candles = candles;
            s.ticker = ticker;
            s.interval = interval;
            const visCount = Math.min(DEFAULT_VISIBLE, candles.length);
            s.rightPadding = Math.floor(visCount * 0.35);
            s.viewEnd = candles.length;
            s.viewStart = Math.max(0, candles.length - (visCount - s.rightPadding));
            s.priceOffset = 0;
            s.lastHeatKey = "";
          }
          setLoading(false);
        } else if (!cancelled) {
          const errData = await res.json().catch(() => ({}));
          setFeedUnavailable(errData.detail || `Feed returned HTTP ${res.status}`);
          state.current.candles = [];
          setLoading(false);
        }
      } catch (err: unknown) {
        if (!cancelled) {
          const message = err instanceof Error ? err.message : "Connection error";
          setFeedUnavailable(message);
          setLoading(false);
        }
      } finally {
        fetching = false;
      }
    }

    fetchData();
    const refreshMs = REFRESH_MS[interval] || 60_000;
    refreshTimer = setInterval(() => fetchData(true), refreshMs);

    return () => {
      cancelled = true;
      if (refreshTimer) clearInterval(refreshTimer);
    };
  }, [ticker, interval]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    let animId: number;
    const s = state.current;

    function render() {
      if (!canvas) return;
      const ctx = canvas.getContext("2d");
      if (!ctx) return;

      const dpr = window.devicePixelRatio || 1;
      const rect = canvas.getBoundingClientRect();
      const W = rect.width;
      const H = rect.height;

      if (canvas.width !== Math.round(W * dpr) || canvas.height !== Math.round(H * dpr)) {
        canvas.width = Math.round(W * dpr);
        canvas.height = Math.round(H * dpr);
      }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

      s.animTime += 0.016;

      // Apply momentum (inertia scrolling)
      if (!s.isDragging && (Math.abs(s.momentumVx) > 2 || Math.abs(s.momentumVy) > 2)) {
        const mChartW = W - 64;
        const mTotalSlots = (s.viewEnd - s.viewStart) + (s.rightPadding || 0);
        const mCandlePx = mTotalSlots > 0 ? mChartW / mTotalSlots : 1;
        const friction = 0.93;
        const dt = 0.016;
        const allLen = s.candles.length;

        const candleShift = Math.round(-s.momentumVx * dt / mCandlePx);
        if (candleShift !== 0) {
          let newStart = s.viewStart + candleShift;
          let newPad = s.rightPadding - candleShift;
          const maxPad = Math.floor(mTotalSlots * 0.6);
          if (newPad < 0) { newStart -= newPad; newPad = 0; }
          if (newPad > maxPad) { newStart -= (newPad - maxPad); newPad = maxPad; }
          if (newStart < 0) { newPad += newStart; newStart = 0; }
          const dataSlots = mTotalSlots - newPad;
          if (newStart + dataSlots > allLen) {
            newStart = Math.max(0, allLen - dataSlots);
          }
          s.viewStart = newStart;
          s.viewEnd = newStart + dataSlots;
          s.rightPadding = Math.max(0, newPad);
        }

        const mPriceH = (H - 38) * 0.82;
        if (s.lastVisibleRange > 0 && mPriceH > 0) {
          s.priceOffset += (s.momentumVy * dt / mPriceH) * s.lastVisibleRange;
        }

        s.momentumVx *= friction;
        s.momentumVy *= friction;
        if (Math.abs(s.momentumVx) < 2) s.momentumVx = 0;
        if (Math.abs(s.momentumVy) < 2) s.momentumVy = 0;
      }

      // Background
      const bg = ctx.createLinearGradient(0, 0, 0, H);
      bg.addColorStop(0, "#060b16");
      bg.addColorStop(0.55, "#03060d");
      bg.addColorStop(1, "#010203");
      ctx.fillStyle = bg;
      ctx.fillRect(0, 0, W, H);

      // Smooth animation: lerp price and last 3 candles
      const sp = s.lerpSpeed;
      if (s.candles.length > 0) {
        const lastClose = s.candles[s.candles.length - 1].close;
        s.displayPrice = s.displayPrice === 0 ? lastClose : lerp(s.displayPrice, lastClose, sp);

        while (s.displayCandles.length < s.candles.length) {
          const src = s.candles[s.displayCandles.length];
          s.displayCandles.push({ ...src });
        }
        if (s.displayCandles.length > s.candles.length) {
          s.displayCandles = s.displayCandles.slice(0, s.candles.length);
        }
        const lerpCount = Math.min(3, s.candles.length);
        for (let i = s.candles.length - lerpCount; i < s.candles.length; i++) {
          const dc = s.displayCandles[i];
          const tc = s.candles[i];
          dc.open = lerp(dc.open, tc.open, sp);
          dc.high = lerp(dc.high, tc.high, sp * 1.5);
          dc.low = lerp(dc.low, tc.low, sp * 1.5);
          dc.close = lerp(dc.close, tc.close, sp);
          dc.volume = lerp(dc.volume, tc.volume, sp * 0.5);
          dc.time = tc.time;
        }
        for (let i = 0; i < s.candles.length - lerpCount; i++) {
          const dc = s.displayCandles[i];
          const tc = s.candles[i];
          dc.open = tc.open; dc.high = tc.high; dc.low = tc.low;
          dc.close = tc.close; dc.volume = tc.volume; dc.time = tc.time;
        }
      }

      const allCandles = s.displayCandles.length === s.candles.length
        ? s.displayCandles : s.candles;
      if (!allCandles || allCandles.length < 2) {
        ctx.fillStyle = "rgba(201,168,76,0.4)";
        ctx.font = "11px JetBrains Mono, monospace";
        ctx.textAlign = "center";
        ctx.fillText("WAITING FOR MARKET DATA...", W / 2, H / 2);
        return;
      }

      const rPad = Math.min(s.rightPadding || 0, Math.floor((s.viewEnd - s.viewStart + (s.rightPadding || 0)) * 0.6));
      const totalSlots = (s.viewEnd - s.viewStart) + rPad;
      const vs = Math.max(0, Math.floor(s.viewStart));
      const ve = Math.min(allCandles.length, vs + (totalSlots - rPad));
      const visibleCandles = allCandles.slice(vs, ve);
      if (visibleCandles.length < 2) return;

      // Rebuild heatmap if view changed
      const heatKey = `${vs}-${ve}`;
      if (heatKey !== s.lastHeatKey) {
        s.heatmap = buildHeatmap(visibleCandles);
        s.lastHeatKey = heatKey;
      }

      const padd = { top: 8, right: 60, bottom: 30, left: 4 };
      const chartW = W - padd.left - padd.right;
      const priceH = (H - padd.top - padd.bottom) * 0.82;
      const volH = (H - padd.top - padd.bottom) * 0.15;
      const gapH = (H - padd.top - padd.bottom) * 0.03;
      const chartX = padd.left;
      const priceY = padd.top;
      const volY = padd.top + priceH + gapH;

      const n = visibleCandles.length;
      const candleW = chartW / totalSlots;

      let priceHigh = -Infinity, priceLow = Infinity, maxVol = 0;
      visibleCandles.forEach(c => {
        if (c.high > priceHigh) priceHigh = c.high;
        if (c.low < priceLow) priceLow = c.low;
        if (c.volume > maxVol) maxVol = c.volume;
      });

      const levels = s.levels;
      if (levels) {
        levels.resistance.forEach(r => { if (r > priceHigh) priceHigh = r; });
        levels.support.forEach(sv => { if (sv < priceLow) priceLow = sv; });
      }

      const priceRange = priceHigh - priceLow || 1;
      const pricePad = priceRange * 0.08;
      priceHigh += pricePad;
      priceLow -= pricePad;

      const vOff = s.priceOffset || 0;
      priceHigh += vOff;
      priceLow += vOff;

      // Smooth viewport bounds — snap on large jumps, lerp on small adjustments
      const targetRange = priceHigh - priceLow;
      const displayRange = s.displayHigh - s.displayLow;
      const rangeJump = displayRange > 0 ? Math.abs(targetRange - displayRange) / displayRange : 999;
      const centerJump = displayRange > 0 ? Math.abs((priceHigh + priceLow) - (s.displayHigh + s.displayLow)) / displayRange : 999;

      if (s.displayHigh === 0 || rangeJump > 0.5 || centerJump > 0.5) {
        s.displayHigh = priceHigh;
        s.displayLow = priceLow;
      } else {
        s.displayHigh = lerp(s.displayHigh, priceHigh, sp);
        s.displayLow = lerp(s.displayLow, priceLow, sp);
      }
      priceHigh = s.displayHigh;
      priceLow = s.displayLow;

      const totalRange = priceHigh - priceLow;
      s.lastVisibleRange = totalRange;

      const priceToY = (p: number) => priceY + (1 - (p - priceLow) / totalRange) * priceH;
      const idxToX = (i: number) => chartX + i * candleW + candleW / 2;

      // Patch last candle with lerped display price
      if (s.displayPrice > 0 && visibleCandles.length > 0) {
        const last = visibleCandles[visibleCandles.length - 1];
        last.close = s.displayPrice;
        if (s.displayPrice > last.high) last.high = s.displayPrice;
        if (s.displayPrice < last.low) last.low = s.displayPrice;
      }

      const currentPrice = s.displayPrice || visibleCandles[visibleCandles.length - 1].close;
      const dec = getDecimals(currentPrice, s.ticker);

      // === LAYER 1: Blue liquidity heatmap (ImageData rendering) ===
      const hm = s.heatmap;
      if (hm && hm.max > 0 && n >= 2) {
        const hRows = hm.rows;
        const hCols = hm.cols;

        if (!s.heatCanvas) {
          s.heatCanvas = document.createElement("canvas");
        }
        const oc = s.heatCanvas;
        if (oc.width !== hCols || oc.height !== hRows) {
          oc.width = hCols;
          oc.height = hRows;
        }
        const octx = oc.getContext("2d", { willReadFrequently: true })!;
        const imgData = octx.createImageData(hCols, hRows);
        const pixels = imgData.data;

        for (let row = 0; row < hRows; row++) {
          const imgRow = hRows - 1 - row;
          for (let col = 0; col < hCols; col++) {
            const v = hm.grid[row * hCols + col];
            const norm = v / hm.max;
            if (norm < 0.003) continue;
            const [r, g, b, a] = heatColorRGBA(norm, 1.4);
            const idx = (imgRow * hCols + col) * 4;
            pixels[idx] = r;
            pixels[idx + 1] = g;
            pixels[idx + 2] = b;
            pixels[idx + 3] = a;
          }
        }
        octx.putImageData(imgData, 0, 0);

        ctx.save();
        ctx.beginPath();
        ctx.rect(chartX, priceY, chartW, priceH);
        ctx.clip();
        ctx.imageSmoothingEnabled = true;
        ctx.imageSmoothingQuality = "high";

        const hmTopY = priceToY(hm.hi);
        const hmBotY = priceToY(hm.lo);
        const hmScreenH = hmBotY - hmTopY;
        const dataW = n * candleW;
        ctx.drawImage(oc, 0, 0, hCols, hRows, chartX, hmTopY, dataW, hmScreenH);
        ctx.restore();

        // Glow overlay for high-intensity price levels
        const cellH = Math.max(priceH / hRows, 1);
        for (let row = 0; row < hRows; row++) {
          const rowIntensity = hm.rowProfile[row] / hm.rowMax;
          if (rowIntensity > 0.25) {
            const price = hm.lo + (row + 0.5) * hm.step;
            const y = priceToY(price);
            if (y < priceY - cellH || y > priceY + priceH + cellH) continue;
            const glowAlpha = (rowIntensity - 0.25) / 0.75;
            ctx.save();
            ctx.shadowColor = "rgba(0,160,220,0.6)";
            ctx.shadowBlur = 18;
            ctx.fillStyle = heatColor(0.65 + rowIntensity * 0.35, glowAlpha * 0.45);
            ctx.fillRect(chartX, y - cellH * 1.2, chartW, cellH * 2.4);
            ctx.restore();
          }
        }
      }

      // === LAYER 2: S/R levels ===
      if (levels) {
        levels.resistance.forEach((r, i) => {
          const y = priceToY(r);
          if (y < priceY - 5 || y > priceY + priceH + 5) return;
          const alpha = Math.max(0.5, 0.9 - i * 0.15);
          const isOrange = i % 2 === 1;
          const coreRGB = isOrange ? "255,140,26" : "255,70,56";
          const glowRGB = isOrange ? "255,160,60" : "255,90,70";
          ctx.save();
          ctx.shadowColor = `rgba(${glowRGB},0.9)`;
          ctx.shadowBlur = 16;
          ctx.fillStyle = `rgba(${coreRGB},${alpha})`;
          ctx.fillRect(chartX, y - 1.5, chartW, 3);
          ctx.shadowBlur = 0;
          ctx.fillStyle = `rgba(255,205,180,${Math.min(1, alpha + 0.15)})`;
          ctx.fillRect(chartX, y - 0.6, chartW, 1.2);
          ctx.restore();
          ctx.fillStyle = `rgba(${coreRGB},${alpha})`;
          ctx.font = "bold 8px JetBrains Mono, monospace";
          ctx.textAlign = "left";
          ctx.fillText(`R${i + 1}`, chartX + 4, y - 4);
        });
        levels.support.forEach((sv, i) => {
          const y = priceToY(sv);
          if (y < priceY - 5 || y > priceY + priceH + 5) return;
          const alpha = Math.max(0.5, 0.9 - i * 0.15);
          const isYellow = i % 2 === 1;
          const coreRGB = isYellow ? "250,210,20" : "245,160,11";
          const glowRGB = isYellow ? "255,225,80" : "250,180,60";
          ctx.save();
          ctx.shadowColor = `rgba(${glowRGB},0.9)`;
          ctx.shadowBlur = 16;
          ctx.fillStyle = `rgba(${coreRGB},${alpha})`;
          ctx.fillRect(chartX, y - 1.5, chartW, 3);
          ctx.shadowBlur = 0;
          ctx.fillStyle = `rgba(255,240,190,${Math.min(1, alpha + 0.15)})`;
          ctx.fillRect(chartX, y - 0.6, chartW, 1.2);
          ctx.restore();
          ctx.fillStyle = `rgba(${coreRGB},${alpha})`;
          ctx.font = "bold 8px JetBrains Mono, monospace";
          ctx.textAlign = "left";
          ctx.fillText(`S${i + 1}`, chartX + 4, y - 4);
        });
        if (levels.pivot) {
          const y = priceToY(levels.pivot);
          if (y >= priceY && y <= priceY + priceH) {
            ctx.save();
            ctx.strokeStyle = "rgba(201,168,76,0.4)";
            ctx.setLineDash([4, 3]);
            ctx.lineWidth = 1;
            ctx.beginPath(); ctx.moveTo(chartX, y); ctx.lineTo(chartX + chartW, y); ctx.stroke();
            ctx.setLineDash([]);
            ctx.restore();
          }
        }
      }

      // === LAYER 3: Price axis grid ===
      const gridStep = niceStep(totalRange, 6);
      const gridStart = Math.ceil(priceLow / gridStep) * gridStep;
      ctx.textAlign = "right";
      ctx.font = "9px JetBrains Mono, monospace";
      for (let p = gridStart; p <= priceHigh; p += gridStep) {
        const y = priceToY(p);
        ctx.fillStyle = "rgba(201,168,76,0.22)";
        ctx.fillText(p.toFixed(dec), W - 2, y + 3);
      }

      // === LAYER 3: EMA lines ===
      if (visibleCandles.length > 10) {
        drawEmaLine(ctx, visibleCandles, 9, "rgba(229,213,160,0.45)", idxToX, priceToY);
        drawEmaLine(ctx, visibleCandles, 21, "rgba(201,168,76,0.32)", idxToX, priceToY);
        if (visibleCandles.length > 50)
          drawEmaLine(ctx, visibleCandles, 50, "rgba(139,122,58,0.22)", idxToX, priceToY);
      }

      // === LAYER 4: Order flow beads ===
      const baseR = Math.max(Math.min(candleW * 0.55, 9), 2.5);

      // Compute avg candle range for "big move" detection
      let avgRange = 0;
      visibleCandles.forEach(c => { avgRange += c.high - c.low; });
      avgRange /= visibleCandles.length || 1;

      ctx.save();
      ctx.beginPath();
      visibleCandles.forEach((c, i) => {
        const x = idxToX(i);
        const y = priceToY(c.close);
        if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      });
      ctx.shadowColor = "rgba(180,222,255,0.35)";
      ctx.shadowBlur = 3;
      ctx.strokeStyle = "rgba(205,230,255,0.12)";
      ctx.lineWidth = 0.8;
      ctx.stroke();
      ctx.restore();

      visibleCandles.forEach((c, i) => {
        const x = idxToX(i);
        const isBull = c.close >= c.open;
        const dirRGB = isBull ? BULL_RGB : BEAR_RGB;
        const volNorm = maxVol ? c.volume / maxVol : 0.5;
        const candleRange = c.high - c.low;
        if (candleRange <= 0) return;

        // Scale factor: bigger bubbles for high volume + big range candles
        const moveRatio = avgRange > 0 ? candleRange / avgRange : 1;
        const intensity = Math.min(2.2, 0.6 + volNorm * 0.8 + Math.max(0, moveRatio - 1) * 0.6);

        const bodyHi = Math.max(c.open, c.close);
        const bodyLo = Math.min(c.open, c.close);
        const bodyPx = priceToY(bodyLo) - priceToY(bodyHi);
        const scaledR = baseR * intensity;

        if (c.high > bodyHi + candleRange * 0.04) {
          const wickSteps = Math.max(Math.round((priceToY(bodyHi) - priceToY(c.high)) / (scaledR * 2.2)), 1);
          for (let w = 0; w <= wickSteps; w++) {
            const t = wickSteps > 0 ? w / wickSteps : 0;
            const price = c.high + t * (bodyHi - c.high);
            const fade = 0.18 + t * 0.15;
            drawSphere(ctx, x, priceToY(price), scaledR * 0.4, BEAR_RGB, fade);
          }
        }

        if (c.low < bodyLo - candleRange * 0.04) {
          const wickSteps = Math.max(Math.round((priceToY(c.low) - priceToY(bodyLo)) / (scaledR * 2.2)), 1);
          for (let w = 0; w <= wickSteps; w++) {
            const t = wickSteps > 0 ? w / wickSteps : 0;
            const price = bodyLo - t * (bodyLo - c.low);
            const fade = 0.18 + (1 - t) * 0.15;
            drawSphere(ctx, x, priceToY(price), scaledR * 0.4, BULL_RGB, fade);
          }
        }

        const numBubbles = Math.max(Math.round(bodyPx / (scaledR * 1.6)), 2);
        const bodySize = 0.5 + volNorm * 0.6 + Math.max(0, moveRatio - 1) * 0.3;
        for (let b = 0; b < numBubbles; b++) {
          const t = numBubbles > 1 ? b / (numBubbles - 1) : 0.5;
          const price = bodyLo + t * (bodyHi - bodyLo);
          drawSphere(ctx, x, priceToY(price), scaledR * bodySize * 0.72, dirRGB, 0.65);
        }

        const closeY = priceToY(c.close);
        const closeR = scaledR * (0.9 + volNorm * 0.8);
        drawSphere(ctx, x, closeY, closeR, dirRGB, 1);
      });

      // === LAYER 5: Current price line + gold tag ===
      if (currentPrice) {
        const y = priceToY(currentPrice);
        const pulse = (Math.sin(s.animTime * 3) + 1) * 0.5;

        ctx.beginPath(); ctx.moveTo(chartX, y); ctx.lineTo(chartX + chartW, y);
        ctx.strokeStyle = `rgba(201,168,76,${0.3 + pulse * 0.15})`;
        ctx.lineWidth = 0.8; ctx.setLineDash([2, 2]); ctx.stroke(); ctx.setLineDash([]);

        const tagW = 56;
        ctx.fillStyle = `rgba(201,168,76,${0.85 + pulse * 0.15})`;
        ctx.fillRect(chartX + chartW + 2, y - 8, tagW, 16);
        ctx.fillStyle = "#0A0908";
        ctx.font = "bold 9px JetBrains Mono, monospace";
        ctx.textAlign = "center";
        ctx.fillText(currentPrice.toFixed(dec), chartX + chartW + 2 + tagW / 2, y + 3);
      }

      // === LAYER 6: Volume bars ===
      const bodyW = Math.max(candleW * 0.6, 2);
      visibleCandles.forEach((c, i) => {
        const x = idxToX(i);
        const vNorm = maxVol ? c.volume / maxVol : 0;
        const vH = vNorm * volH;
        const isBull = c.close >= c.open;
        ctx.fillStyle = isBull
          ? `rgba(16,185,129,${0.2 + vNorm * 0.35})`
          : `rgba(239,68,68,${0.2 + vNorm * 0.35})`;
        ctx.fillRect(x - bodyW / 2, volY + volH - vH, bodyW, vH);
      });

      ctx.beginPath();
      ctx.moveTo(chartX, volY - 2);
      ctx.lineTo(chartX + chartW, volY - 2);
      ctx.strokeStyle = "rgba(201,168,76,0.06)";
      ctx.lineWidth = 0.5;
      ctx.stroke();

      // === LAYER 7: Time labels ===
      ctx.fillStyle = "rgba(201,168,76,0.2)";
      ctx.font = "8px JetBrains Mono, monospace";
      ctx.textAlign = "center";
      const labelEvery = Math.max(Math.floor(n / 6), 1);
      visibleCandles.forEach((c, i) => {
        if (i % labelEvery === 0) {
          const d = new Date(c.time * 1000);
          const intv = s.interval;
          let label: string;
          if (intv === "1d" || intv === "1wk") {
            label = `${d.getMonth() + 1}/${d.getDate()}`;
          } else {
            const hh = String(d.getHours()).padStart(2, "0");
            const mm = String(d.getMinutes()).padStart(2, "0");
            label = `${hh}:${mm}`;
          }
          ctx.fillText(label, idxToX(i), H - 4);
        }
      });

      // Chart label
      ctx.fillStyle = "rgba(201,168,76,0.12)";
      ctx.font = "9px JetBrains Mono, monospace";
      ctx.textAlign = "left";
      ctx.fillText(`${s.interval.toUpperCase()} ORDER FLOW`, chartX + 4, priceY + 10);

      // === CROSSHAIR ===
      if (s.mouseX >= 0 && !s.isDragging) {
        const mx = s.mouseX;
        const my = s.mouseY;

        if (mx > chartX && mx < chartX + chartW && my > priceY && my < priceY + priceH) {
          ctx.save();
          ctx.setLineDash([4, 4]);
          ctx.strokeStyle = "rgba(201,168,76,0.4)";
          ctx.lineWidth = 0.5;

          ctx.beginPath();
          ctx.moveTo(mx, priceY);
          ctx.lineTo(mx, priceY + priceH);
          ctx.stroke();

          ctx.beginPath();
          ctx.moveTo(chartX, my);
          ctx.lineTo(chartX + chartW, my);
          ctx.stroke();
          ctx.setLineDash([]);

          // Price label
          const crossPrice = priceLow + (1 - (my - priceY) / priceH) * totalRange;
          const priceText = crossPrice.toFixed(dec);
          ctx.fillStyle = "rgba(201,168,76,0.9)";
          const labelW = ctx.measureText(priceText).width + 8;
          ctx.fillRect(chartX + chartW + 1, my - 8, labelW + 4, 16);
          ctx.fillStyle = "#0A0908";
          ctx.font = "bold 8px JetBrains Mono, monospace";
          ctx.textAlign = "left";
          ctx.fillText(priceText, chartX + chartW + 5, my + 3);

          // Time label
          const candleIdx = Math.floor((mx - chartX) / candleW);
          if (candleIdx >= 0 && candleIdx < visibleCandles.length) {
            const cd = new Date(visibleCandles[candleIdx].time * 1000);
            const intv = s.interval;
            let timeText: string;
            if (intv === "1d" || intv === "1wk") {
              timeText = `${cd.getFullYear()}-${String(cd.getMonth() + 1).padStart(2, "0")}-${String(cd.getDate()).padStart(2, "0")}`;
            } else {
              timeText = `${String(cd.getHours()).padStart(2, "0")}:${String(cd.getMinutes()).padStart(2, "0")}`;
            }
            const tw = ctx.measureText(timeText).width + 8;
            ctx.fillStyle = "rgba(201,168,76,0.9)";
            ctx.fillRect(mx - tw / 2, priceY + priceH + 2, tw, 14);
            ctx.fillStyle = "#0A0908";
            ctx.font = "bold 8px JetBrains Mono, monospace";
            ctx.textAlign = "center";
            ctx.fillText(timeText, mx, priceY + priceH + 12);

            // OHLCV tooltip
            const hc = visibleCandles[candleIdx];
            const ohlcText = `O:${hc.open.toFixed(dec)} H:${hc.high.toFixed(dec)} L:${hc.low.toFixed(dec)} C:${hc.close.toFixed(dec)}`;
            ctx.fillStyle = "rgba(201,168,76,0.35)";
            ctx.font = "8px JetBrains Mono, monospace";
            ctx.textAlign = "left";
            ctx.fillText(ohlcText, chartX + 4, priceY + 22);
          }

          ctx.restore();
        }
      }
    }

    // Event handlers
    function onWheel(e: WheelEvent) {
      e.preventDefault();
      const allLen = s.candles.length;
      if (allLen < 2) return;

      const rect = canvas!.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      const chartLeft = 4;
      const chartRight = 60;
      const cW = rect.width - chartLeft - chartRight;

      const dataRange = s.viewEnd - s.viewStart;
      const visCount = dataRange + s.rightPadding;
      const mouseRatio = Math.max(0, Math.min(1, (mouseX - chartLeft) / cW));
      const mouseSlot = s.viewStart + mouseRatio * visCount;

      const zoomFactor = e.deltaY > 0 ? 1.1 : 0.91;
      let newVisCount = Math.round(visCount * zoomFactor);
      newVisCount = Math.max(MIN_VISIBLE, Math.min(allLen + Math.floor(allLen * 0.6), newVisCount));

      let newViewStart = Math.round(mouseSlot - mouseRatio * newVisCount);
      const padRatio = visCount > 0 ? s.rightPadding / visCount : 0;
      let newPad = Math.round(newVisCount * padRatio);
      const maxPad = Math.floor(newVisCount * 0.6);
      if (newPad > maxPad) newPad = maxPad;

      const newDataRange = newVisCount - newPad;
      if (newViewStart < 0) newViewStart = 0;
      if (newViewStart + newDataRange > allLen) {
        newViewStart = Math.max(0, allLen - newDataRange);
      }

      s.viewStart = newViewStart;
      s.viewEnd = newViewStart + newDataRange;
      s.rightPadding = newPad;
      s.momentumVx = 0;
      s.momentumVy = 0;
    }

    function onMouseDown(e: MouseEvent) {
      e.preventDefault();
      s.isDragging = true;
      s.dragStartX = e.clientX;
      s.dragStartY = e.clientY;
      s.dragViewStart = s.viewStart;
      s.dragViewEnd = s.viewEnd;
      s.dragStartPad = s.rightPadding;
      s.dragStartPriceOffset = s.priceOffset;
      s.momentumVx = 0;
      s.momentumVy = 0;
      s.dragHistory = [{ x: e.clientX, y: e.clientY, t: performance.now() }];
      canvas!.style.cursor = "grabbing";
    }

    function onMouseMove(e: MouseEvent) {
      const rect = canvas!.getBoundingClientRect();
      s.mouseX = e.clientX - rect.left;
      s.mouseY = e.clientY - rect.top;

      if (s.isDragging) {
        const allLen = s.candles.length;
        const cW = rect.width - 64;
        const visCount = (s.dragViewEnd - s.dragViewStart) + s.dragStartPad;
        const candlePx = cW / visCount;
        const dx = e.clientX - s.dragStartX;
        const shift = Math.round(-dx / candlePx);

        let newStart = s.dragViewStart + shift;
        let newPad = s.dragStartPad - shift;
        const maxPad = Math.floor(visCount * 0.6);
        if (newPad < 0) { newStart -= newPad; newPad = 0; }
        if (newPad > maxPad) { newStart -= (newPad - maxPad); newPad = maxPad; }
        if (newStart < 0) { newPad += newStart; newStart = 0; }
        const dataSlots = visCount - newPad;
        if (newStart + dataSlots > allLen) {
          newStart = Math.max(0, allLen - dataSlots);
        }
        s.viewStart = newStart;
        s.viewEnd = newStart + dataSlots;
        s.rightPadding = Math.max(0, newPad);

        const dy = e.clientY - s.dragStartY;
        const pH = (rect.height - 38) * 0.82;
        if (s.lastVisibleRange && pH > 0) {
          s.priceOffset = s.dragStartPriceOffset + (dy / pH) * s.lastVisibleRange;
        }

        s.dragHistory.push({ x: e.clientX, y: e.clientY, t: performance.now() });
        if (s.dragHistory.length > 6) s.dragHistory.shift();
      }
    }

    function onMouseUp() {
      if (s.isDragging && s.dragHistory.length >= 2) {
        const last = s.dragHistory[s.dragHistory.length - 1];
        const prev = s.dragHistory[Math.max(0, s.dragHistory.length - 3)];
        const dt = (last.t - prev.t) / 1000;
        if (dt > 0 && dt < 0.15) {
          s.momentumVx = (last.x - prev.x) / dt;
          s.momentumVy = (last.y - prev.y) / dt;
        } else {
          s.momentumVx = 0;
          s.momentumVy = 0;
        }
      }
      s.isDragging = false;
      s.dragHistory = [];
      if (canvas) {
        const rect = canvas.getBoundingClientRect();
        const inside = s.mouseX >= 0 && s.mouseX <= rect.width && s.mouseY >= 0 && s.mouseY <= rect.height;
        if (!inside) {
          s.mouseX = -1;
          s.mouseY = -1;
        }
        canvas.style.cursor = "crosshair";
      }
    }

    function onMouseLeave() {
      if (!s.isDragging) {
        s.mouseX = -1;
        s.mouseY = -1;
        canvas!.style.cursor = "crosshair";
      }
    }

    function onDblClick() {
      s.viewEnd = s.candles.length;
      s.viewStart = Math.max(0, s.candles.length - DEFAULT_VISIBLE);
      s.rightPadding = 0;
      s.priceOffset = 0;
    }

    function onKeyDown(e: KeyboardEvent) {
      const allLen = s.candles.length;
      if (allLen < 2) return;
      const visCount = (s.viewEnd - s.viewStart) + s.rightPadding;
      const step = Math.max(1, Math.round(visCount * 0.05));

      if (e.key === "ArrowLeft") {
        e.preventDefault();
        let newStart = s.viewStart - step;
        let newPad = s.rightPadding + step;
        const maxPad = Math.floor(visCount * 0.6);
        if (newPad > maxPad) { newStart -= (newPad - maxPad); newPad = maxPad; }
        if (newStart < 0) { newPad += newStart; newStart = 0; }
        s.viewStart = newStart;
        s.viewEnd = newStart + (visCount - newPad);
        s.rightPadding = Math.max(0, newPad);
      } else if (e.key === "ArrowRight") {
        e.preventDefault();
        let newStart = s.viewStart + step;
        let newPad = s.rightPadding - step;
        if (newPad < 0) { newStart -= newPad; newPad = 0; }
        const dataSlots = visCount - newPad;
        if (newStart + dataSlots > allLen) {
          newStart = Math.max(0, allLen - dataSlots);
        }
        s.viewStart = newStart;
        s.viewEnd = newStart + dataSlots;
        s.rightPadding = Math.max(0, newPad);
      } else if (e.key === "ArrowUp" || e.key === "+" || e.key === "=") {
        e.preventDefault();
        const zf = 0.91;
        let nv = Math.round(visCount * zf);
        nv = Math.max(MIN_VISIBLE, nv);
        const padRatio = visCount > 0 ? s.rightPadding / visCount : 0;
        s.rightPadding = Math.min(Math.round(nv * padRatio), Math.floor(nv * 0.6));
        const nd = nv - s.rightPadding;
        if (s.viewStart + nd > allLen) s.viewStart = Math.max(0, allLen - nd);
        s.viewEnd = s.viewStart + nd;
      } else if (e.key === "ArrowDown" || e.key === "-") {
        e.preventDefault();
        const zf = 1.1;
        let nv = Math.round(visCount * zf);
        nv = Math.min(allLen + Math.floor(allLen * 0.6), nv);
        const padRatio = visCount > 0 ? s.rightPadding / visCount : 0;
        s.rightPadding = Math.min(Math.round(nv * padRatio), Math.floor(nv * 0.6));
        const nd = nv - s.rightPadding;
        if (s.viewStart + nd > allLen) s.viewStart = Math.max(0, allLen - nd);
        s.viewEnd = s.viewStart + nd;
      } else if (e.key === "Home") {
        e.preventDefault();
        s.viewEnd = allLen;
        s.viewStart = Math.max(0, allLen - DEFAULT_VISIBLE);
        s.rightPadding = 0;
        s.priceOffset = 0;
      }
    }

    function onTouchStart(e: TouchEvent) {
      if (e.touches.length === 1) {
        const t = e.touches[0];
        s.isDragging = true;
        s.dragStartX = t.clientX;
        s.dragStartY = t.clientY;
        s.dragViewStart = s.viewStart;
        s.dragViewEnd = s.viewEnd;
        s.dragStartPad = s.rightPadding;
        s.dragStartPriceOffset = s.priceOffset;
        s.momentumVx = 0;
        s.momentumVy = 0;
        s.dragHistory = [{ x: t.clientX, y: t.clientY, t: performance.now() }];
      }
    }

    function onTouchMove(e: TouchEvent) {
      e.preventDefault();
      if (e.touches.length === 1 && s.isDragging) {
        const t = e.touches[0];
        const rect = canvas!.getBoundingClientRect();
        const allLen = s.candles.length;
        const cW = rect.width - 64;
        const visCount = (s.dragViewEnd - s.dragViewStart) + s.dragStartPad;
        const candlePx = cW / visCount;
        const dx = t.clientX - s.dragStartX;
        const shift = Math.round(-dx / candlePx);

        let newStart = s.dragViewStart + shift;
        let newPad = s.dragStartPad - shift;
        const maxPad = Math.floor(visCount * 0.6);
        if (newPad < 0) { newStart -= newPad; newPad = 0; }
        if (newPad > maxPad) { newStart -= (newPad - maxPad); newPad = maxPad; }
        if (newStart < 0) { newPad += newStart; newStart = 0; }
        const dataSlots = visCount - newPad;
        if (newStart + dataSlots > allLen) {
          newStart = Math.max(0, allLen - dataSlots);
        }
        s.viewStart = newStart;
        s.viewEnd = newStart + dataSlots;
        s.rightPadding = Math.max(0, newPad);

        const dy = t.clientY - s.dragStartY;
        const pH = (rect.height - 38) * 0.82;
        if (s.lastVisibleRange && pH > 0) {
          s.priceOffset = s.dragStartPriceOffset + (dy / pH) * s.lastVisibleRange;
        }

        s.dragHistory.push({ x: t.clientX, y: t.clientY, t: performance.now() });
        if (s.dragHistory.length > 6) s.dragHistory.shift();
      }
    }

    function onTouchEnd() {
      if (s.isDragging && s.dragHistory.length >= 2) {
        const last = s.dragHistory[s.dragHistory.length - 1];
        const prev = s.dragHistory[Math.max(0, s.dragHistory.length - 3)];
        const dt = (last.t - prev.t) / 1000;
        if (dt > 0 && dt < 0.15) {
          s.momentumVx = (last.x - prev.x) / dt;
          s.momentumVy = (last.y - prev.y) / dt;
        }
      }
      s.isDragging = false;
      s.dragHistory = [];
    }

    canvas.addEventListener("wheel", onWheel, { passive: false });
    canvas.addEventListener("mousedown", onMouseDown);
    canvas.addEventListener("dblclick", onDblClick);
    canvas.addEventListener("touchstart", onTouchStart, { passive: true });
    canvas.addEventListener("touchmove", onTouchMove, { passive: false });
    canvas.addEventListener("touchend", onTouchEnd);
    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);
    canvas.addEventListener("mouseleave", onMouseLeave);
    window.addEventListener("keydown", onKeyDown);

    function animate() {
      render();
      animId = requestAnimationFrame(animate);
    }
    animId = requestAnimationFrame(animate);

    return () => {
      cancelAnimationFrame(animId);
      canvas.removeEventListener("wheel", onWheel);
      canvas.removeEventListener("mousedown", onMouseDown);
      canvas.removeEventListener("dblclick", onDblClick);
      canvas.removeEventListener("touchstart", onTouchStart);
      canvas.removeEventListener("touchmove", onTouchMove);
      canvas.removeEventListener("touchend", onTouchEnd);
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseup", onMouseUp);
      canvas.removeEventListener("mouseleave", onMouseLeave);
      window.removeEventListener("keydown", onKeyDown);
    };
  }, []);

  return (
    <div
      className={fillContainer ? "w-full h-full relative" : "w-full relative rounded overflow-hidden border border-border/50"}
      style={{ minHeight: fillContainer ? "400px" : "380px", outline: "none" }}
      tabIndex={0}
    >
      {/* Timeframe selector */}
      <div className="absolute top-2 left-2 z-20 flex items-center gap-0.5">
        {TIMEFRAMES.map((tf) => (
          <button
            key={tf}
            onClick={() => setLocalInterval(tf)}
            style={{
              padding: "2px 7px",
              borderRadius: 3,
              fontSize: 10,
              fontFamily: "JetBrains Mono, monospace",
              fontWeight: 700,
              letterSpacing: "0.04em",
              cursor: "pointer",
              border: interval === tf
                ? "1px solid rgba(201,168,76,0.6)"
                : "1px solid rgba(201,168,76,0.15)",
              background: interval === tf
                ? "rgba(201,168,76,0.15)"
                : "rgba(6,11,22,0.7)",
              color: interval === tf
                ? "rgba(229,213,160,1)"
                : "rgba(201,168,76,0.45)",
              transition: "all 0.15s ease",
            }}
          >
            {tf.toUpperCase()}
          </button>
        ))}
      </div>

      {loading && (
        <div className="absolute inset-0 flex items-center justify-center z-10" style={{ background: "rgba(6,11,22,0.85)" }}>
          <div className="flex items-center gap-2 text-[14px] font-mono" style={{ color: "rgba(201,168,76,0.6)" }}>
            <span className="h-3 w-3 rounded-full border-2 border-amber-500/30 border-t-amber-500 animate-spin" />
            LOADING {ticker}…
          </div>
        </div>
      )}
      {feedUnavailable && (
        <div className="absolute inset-0 flex flex-col items-center justify-center p-6 text-center z-20 font-mono" style={{ background: "rgba(6,11,22,0.95)" }}>
          <div className="text-[12px] tracking-widest text-amber-400 border border-amber-500/30 bg-amber-500/10 px-2.5 py-1 mb-2 rounded-sm font-bold">
            FEED UNAVAILABLE
          </div>
          <div className="text-sm font-semibold text-foreground mb-1">
            {ticker}
          </div>
          <div className="text-xs text-muted-foreground max-w-md leading-relaxed">
            {feedUnavailable}
          </div>
          <div className="text-[12px] text-muted-foreground/60 mt-3">
            Institutional restraint: abstaining from simulating synthetic order flow.
          </div>
        </div>
      )}
      <canvas
        ref={canvasRef}
        style={{ width: "100%", height: fillContainer ? "100%" : "380px", cursor: "crosshair" }}
      />
    </div>
  );
}
