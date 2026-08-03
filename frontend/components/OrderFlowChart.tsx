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
  { t: 0.00, r: 4,   g: 12,  b: 26,  a: 0.00 },
  { t: 0.06, r: 7,   g: 24,  b: 50,  a: 0.30 },
  { t: 0.18, r: 11,  g: 46,  b: 88,  a: 0.50 },
  { t: 0.36, r: 8,   g: 82,  b: 140, a: 0.68 },
  { t: 0.55, r: 0,   g: 128, b: 195, a: 0.82 },
  { t: 0.75, r: 0,   g: 182, b: 228, a: 0.94 },
  { t: 0.90, r: 70,  g: 218, b: 248, a: 1.00 },
  { t: 1.00, r: 205, g: 242, b: 255, a: 1.00 },
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

interface OrderFlowChartProps {
  ticker: string;
  interval?: string;
  fillContainer?: boolean;
}

export function OrderFlowChart({ ticker, interval = "1d", fillContainer }: OrderFlowChartProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [loading, setLoading] = useState(true);

  const state = useRef({
    candles: [] as Candle[],
    viewStart: 0,
    viewEnd: 0,
    mouseX: -1,
    mouseY: -1,
    isDragging: false,
    dragStartX: 0,
    dragViewStart: 0,
    dragViewEnd: 0,
    animTime: 0,
    heatmap: null as HeatmapData | null,
    lastHeatKey: "",
    ticker: "",
    interval: "",
  });

  useEffect(() => {
    let cancelled = false;
    let refreshTimer: ReturnType<typeof setInterval> | null = null;

    async function fetchData(isRefresh = false) {
      if (!isRefresh) setLoading(true);
      const period = INTERVAL_TO_PERIOD[interval] || "6mo";
      try {
        const res = await fetch(
          `${API}/api/v1/market/ohlcv/${encodeURIComponent(ticker)}?period=${period}&interval=${interval}`,
        );
        if (res.ok && !cancelled) {
          const data = await res.json();
          const candles: Candle[] = (data.candles ?? []).map((c: Record<string, number>) => ({
            time: c.time, open: c.open, high: c.high, low: c.low, close: c.close,
            volume: c.volume ?? 0,
          }));
          const s = state.current;
          if (isRefresh && s.candles.length > 0) {
            // On refresh: update price data but preserve zoom/pan position
            s.candles = candles;
            s.lastHeatKey = "";
            // Clamp view if data length changed
            if (s.viewEnd > candles.length) {
              const range = s.viewEnd - s.viewStart;
              s.viewEnd = candles.length;
              s.viewStart = Math.max(0, candles.length - range);
            }
          } else {
            s.candles = candles;
            s.ticker = ticker;
            s.interval = interval;
            s.viewEnd = candles.length;
            s.viewStart = Math.max(0, candles.length - DEFAULT_VISIBLE);
            s.lastHeatKey = "";
          }
          setLoading(false);
        }
      } catch {
        if (!cancelled) setLoading(false);
      }
    }

    fetchData();
    refreshTimer = setInterval(() => fetchData(true), 60_000);

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

      // Background
      const bg = ctx.createLinearGradient(0, 0, 0, H);
      bg.addColorStop(0, "#060b16");
      bg.addColorStop(0.55, "#03060d");
      bg.addColorStop(1, "#010203");
      ctx.fillStyle = bg;
      ctx.fillRect(0, 0, W, H);

      const allCandles = s.candles;
      if (!allCandles || allCandles.length < 2) {
        ctx.fillStyle = "rgba(201,168,76,0.4)";
        ctx.font = "11px JetBrains Mono, monospace";
        ctx.textAlign = "center";
        ctx.fillText("WAITING FOR MARKET DATA...", W / 2, H / 2);
        return;
      }

      const vs = Math.max(0, Math.floor(s.viewStart));
      const ve = Math.min(allCandles.length, Math.ceil(s.viewEnd));
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
      const candleW = chartW / n;

      let priceHigh = -Infinity, priceLow = Infinity, maxVol = 0;
      visibleCandles.forEach(c => {
        if (c.high > priceHigh) priceHigh = c.high;
        if (c.low < priceLow) priceLow = c.low;
        if (c.volume > maxVol) maxVol = c.volume;
      });

      const priceRange = priceHigh - priceLow || 1;
      const pricePad = priceRange * 0.08;
      priceHigh += pricePad;
      priceLow -= pricePad;
      const totalRange = priceHigh - priceLow;

      const priceToY = (p: number) => priceY + (1 - (p - priceLow) / totalRange) * priceH;
      const idxToX = (i: number) => chartX + i * candleW + candleW / 2;

      const currentPrice = visibleCandles[visibleCandles.length - 1].close;
      const dec = getDecimals(currentPrice, s.ticker);

      // === LAYER 1: Blue liquidity heatmap ===
      const hm = s.heatmap;
      if (hm && hm.max > 0) {
        const rows = hm.rows;
        const cols = hm.cols;
        const cellW = chartW / cols;
        const cellH = Math.max(priceH / rows, 1);

        ctx.save();
        ctx.globalCompositeOperation = "lighter";
        for (let row = 0; row < rows; row++) {
          const price = hm.lo + (row + 0.5) * hm.step;
          const y = priceToY(price);
          if (y < priceY - cellH || y > priceY + priceH + cellH) continue;

          for (let col = 0; col < cols; col++) {
            const v = hm.grid[row * cols + col];
            const norm = v / hm.max;
            if (norm < 0.015) continue;
            ctx.fillStyle = heatColor(norm, 1.25);
            const x = chartX + col * cellW;
            ctx.fillRect(x, y - cellH / 2, cellW + 0.8, cellH + 0.8);
          }

          const rowIntensity = hm.rowProfile[row] / hm.rowMax;
          if (rowIntensity > 0.38) {
            const glowAlpha = (rowIntensity - 0.38) / 0.62;
            ctx.save();
            ctx.shadowColor = "rgba(40,205,235,0.8)";
            ctx.shadowBlur = 14;
            ctx.fillStyle = heatColor(0.85 + rowIntensity * 0.15, glowAlpha * 0.75);
            ctx.fillRect(chartX, y - cellH * 1.4, chartW, cellH * 2.8);
            ctx.restore();
          }
        }
        ctx.restore();
      }

      // === LAYER 2: Price axis grid ===
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
      const baseR = Math.max(Math.min(candleW * 0.55, 7), 2.5);

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

        const bodyHi = Math.max(c.open, c.close);
        const bodyLo = Math.min(c.open, c.close);
        const bodyPx = priceToY(bodyLo) - priceToY(bodyHi);

        if (c.high > bodyHi + candleRange * 0.04) {
          const wickSteps = Math.max(Math.round((priceToY(bodyHi) - priceToY(c.high)) / (baseR * 2.5)), 1);
          for (let w = 0; w <= wickSteps; w++) {
            const t = wickSteps > 0 ? w / wickSteps : 0;
            const price = c.high + t * (bodyHi - c.high);
            const fade = 0.18 + t * 0.15;
            drawSphere(ctx, x, priceToY(price), baseR * 0.35, BEAR_RGB, fade);
          }
        }

        if (c.low < bodyLo - candleRange * 0.04) {
          const wickSteps = Math.max(Math.round((priceToY(c.low) - priceToY(bodyLo)) / (baseR * 2.5)), 1);
          for (let w = 0; w <= wickSteps; w++) {
            const t = wickSteps > 0 ? w / wickSteps : 0;
            const price = bodyLo - t * (bodyLo - c.low);
            const fade = 0.18 + (1 - t) * 0.15;
            drawSphere(ctx, x, priceToY(price), baseR * 0.35, BULL_RGB, fade);
          }
        }

        const numBubbles = Math.max(Math.round(bodyPx / (baseR * 1.8)), 2);
        const bodySize = 0.45 + volNorm * 0.55;
        for (let b = 0; b < numBubbles; b++) {
          const t = numBubbles > 1 ? b / (numBubbles - 1) : 0.5;
          const price = bodyLo + t * (bodyHi - bodyLo);
          drawSphere(ctx, x, priceToY(price), baseR * bodySize * 0.72, dirRGB, 0.6);
        }

        const closeY = priceToY(c.close);
        const closeR = baseR * (0.85 + volNorm * 0.7);
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
      const mouseXRatio = (e.clientX - rect.left - 4) / (rect.width - 64);
      const clampedRatio = Math.max(0, Math.min(1, mouseXRatio));

      const currentRange = s.viewEnd - s.viewStart;
      const zoomFactor = e.deltaY > 0 ? 1.15 : 0.87;
      let newRange = Math.round(currentRange * zoomFactor);
      newRange = Math.max(MIN_VISIBLE, Math.min(allLen, newRange));

      const mouseIdx = s.viewStart + clampedRatio * currentRange;
      let newStart = mouseIdx - clampedRatio * newRange;
      let newEnd = mouseIdx + (1 - clampedRatio) * newRange;

      if (newStart < 0) { newEnd -= newStart; newStart = 0; }
      if (newEnd > allLen) { newStart -= (newEnd - allLen); newEnd = allLen; }
      s.viewStart = Math.max(0, Math.round(newStart));
      s.viewEnd = Math.min(allLen, Math.round(newEnd));
    }

    function onMouseDown(e: MouseEvent) {
      e.preventDefault();
      s.isDragging = true;
      s.dragStartX = e.clientX;
      s.dragViewStart = s.viewStart;
      s.dragViewEnd = s.viewEnd;
      canvas!.style.cursor = "grabbing";
    }

    function onMouseMove(e: MouseEvent) {
      const rect = canvas!.getBoundingClientRect();
      s.mouseX = e.clientX - rect.left;
      s.mouseY = e.clientY - rect.top;

      if (s.isDragging) {
        const allLen = s.candles.length;
        const chartW = rect.width - 64;
        const currentRange = s.dragViewEnd - s.dragViewStart;
        const candleW = chartW / currentRange;
        const dx = e.clientX - s.dragStartX;
        const candleShift = Math.round(-dx / candleW);

        let newStart = s.dragViewStart + candleShift;
        let newEnd = s.dragViewEnd + candleShift;

        if (newStart < 0) { newEnd -= newStart; newStart = 0; }
        if (newEnd > allLen) { newStart -= (newEnd - allLen); newEnd = allLen; }
        s.viewStart = Math.max(0, newStart);
        s.viewEnd = Math.min(allLen, newEnd);
      }
    }

    function onMouseUp() {
      s.isDragging = false;
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

    canvas.addEventListener("wheel", onWheel, { passive: false });
    canvas.addEventListener("mousedown", onMouseDown);
    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);
    canvas.addEventListener("mouseleave", onMouseLeave);

    function animate() {
      render();
      animId = requestAnimationFrame(animate);
    }
    animId = requestAnimationFrame(animate);

    return () => {
      cancelAnimationFrame(animId);
      canvas.removeEventListener("wheel", onWheel);
      canvas.removeEventListener("mousedown", onMouseDown);
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseup", onMouseUp);
      canvas.removeEventListener("mouseleave", onMouseLeave);
    };
  }, []);

  return (
    <div
      className={fillContainer ? "w-full h-full relative" : "w-full relative rounded overflow-hidden border border-border/50"}
      style={{ minHeight: fillContainer ? "400px" : "380px" }}
    >
      {loading && (
        <div className="absolute inset-0 flex items-center justify-center z-10" style={{ background: "rgba(6,11,22,0.85)" }}>
          <div className="flex items-center gap-2 text-[14px] font-mono" style={{ color: "rgba(201,168,76,0.6)" }}>
            <span className="h-3 w-3 rounded-full border-2 border-amber-500/30 border-t-amber-500 animate-spin" />
            LOADING {ticker}…
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
