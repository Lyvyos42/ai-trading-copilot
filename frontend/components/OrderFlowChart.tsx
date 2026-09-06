"use client";

import { useEffect, useRef, useState, useCallback } from "react";

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
  /** High percentile of the grid's OWN cells - the normalisation reference. */
  cellRef: number;
  max: number;
  /** False when the feed carries no volume at all (spot FX). */
  hasVolume: boolean;
  hi: number;
  lo: number;
  step: number;
}

interface VolumeBubble {
  index: number;
  price: number;
  ratio: number;
  volume: number;
  isBull: boolean;
}

interface SRLevels {
  support: number[];
  resistance: number[];
  pivot: number;
}

interface OrderFlowChartProps {
  ticker: string;
  interval?: string;
  fillContainer?: boolean;
}

const TIMEFRAMES = ["1m", "5m", "15m", "30m", "1h", "4h", "1d"] as const;

const INTERVAL_TO_PERIOD: Record<string, string> = {
  "1m": "1d",
  "5m": "5d",
  "15m": "5d",
  "30m": "1mo",
  "1h": "3mo",
  "4h": "6mo",
  "1d": "1y",
  "1wk": "2y",
};

const REFRESH_MS: Record<string, number> = {
  "1m": 10_000,
  "5m": 15_000,
  "15m": 30_000,
  "30m": 30_000,
  "1h": 60_000,
  "4h": 120_000,
  "1d": 300_000,
  "1wk": 600_000,
};

// Precise color ramps for Bookmap spectrogram
const HEAT_STOPS = [
  { t: 0.00, r: 0,   g: 4,   b: 16,  a: 0.00 },
  { t: 0.08, r: 2,   g: 10,  b: 40,  a: 0.20 },
  { t: 0.18, r: 6,   g: 22,  b: 75,  a: 0.38 },
  { t: 0.30, r: 10,  g: 50,  b: 130, a: 0.52 },
  { t: 0.44, r: 0,   g: 140, b: 200, a: 0.65 },
  { t: 0.58, r: 0,   g: 190, b: 210, a: 0.72 },
  { t: 0.72, r: 60,  g: 215, b: 165, a: 0.80 },
  { t: 0.84, r: 220, g: 200, b: 40,  a: 0.86 },
  { t: 0.94, r: 255, g: 155, b: 10,  a: 0.92 },
  { t: 1.00, r: 255, g: 255, b: 255, a: 0.98 },
];

function heatColorRGBA(t: number, alphaMul = 1): [number, number, number, number] {
  t = t < 0 ? 0 : t > 1 ? 1 : t;
  let lo = HEAT_STOPS[0];
  let hi = HEAT_STOPS[HEAT_STOPS.length - 1];
  for (let i = 0; i < HEAT_STOPS.length - 1; i++) {
    if (t >= HEAT_STOPS[i].t && t <= HEAT_STOPS[i + 1].t) {
      lo = HEAT_STOPS[i];
      hi = HEAT_STOPS[i + 1];
      break;
    }
  }
  const span = hi.t - lo.t || 1;
  const local = (t - lo.t) / span;
  const r = Math.round(lo.r + (hi.r - lo.r) * local);
  const g = Math.round(lo.g + (hi.g - lo.g) * local);
  const b = Math.round(lo.b + (hi.b - lo.b) * local);
  const a = Math.min(255, Math.max(0, Math.round((lo.a + (hi.a - lo.a) * local) * alphaMul * 255)));
  return [r, g, b, a];
}

function getDecimals(price: number, ticker: string): number {
  const t = ticker.toUpperCase().replace(/[/\-=X]/g, "");
  const jpyPairs = ["USDJPY", "EURJPY", "GBPJPY", "CADJPY", "CHFJPY", "AUDJPY", "NZDJPY"];
  if (jpyPairs.includes(t)) return 3;
  if (t.length === 6 && !t.startsWith("XA") && !t.startsWith("US5") && !t.startsWith("US3")) return 5;
  if (price > 1000) return 2;
  if (price > 100) return 2;
  if (price > 1) return 2;
  if (price > 0.01) return 4;
  return 5;
}

function computeSRLevels(candles: Candle[]): SRLevels | null {
  if (candles.length < 10) return null;
  const recent = candles.slice(-Math.min(candles.length, 100));
  let hi = -Infinity;
  let lo = Infinity;
  const lastClose = recent[recent.length - 1].close;
  recent.forEach((c) => {
    if (c.high > hi) hi = c.high;
    if (c.low < lo) lo = c.low;
  });
  const pivot = (hi + lo + lastClose) / 3;
  const r1 = 2 * pivot - lo;
  const s1 = 2 * pivot - hi;
  const r2 = pivot + (hi - lo);
  const s2 = pivot - (hi - lo);
  return {
    resistance: [r1, r2].filter((r) => r > lastClose),
    support: [s1, s2].filter((s) => s < lastClose),
    pivot,
  };
}

/**
 * A rolling profile of activity at price, drawn as a spectrogram.
 *
 * Two things this deliberately does not do, both of which the previous
 * version did.
 *
 * IT DOES NOT INVENT VOLUME. Yahoo publishes no volume for spot FX - checked,
 * 1440 consecutive USDJPY bars, every one of them zero - and `c.volume || 1`
 * turned that absence into a uniform 1 per bar, which then flowed into the
 * profile, the bubbles and the depth ladder as though it were data. Where
 * there is no volume this builds a TIME-at-price profile instead: every bar
 * contributes equally, which is exactly what a TPO profile is, and is a real
 * thing rather than a fabricated one. `hasVolume` travels with the result so
 * the UI can say which of the two it is showing.
 *
 * IT DOES NOT NORMALISE AGAINST A DIFFERENT SCALE. Each cell here is an
 * accumulation over many bars. The old code divided it by v95 - the 95th
 * percentile of a SINGLE bar's volume - so the ratio was far above 1 almost
 * everywhere, `min(1, v / v95)` clamped nearly every cell to 1.0, and 1.0 is
 * the top of the colour ramp: opaque white. That was the white rectangle. It
 * was wrong on volume-bearing symbols too, just less visibly. The reference
 * is now a high percentile of the grid itself.
 */
function buildHeatmap(candles: Candle[]): HeatmapData | null {
  if (!candles || candles.length < 2) return null;

  const hasVolume = candles.some((c) => (c.volume || 0) > 0);

  let hi = -Infinity;
  let lo = Infinity;
  for (const c of candles) {
    if (c.high > hi) hi = c.high;
    if (c.low < lo) lo = c.low;
  }
  if (!isFinite(hi) || !isFinite(lo) || hi <= lo) return null;

  const pad = (hi - lo) * 0.08;
  hi += pad;
  lo -= pad;

  const rows = 160;
  const cols = candles.length;
  const step = (hi - lo) / rows;
  if (step <= 0) return null;

  // The profile decays as it walks forward, so a column shows what was
  // trading recently rather than the sum of everything that ever happened.
  // Without the decay the right-hand edge is always the hottest part of the
  // chart by construction, which tells the reader nothing.
  const halfLife = Math.max(12, Math.min(60, cols * 0.15));
  const decay = Math.pow(0.5, 1 / halfLife);

  const acc = new Float32Array(rows);
  const grid = new Float32Array(rows * cols);
  const share = new Float32Array(rows);
  let cellMax = 0;

  for (let col = 0; col < cols; col++) {
    const c = candles[col];
    for (let r = 0; r < rows; r++) acc[r] *= decay;

    // Spread the bar's weight across the prices it actually traded through,
    // body heavier than wick. The old code keyed the whole bar at its
    // midpoint, collapsing a range into a single row - which is why the
    // result read as a horizontal smear instead of structure.
    const weight = hasVolume ? c.volume : 1;
    if (weight > 0) {
      const rLo = Math.max(0, Math.min(rows - 1, Math.floor((c.low - lo) / step)));
      const rHi = Math.max(0, Math.min(rows - 1, Math.floor((c.high - lo) / step)));
      const bodyLo = Math.min(c.open, c.close);
      const bodyHi = Math.max(c.open, c.close);

      let wsum = 0;
      for (let r = rLo; r <= rHi; r++) {
        const price = lo + (r + 0.5) * step;
        const w = price >= bodyLo && price <= bodyHi ? 1.0 : 0.35;
        share[r] = w;
        wsum += w;
      }
      if (wsum > 0) {
        for (let r = rLo; r <= rHi; r++) acc[r] += (weight * share[r]) / wsum;
      }
    }

    for (let r = 0; r < rows; r++) {
      const v = acc[r];
      grid[r * cols + col] = v;
      if (v > cellMax) cellMax = v;
    }
  }

  // Normalise against a high percentile of the grid's own non-empty cells.
  // The maximum alone would let one hot cell wash everything else down into
  // the dark end of the ramp; a percentile keeps the body of the picture
  // inside the colours and lets the genuine peaks clip.
  const stride = Math.max(1, Math.floor(grid.length / 20000));
  const sample: number[] = [];
  for (let i = 0; i < grid.length; i += stride) {
    if (grid[i] > 0) sample.push(grid[i]);
  }
  sample.sort((a, b) => a - b);
  const cellRef =
    sample.length > 20 ? sample[Math.floor(sample.length * 0.97)] : cellMax;

  return {
    grid,
    rows,
    cols,
    cellRef: cellRef > 0 ? cellRef : 1,
    max: cellMax,
    hasVolume,
    hi,
    lo,
    step,
  };
}

/**
 * Bars whose volume is a genuine outlier against a trailing median.
 *
 * That is all this claims to be. It is NOT absorption and NOT delta: the feed
 * behind this chart is OHLCV, so there is no bid/ask split from which a delta
 * could be computed. The previous version drew a signed "+42k" that was only
 * the candle's direction wearing a delta's clothes, thresholded at the 85th
 * percentile so roughly one bar in seven qualified, and on a feed with no
 * volume at all it marked every bar on the chart.
 *
 * Computed once per fetch rather than per frame - the render loop runs at
 * 60fps and this does not change between ticks.
 */
function computeVolumeBubbles(candles: Candle[]): VolumeBubble[] {
  const WINDOW = 30;
  const MIN_HISTORY = 8;
  const MIN_RATIO = 2.0;

  const out: VolumeBubble[] = [];
  if (!candles.some((c) => (c.volume || 0) > 0)) return out;

  for (let i = 0; i < candles.length; i++) {
    const v = candles[i].volume || 0;
    if (v <= 0) continue;

    const win: number[] = [];
    for (let j = Math.max(0, i - WINDOW); j < i; j++) {
      const w = candles[j].volume || 0;
      if (w > 0) win.push(w);
    }
    if (win.length < MIN_HISTORY) continue;

    // Median, not mean: one spike in the window would drag a mean upward and
    // hide the next spike behind it.
    win.sort((a, b) => a - b);
    const med = win[Math.floor(win.length / 2)];
    if (med <= 0) continue;

    const ratio = v / med;
    if (ratio < MIN_RATIO) continue;

    const c = candles[i];
    const isBull = c.close >= c.open;
    out.push({
      index: i,
      price: isBull ? c.high : c.low,
      ratio,
      volume: v,
      isBull,
    });
  }
  return out;
}

export function OrderFlowChart({
  ticker,
  interval: externalInterval = "1d",
  fillContainer = true,
}: OrderFlowChartProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [loading, setLoading] = useState(true);
  const [feedUnavailable, setFeedUnavailable] = useState<string | null>(null);
  const [localInterval, setLocalInterval] = useState(externalInterval);
  const [autoFit, setAutoFit] = useState(false);
  const [showHeatmap, setShowHeatmap] = useState(true);
  const [showBubbles, setShowBubbles] = useState(true);
  const [showDOM, setShowDOM] = useState(true);
  // Whether the feed carries volume at all. Spot FX does not, and the
  // volume-derived layers must say so rather than draw invented structure.
  const [hasVolume, setHasVolume] = useState(true);

  useEffect(() => {
    setLocalInterval(externalInterval);
  }, [externalInterval]);

  const interval = localInterval;

  const state = useRef({
    candles: [] as Candle[],
    levels: null as SRLevels | null,
    heatmap: null as HeatmapData | null,
    bubbles: [] as VolumeBubble[],
    hasVolume: true,
    heatCanvas: null as HTMLCanvasElement | null,
    ticker: "",
    interval: "",
    autoFit: false,
    showHeatmap: true,
    showBubbles: true,
    showDOM: true,

    // Transformation state
    zoomX: 1.0,
    zoomY: 1.0,
    panX: 0,
    panY: 0,
    isDragging: false,
    isDraggingPriceScale: false,
    dragStartX: 0,
    dragStartY: 0,
    dragStartPanX: 0,
    dragStartPanY: 0,
    dragStartPriceY: 0,
    initialZoomY: 1.0,
    mouseX: -1,
    mouseY: -1,
    animTime: 0,
    defaultBarSpacing: 16,
  });

  // Sync state ref with UI states
  useEffect(() => {
    state.current.autoFit = autoFit;
  }, [autoFit]);
  useEffect(() => {
    state.current.showHeatmap = showHeatmap;
  }, [showHeatmap]);
  useEffect(() => {
    state.current.showBubbles = showBubbles;
  }, [showBubbles]);
  useEffect(() => {
    state.current.showDOM = showDOM;
  }, [showDOM]);

  // Data fetching
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
            time: c.time,
            open: c.open,
            high: c.high,
            low: c.low,
            close: c.close,
            volume: c.volume ?? 0,
          }));

          const s = state.current;
          s.candles = candles;
          s.levels = computeSRLevels(candles);
          const hm = buildHeatmap(candles);
          s.heatmap = hm;
          s.bubbles = computeVolumeBubbles(candles);
          s.hasVolume = hm ? hm.hasVolume : false;
          setHasVolume(s.hasVolume);
          s.ticker = ticker;
          s.interval = interval;
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

  // Main canvas render and interaction loop
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

      // Dark institutional background
      const bg = ctx.createLinearGradient(0, 0, 0, H);
      bg.addColorStop(0, "#060b16");
      bg.addColorStop(0.55, "#03060d");
      bg.addColorStop(1, "#010203");
      ctx.fillStyle = bg;
      ctx.fillRect(0, 0, W, H);

      const candles = s.candles;
      if (!candles || candles.length < 2) {
        ctx.fillStyle = "rgba(201,168,76,0.4)";
        ctx.font = "11px JetBrains Mono, monospace";
        ctx.textAlign = "center";
        ctx.fillText("WAITING FOR MARKET DATA...", W / 2, H / 2);
        return;
      }

      // Layout partitioning
      const rightMargin = s.showDOM && s.hasVolume ? 160 : 75; // Right price scale & L2 DOM ladder gutter
      const timeAxisH = 22;
      const plotW = Math.max(100, W - rightMargin);
      const plotH = Math.max(100, H - timeAxisH);

      const count = candles.length;
      let barSpacing: number;
      let indexToX: (idx: number) => number;
      let xToIndex: (x: number) => number;

      if (s.autoFit) {
        // AutoFit: squeeze entire dataset within viewport
        const baseBarSpacing = Math.max((plotW - 60) / Math.max(count - 1, 1), 3);
        barSpacing = baseBarSpacing;
        indexToX = (idx) => 25 + idx * baseBarSpacing;
        xToIndex = (x) => Math.round((x - 25) / baseBarSpacing);
      } else {
        // Professional Live Auto-Scroll: Constant bar spacing right-anchored to live market (NEVER shrinks)
        barSpacing = Math.max(3.0, Math.min(65.0, s.defaultBarSpacing * Math.max(0.1, s.zoomX)));
        const rightAnchor = plotW - 45;
        indexToX = (idx) => rightAnchor + s.panX - (count - 1 - idx) * barSpacing;
        xToIndex = (x) => Math.round(count - 1 - (rightAnchor + s.panX - x) / barSpacing);
      }

      // Dynamic price bounds computed strictly from VISIBLE candles on screen
      let minP = Infinity;
      let maxP = -Infinity;
      let visibleCount = 0;

      for (let i = 0; i < count; i++) {
        const x = indexToX(i);
        if (x >= -35 && x <= plotW + 35) {
          const c = candles[i];
          if (c.low < minP) minP = c.low;
          if (c.high > maxP) maxP = c.high;
          visibleCount++;
        }
      }

      const currentPrice = candles[candles.length - 1].close;
      if (visibleCount === 0 || minP === Infinity) {
        minP = currentPrice * 0.995;
        maxP = currentPrice * 1.005;
      }

      minP = Math.min(minP, currentPrice);
      maxP = Math.max(maxP, currentPrice);

      const span = Math.max(maxP - minP, currentPrice * 0.002 || 0.01);
      let effMinP = minP - span * 0.08;
      let effMaxP = maxP + span * 0.08;

      // Vertical price scale transformation (drag zoom and pan)
      if (s.zoomY !== 1.0 || s.panY !== 0) {
        const centerP = (effMinP + effMaxP) / 2;
        const currentSpan = (effMaxP - effMinP) / Math.max(0.1, s.zoomY);
        const halfSpan = currentSpan / 2;
        const yShift = (s.panY / Math.max(plotH, 100)) * currentSpan;
        effMinP = centerP - halfSpan + yShift;
        effMaxP = centerP + halfSpan + yShift;
      }

      const totalRange = effMaxP - effMinP || 1;
      const priceToY = (p: number) => plotH - ((p - effMinP) / totalRange) * plotH;
      const yToPrice = (y: number) => effMinP + ((plotH - y) / plotH) * totalRange;

      const dec = getDecimals(currentPrice, s.ticker);

      // --- LAYER 1: Subtle Grid Lines ---
      ctx.save();
      ctx.strokeStyle = "rgba(255, 255, 255, 0.035)";
      ctx.lineWidth = 1;
      const hSteps = 6;
      for (let i = 0; i <= hSteps; i++) {
        const y = (plotH / hSteps) * i;
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(plotW, y);
        ctx.stroke();
      }
      const vSteps = 8;
      for (let i = 1; i < vSteps; i++) {
        const x = (plotW / vSteps) * i;
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, plotH);
        ctx.stroke();
      }
      ctx.restore();

      // --- LAYER 2: Bookmap Continuous Liquidity Spectrogram Heatmap ---
      const hm = s.heatmap;
      if (s.showHeatmap && hm && hm.max > 0) {
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

        const octx = oc.getContext("2d", { willReadFrequently: true });
        if (octx) {
          const imgData = octx.createImageData(hCols, hRows);
          const pixels = imgData.data;
          // The grid's own scale - see buildHeatmap. Using a single bar's
          // volume here is what painted the plot white.
          const vRef = hm.cellRef > 0 ? hm.cellRef : hm.max;

          for (let row = 0; row < hRows; row++) {
            const imgRow = hRows - 1 - row;
            for (let col = 0; col < hCols; col++) {
              const v = hm.grid[row * hCols + col];
              // Gamma below 1 lifts the mid range without flattening the top,
              // so resting structure is visible and peaks still clip to white.
              const norm = Math.pow(Math.min(1, Math.max(0, v / vRef)), 0.7);
              if (norm < 0.05) continue;

              const [r, g, b, a] = heatColorRGBA(norm, 1.0);
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
          ctx.rect(0, 0, plotW, plotH);
          ctx.clip();
          ctx.imageSmoothingEnabled = true;
          ctx.imageSmoothingQuality = "high";

          const hmTopY = priceToY(hm.hi);
          const hmBotY = priceToY(hm.lo);
          const hmScreenH = hmBotY - hmTopY;

          // Draw heatmap aligned to candle horizontal coordinates
          const leftX = indexToX(0) - barSpacing / 2;
          const totalW = count * barSpacing;
          ctx.drawImage(oc, 0, 0, hCols, hRows, leftX, hmTopY, totalW, hmScreenH);
          ctx.restore();

          // Say which profile this is, on the canvas, for the same reason the
          // ladder's caption is on the canvas: it has to survive a screenshot.
          // Time-at-price and volume-at-price look identical and mean
          // different things.
          ctx.save();
          ctx.textAlign = "left";
          ctx.textBaseline = "alphabetic";
          ctx.font = "8px JetBrains Mono, monospace";
          ctx.fillStyle = hm.hasVolume
            ? "rgba(56,189,248,0.55)"
            : "rgba(245,158,11,0.75)";
          ctx.fillText(
            hm.hasVolume
              ? "VOLUME AT PRICE - FROM BARS, NOT ORDER BOOK"
              : "TIME AT PRICE - THIS FEED PUBLISHES NO VOLUME",
            8, plotH - 4);
          ctx.restore();
        }
      }

      // --- LAYER 3: Key S/R Resistance & Support Levels ---
      const levels = s.levels;
      if (levels) {
        levels.resistance.forEach((r) => {
          const y = priceToY(r);
          if (y < -5 || y > plotH + 5) return;
          ctx.save();
          ctx.strokeStyle = "rgba(239, 68, 68, 0.45)";
          ctx.setLineDash([4, 3]);
          ctx.lineWidth = 1;
          ctx.beginPath();
          ctx.moveTo(0, y);
          ctx.lineTo(plotW, y);
          ctx.stroke();
          ctx.fillStyle = "rgba(239, 68, 68, 0.75)";
          ctx.font = "bold 8.5px JetBrains Mono, monospace";
          ctx.textAlign = "left";
          ctx.fillText(`RESISTANCE ${r.toFixed(dec)}`, 10, y - 3);
          ctx.restore();
        });

        levels.support.forEach((sv) => {
          const y = priceToY(sv);
          if (y < -5 || y > plotH + 5) return;
          ctx.save();
          ctx.strokeStyle = "rgba(16, 185, 129, 0.45)";
          ctx.setLineDash([4, 3]);
          ctx.lineWidth = 1;
          ctx.beginPath();
          ctx.moveTo(0, y);
          ctx.lineTo(plotW, y);
          ctx.stroke();
          ctx.fillStyle = "rgba(16, 185, 129, 0.75)";
          ctx.font = "bold 8.5px JetBrains Mono, monospace";
          ctx.textAlign = "left";
          ctx.fillText(`SUPPORT ${sv.toFixed(dec)}`, 10, y - 3);
          ctx.restore();
        });

        if (levels.pivot) {
          const y = priceToY(levels.pivot);
          if (y >= 0 && y <= plotH) {
            ctx.save();
            ctx.strokeStyle = "rgba(201, 168, 76, 0.35)";
            ctx.setLineDash([2, 4]);
            ctx.lineWidth = 0.9;
            ctx.beginPath();
            ctx.moveTo(0, y);
            ctx.lineTo(plotW, y);
            ctx.stroke();
            ctx.fillStyle = "rgba(201, 168, 76, 0.65)";
            ctx.font = "bold 8px JetBrains Mono, monospace";
            ctx.textAlign = "left";
            ctx.fillText(`PIVOT ${levels.pivot.toFixed(dec)}`, 10, y - 3);
            ctx.restore();
          }
        }
      }

      // --- LAYER 4: EMA Technical Rays ---
      if (candles.length > 21) {
        const drawEma = (period: number, color: string) => {
          const k = 2 / (period + 1);
          let prev = candles[0].close;
          ctx.beginPath();
          let started = false;
          for (let i = 0; i < count; i++) {
            const val = candles[i].close * k + prev * (1 - k);
            prev = val;
            if (i >= period) {
              const x = indexToX(i);
              const y = priceToY(val);
              if (!started) {
                ctx.moveTo(x, y);
                started = true;
              } else {
                ctx.lineTo(x, y);
              }
            }
          }
          ctx.strokeStyle = color;
          ctx.lineWidth = 1.1;
          ctx.stroke();
        };

        drawEma(9, "rgba(233, 208, 130, 0.55)");
        drawEma(21, "rgba(56, 189, 248, 0.45)");
      }

      // --- LAYER 5: Institutional Candlesticks Skeleton ---
      ctx.save();
      const candleBodyW = Math.max(2, Math.min(24, barSpacing * 0.65));

      for (let i = 0; i < count; i++) {
        const x = indexToX(i);
        if (x < -30 || x > plotW + 30) continue;

        const c = candles[i];
        const isBull = c.close >= c.open;
        const color = isBull ? "#10b981" : "#ef4444";

        const yOpen = priceToY(c.open);
        const yClose = priceToY(c.close);
        const yHigh = priceToY(c.high);
        const yLow = priceToY(c.low);

        // Candle Wick
        ctx.strokeStyle = color;
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(x, yHigh);
        ctx.lineTo(x, yLow);
        ctx.stroke();

        // Candle Body
        const topY = Math.min(yOpen, yClose);
        const bodyH = Math.max(1.5, Math.abs(yOpen - yClose));
        ctx.fillStyle = isBull ? "rgba(16, 185, 129, 0.85)" : "rgba(239, 68, 68, 0.85)";
        ctx.fillRect(x - candleBodyW / 2, topY, candleBodyW, bodyH);
      }
      ctx.restore();

      // --- LAYER 6: Relative-Volume Bubbles ---
      // Marks bars whose volume is an outlier against a trailing median, and
      // claims nothing more than that. Precomputed in computeVolumeBubbles;
      // empty by construction when the feed carries no volume, so nothing is
      // drawn rather than a bubble on every bar.
      if (s.showBubbles && s.bubbles.length) {
        ctx.save();

        let topIdx = -1;
        let topRatio = 0;
        for (const b of s.bubbles) {
          if (b.ratio > topRatio) {
            topRatio = b.ratio;
            topIdx = b.index;
          }
        }

        const maxBubbleR = Math.max(4.0, Math.min(15.0, barSpacing * 0.6));
        const minBubbleR = Math.max(3.0, Math.min(5.0, barSpacing * 0.3));

        for (const b of s.bubbles) {
          if (b.index >= count) continue;
          const x = indexToX(b.index);
          if (x < -30 || x > plotW + 30) continue;

          // Log scale: 2x is a small mark, 16x is a big one. A linear map
          // saturates immediately and makes every outlier the same size.
          const mag = Math.min(1, Math.log2(b.ratio) / 4);
          const radius = minBubbleR + mag * (maxBubbleR - minBubbleR);

          const anchorY = priceToY(b.price);
          if (anchorY < 0 || anchorY > plotH) continue;
          const bubbleY = b.isBull ? anchorY - radius - 6 : anchorY + radius + 6;
          if (bubbleY - radius < 2 || bubbleY + radius > plotH - 2) continue;

          const isTopEvent = b.index === topIdx;
          const fillColor = b.isBull
            ? "rgba(201, 168, 76, 0.42)"
            : "rgba(74, 158, 176, 0.38)";
          const strokeColor = b.isBull
            ? "rgba(233, 208, 130, 0.85)"
            : "rgba(126, 205, 224, 0.85)";

          ctx.strokeStyle = b.isBull
            ? "rgba(201, 168, 76, 0.45)"
            : "rgba(74, 158, 176, 0.45)";
          ctx.lineWidth = 0.8;
          ctx.setLineDash([2, 2]);
          ctx.beginPath();
          ctx.moveTo(x, anchorY);
          ctx.lineTo(x, b.isBull ? bubbleY + radius : bubbleY - radius);
          ctx.stroke();
          ctx.setLineDash([]);

          ctx.beginPath();
          ctx.arc(x, bubbleY, radius, 0, Math.PI * 2);
          ctx.fillStyle = fillColor;
          ctx.fill();
          ctx.strokeStyle = strokeColor;
          ctx.lineWidth = 1.2;
          ctx.stroke();

          if (isTopEvent) {
            ctx.beginPath();
            ctx.arc(x, bubbleY, radius + 3.5, 0, Math.PI * 2);
            ctx.strokeStyle = strokeColor;
            ctx.lineWidth = 0.9;
            ctx.setLineDash([2, 2]);
            ctx.stroke();
            ctx.setLineDash([]);
          }

          // The multiple, not a signed figure. There is no delta in this feed
          // to put a sign on.
          const isHovered =
            s.mouseX >= 0 &&
            Math.abs(s.mouseX - x) < Math.max(radius, barSpacing / 2);
          if ((isTopEvent || isHovered) && radius >= 7) {
            ctx.fillStyle = "#ffffff";
            ctx.font = "bold 8.5px JetBrains Mono, monospace";
            ctx.textAlign = "center";
            ctx.textBaseline = "middle";
            ctx.fillText(`${b.ratio.toFixed(1)}x`, x, bubbleY);
          }
        }
        ctx.restore();
      }

      // --- LAYER 7: Current Price Active Ray ---
      const yCurrent = priceToY(currentPrice);
      const pulse = (Math.sin(s.animTime * 3) + 1) * 0.5;
      ctx.beginPath();
      ctx.moveTo(0, yCurrent);
      ctx.lineTo(plotW, yCurrent);
      ctx.strokeStyle = `rgba(201, 168, 76, ${0.35 + pulse * 0.25})`;
      ctx.lineWidth = 0.9;
      ctx.setLineDash([3, 3]);
      ctx.stroke();
      ctx.setLineDash([]);

      // --- LAYER 8: Time Axis Strip ---
      ctx.save();
      ctx.fillStyle = "rgba(201, 168, 76, 0.35)";
      ctx.font = "8.5px JetBrains Mono, monospace";
      ctx.textAlign = "center";
      const labelEvery = Math.max(Math.floor(plotW / (barSpacing * 6)), 1);

      for (let i = 0; i < count; i += labelEvery) {
        const x = indexToX(i);
        if (x < 15 || x > plotW - 15) continue;
        const d = new Date(candles[i].time * 1000);
        let timeLabel: string;
        if (s.interval === "1d" || s.interval === "1wk") {
          timeLabel = `${d.getMonth() + 1}/${d.getDate()}`;
        } else {
          timeLabel = `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
        }
        ctx.fillText(timeLabel, x, H - 6);
      }
      ctx.restore();

      // --- LAYER 9: Interactive 3-Column L2 DOM Price Ladder on Right Margin ---
      ctx.save();
      const ladderX = plotW;
      const ladderW = rightMargin;

      // Background & border
      ctx.fillStyle = "#080c16";
      ctx.fillRect(ladderX, 0, ladderW, H);
      ctx.strokeStyle = "rgba(255, 255, 255, 0.08)";
      ctx.beginPath();
      ctx.moveTo(ladderX, 0);
      ctx.lineTo(ladderX, H);
      ctx.stroke();

      if (s.showDOM && s.hasVolume) {
        // Table Header
        ctx.fillStyle = "#0d1424";
        ctx.fillRect(ladderX, 0, ladderW, 20);
        ctx.strokeStyle = "rgba(255, 255, 255, 0.08)";
        ctx.beginPath();
        ctx.moveTo(ladderX, 20);
        ctx.lineTo(ladderX + ladderW, 20);
        ctx.stroke();

        ctx.fillStyle = "#94a3b8";
        ctx.font = "bold 8px JetBrains Mono, monospace";
        ctx.textBaseline = "middle";

        const col1W = Math.round(ladderW * 0.33);
        const col2W = Math.round(ladderW * 0.34);

        ctx.textAlign = "right";
        ctx.fillText("EST. BID", ladderX + col1W - 4, 10);
        ctx.textAlign = "center";
        ctx.fillText("PRICE", ladderX + col1W + col2W / 2, 10);
        ctx.textAlign = "left";
        ctx.fillText("EST. ASK", ladderX + col1W + col2W + 4, 10);

        // Say it on the canvas, not only on the toggle.
        //
        // This feed carries no order book. The ladder below is DERIVED from
        // the volume profile - an exponential decay away from last price -
        // and no part of it was quoted by anyone. Labelling the columns
        // "BID VOL"/"ASK VOL" presented a formula as market depth, which is
        // a claim this product cannot support and a subscriber cannot check.
        //
        // The caption is drawn here rather than left to the button label so
        // it survives a screenshot, and so a later tidy-up of the toolbar
        // cannot remove the disclosure while leaving the ladder.
        ctx.save();
        ctx.textAlign = "center";
        ctx.font = "8px JetBrains Mono, monospace";
        ctx.fillStyle = "rgba(245,158,11,0.75)";
        ctx.fillText("MODELLED - NO L2 FEED",
                     ladderX + ladderW / 2, plotH - 4);
        ctx.restore();

        // Price Ladder Rows: Render across visible price domain with proper density
        const numRows = Math.min(30, Math.max(10, Math.floor((plotH - 24) / 16)));
        const priceStep = totalRange / numRows;

        // Baseline max volume for depth bar sizing
        let maxDOMVol = 1;
        for (let i = 0; i < count; i++) {
          if (candles[i].volume > maxDOMVol) maxDOMVol = candles[i].volume;
        }

        for (let r = 0; r <= numRows; r++) {
          const rowPrice = effMinP + r * priceStep;
          const yRow = priceToY(rowPrice);
          if (yRow < 22 || yRow > plotH) continue;

          const isAsk = rowPrice > currentPrice;
          const isCurrent = Math.abs(rowPrice - currentPrice) < priceStep * 0.5;

          // Pseudo-depth derived from volume profile with natural clustering
          const distNorm = Math.abs(rowPrice - currentPrice) / span;
          const depthVol = Math.max(14, Math.round((maxDOMVol / 40) * Math.exp(-distNorm * 2.5) * (1 + (r % 3) * 0.4)));
          const barLen = Math.min(col1W - 6, Math.max(4, (depthVol / (maxDOMVol / 20)) * col1W));

          // Fill opposite cell with cross-session volume so there is NEVER an empty gap
          const crossVol = Math.max(8, Math.round(depthVol * 0.42));

          if (isCurrent) {
            // Mid Market Price Row
            ctx.fillStyle = "rgba(201, 168, 76, 0.22)";
            ctx.fillRect(ladderX + 1, yRow - 7, ladderW - 2, 14);
            ctx.strokeStyle = "rgba(201, 168, 76, 0.6)";
            ctx.lineWidth = 0.8;
            ctx.strokeRect(ladderX + 1, yRow - 7, ladderW - 2, 14);

            ctx.fillStyle = "#fef08a";
            ctx.font = "bold 8.5px JetBrains Mono, monospace";
            ctx.textAlign = "center";
            ctx.fillText(`MID ${currentPrice.toFixed(dec)}`, ladderX + ladderW / 2, yRow);
          } else if (isAsk) {
            // Ask Row
            // Ask Vol Bar & Value
            ctx.fillStyle = "rgba(239, 68, 68, 0.25)";
            ctx.fillRect(ladderX + col1W + col2W + 1, yRow - 5, barLen, 10);

            ctx.fillStyle = "#fca5a5";
            ctx.font = "bold 8px JetBrains Mono, monospace";
            ctx.textAlign = "left";
            ctx.fillText(`${depthVol}`, ladderX + col1W + col2W + 4, yRow);

            // Price Center
            ctx.fillStyle = "#f87171";
            ctx.font = "8px JetBrains Mono, monospace";
            ctx.textAlign = "center";
            ctx.fillText(rowPrice.toFixed(dec), ladderX + col1W + col2W / 2, yRow);

            // Opposite Bid Vol (Filled, Never Empty)
            ctx.fillStyle = "#64748b";
            ctx.textAlign = "right";
            ctx.fillText(`${crossVol}`, ladderX + col1W - 4, yRow);
          } else {
            // Bid Row
            // Bid Vol Bar & Value
            ctx.fillStyle = "rgba(16, 185, 129, 0.25)";
            ctx.fillRect(ladderX + col1W - barLen - 1, yRow - 5, barLen, 10);

            ctx.fillStyle = "#86efac";
            ctx.font = "bold 8px JetBrains Mono, monospace";
            ctx.textAlign = "right";
            ctx.fillText(`${depthVol}`, ladderX + col1W - 4, yRow);

            // Price Center
            ctx.fillStyle = "#34d399";
            ctx.font = "8px JetBrains Mono, monospace";
            ctx.textAlign = "center";
            ctx.fillText(rowPrice.toFixed(dec), ladderX + col1W + col2W / 2, yRow);

            // Opposite Ask Vol (Filled, Never Empty)
            ctx.fillStyle = "#64748b";
            ctx.textAlign = "left";
            ctx.fillText(`${crossVol}`, ladderX + col1W + col2W + 4, yRow);
          }
        }
      } else {
        // Standard Price Scale Axis ticks when DOM is toggled off
        const tickSteps = 8;
        ctx.fillStyle = "#94a3b8";
        ctx.font = "9px JetBrains Mono, monospace";
        ctx.textAlign = "right";
        ctx.textBaseline = "middle";

        for (let i = 0; i <= tickSteps; i++) {
          const y = (plotH / tickSteps) * i;
          const p = yToPrice(y);
          ctx.fillText(p.toFixed(dec), W - 6, y);
        }
      }

      // Current Price Flashing Badge in Right Gutter
      const badgeH = 17;
      ctx.fillStyle = "rgba(201, 168, 76, 0.95)";
      ctx.fillRect(ladderX + 2, yCurrent - badgeH / 2, ladderW - 4, badgeH);
      ctx.fillStyle = "#070a13";
      ctx.font = "bold 9.5px JetBrains Mono, monospace";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(currentPrice.toFixed(dec), ladderX + ladderW / 2, yCurrent);
      ctx.restore();

      // --- LAYER 10: Interactive Crosshairs & HUD ---
      if (s.mouseX >= 0 && !s.isDragging && !s.isDraggingPriceScale) {
        const mx = s.mouseX;
        const my = s.mouseY;

        if (mx > 0 && mx < plotW && my > 0 && my < plotH) {
          ctx.save();
          ctx.setLineDash([3, 3]);
          ctx.strokeStyle = "rgba(201, 168, 76, 0.45)";
          ctx.lineWidth = 0.8;

          // Crosshair lines
          ctx.beginPath();
          ctx.moveTo(mx, 0);
          ctx.lineTo(mx, plotH);
          ctx.stroke();

          ctx.beginPath();
          ctx.moveTo(0, my);
          ctx.lineTo(plotW, my);
          ctx.stroke();
          ctx.setLineDash([]);

          // Crosshair Price Tag
          const crossPrice = yToPrice(my);
          const priceText = crossPrice.toFixed(dec);
          ctx.fillStyle = "rgba(201, 168, 76, 0.95)";
          ctx.fillRect(plotW + 2, my - 8, ladderW - 4, 16);
          ctx.fillStyle = "#070a13";
          ctx.font = "bold 8.5px JetBrains Mono, monospace";
          ctx.textAlign = "center";
          ctx.textBaseline = "middle";
          ctx.fillText(priceText, plotW + ladderW / 2, my);

          // Crosshair Time Tag
          const candleIdx = xToIndex(mx);
          if (candleIdx >= 0 && candleIdx < count) {
            const cd = new Date(candles[candleIdx].time * 1000);
            const timeText = `${cd.toLocaleDateString()} ${String(cd.getHours()).padStart(2, "0")}:${String(cd.getMinutes()).padStart(2, "0")}`;
            ctx.fillStyle = "rgba(201, 168, 76, 0.95)";
            const tw = ctx.measureText(timeText).width + 12;
            ctx.fillRect(mx - tw / 2, plotH + 2, tw, 15);
            ctx.fillStyle = "#070a13";
            ctx.fillText(timeText, mx, plotH + 10);

            // OHLCV Floating Tooltip
            const hc = candles[candleIdx];
            const ohlc = `O: ${hc.open.toFixed(dec)}  H: ${hc.high.toFixed(dec)}  L: ${hc.low.toFixed(dec)}  C: ${hc.close.toFixed(dec)}  VOL: ${Math.round(hc.volume).toLocaleString()}`;
            ctx.fillStyle = "rgba(201, 168, 76, 0.55)";
            ctx.font = "8.5px JetBrains Mono, monospace";
            ctx.textAlign = "left";
            ctx.fillText(ohlc, 12, 16);
          }
          ctx.restore();
        }
      }
    }

    // Interactive Event Handlers
    function onMouseDown(e: MouseEvent) {
      const rect = canvas!.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      const rightMargin = s.showDOM && s.hasVolume ? 160 : 75;
      const plotW = rect.width - rightMargin;
      const isNearPriceScale = mouseX > plotW;

      if (isNearPriceScale) {
        // TradingView price scale vertical drag zoom
        s.isDraggingPriceScale = true;
        s.dragStartPriceY = e.clientY;
        s.initialZoomY = s.zoomY;
        s.autoFit = false;
        setAutoFit(false);
      } else {
        // Pan viewport
        s.isDragging = true;
        s.dragStartX = e.clientX;
        s.dragStartY = e.clientY;
        s.dragStartPanX = s.panX;
        s.dragStartPanY = s.panY;
        s.autoFit = false;
        setAutoFit(false);
      }
    }

    function onMouseMove(e: MouseEvent) {
      const rect = canvas!.getBoundingClientRect();
      s.mouseX = e.clientX - rect.left;
      s.mouseY = e.clientY - rect.top;

      const rightMargin = s.showDOM && s.hasVolume ? 160 : 75;
      const plotW = rect.width - rightMargin;
      const isNearPriceScale = s.mouseX > plotW;

      if (s.isDraggingPriceScale) {
        // Dragging UP expands scale (zoom in), dragging DOWN compresses scale (zoom out)
        const dy = s.dragStartPriceY - e.clientY;
        const factor = Math.exp(dy / 140);
        s.zoomY = Math.max(0.10, Math.min(30.0, s.initialZoomY * factor));
        canvas!.style.cursor = "ns-resize";
      } else if (s.isDragging) {
        s.panX = s.dragStartPanX + (e.clientX - s.dragStartX);
        s.panY = s.dragStartPanY + (e.clientY - s.dragStartY);
        canvas!.style.cursor = "grabbing";
      } else {
        canvas!.style.cursor = isNearPriceScale ? "ns-resize" : "crosshair";
      }
    }

    function onMouseUp() {
      s.isDragging = false;
      s.isDraggingPriceScale = false;
      if (canvas) {
        const rect = canvas.getBoundingClientRect();
        const rightMargin = s.showDOM && s.hasVolume ? 160 : 75;
        const isNearPriceScale = s.mouseX > rect.width - rightMargin;
        canvas.style.cursor = isNearPriceScale ? "ns-resize" : "crosshair";
      }
    }

    function onWheel(e: WheelEvent) {
      e.preventDefault();
      const rect = canvas!.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      const rightMargin = s.showDOM && s.hasVolume ? 160 : 75;
      const isNearPriceScale = mouseX > rect.width - rightMargin;
      const zoomFactor = e.deltaY < 0 ? 1.15 : 0.87;

      s.autoFit = false;
      setAutoFit(false);

      if (e.shiftKey || isNearPriceScale) {
        // Shift+Wheel or over price scale -> Vertical Zoom
        s.zoomY = Math.max(0.10, Math.min(30.0, s.zoomY * zoomFactor));
      } else {
        // Wheel -> Horizontal Bar Spacing Zoom
        s.zoomX = Math.max(0.15, Math.min(10.0, s.zoomX * zoomFactor));
      }
    }

    function onDoubleClick() {
      // Double click resets zoom and pan back to defaults
      s.zoomX = 1.0;
      s.zoomY = 1.0;
      s.panX = 0;
      s.panY = 0;
      s.autoFit = false;
      setAutoFit(false);
    }

    canvas.addEventListener("mousedown", onMouseDown);
    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);
    canvas.addEventListener("wheel", onWheel, { passive: false });
    canvas.addEventListener("dblclick", onDoubleClick);

    function animate() {
      render();
      animId = requestAnimationFrame(animate);
    }
    animId = requestAnimationFrame(animate);

    return () => {
      cancelAnimationFrame(animId);
      canvas.removeEventListener("mousedown", onMouseDown);
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseup", onMouseUp);
      canvas.removeEventListener("wheel", onWheel);
      canvas.removeEventListener("dblclick", onDoubleClick);
    };
  }, []);

  const handleToggleAutoFit = useCallback(() => {
    setAutoFit((prev) => {
      const next = !prev;
      state.current.autoFit = next;
      if (next) {
        state.current.panX = 0;
        state.current.panY = 0;
        state.current.zoomX = 1.0;
        state.current.zoomY = 1.0;
      }
      return next;
    });
  }, []);

  const handleResetZoom = useCallback(() => {
    state.current.zoomX = 1.0;
    state.current.zoomY = 1.0;
    state.current.panX = 0;
    state.current.panY = 0;
    state.current.autoFit = false;
    setAutoFit(false);
  }, []);

  return (
    <div
      className={
        fillContainer
          ? "w-full h-full relative select-none"
          : "w-full relative rounded overflow-hidden border border-border/50 select-none"
      }
      style={{ minHeight: fillContainer ? "400px" : "380px", outline: "none" }}
      tabIndex={0}
    >
      {/* Top HUD Controls Bar */}
      <div className="absolute top-2 left-2 z-20 flex flex-wrap items-center gap-1.5">
        {/* Timeframe Selector */}
        <div className="flex items-center gap-0.5 bg-[#080c16]/90 p-0.5 rounded border border-white/10 backdrop-blur-sm">
          {TIMEFRAMES.map((tf) => (
            <button
              key={tf}
              onClick={() => setLocalInterval(tf)}
              style={{
                padding: "2px 6px",
                borderRadius: 2,
                fontSize: 10,
                fontFamily: "JetBrains Mono, monospace",
                fontWeight: 700,
                cursor: "pointer",
                border:
                  interval === tf
                    ? "1px solid rgba(201,168,76,0.6)"
                    : "1px solid transparent",
                background:
                  interval === tf
                    ? "rgba(201,168,76,0.18)"
                    : "transparent",
                color:
                  interval === tf
                    ? "rgba(229,213,160,1)"
                    : "rgba(201,168,76,0.5)",
                transition: "all 0.15s ease",
              }}
            >
              {tf.toUpperCase()}
            </button>
          ))}
        </div>

        {/* Live Auto-Scroll vs AutoFit Mode */}
        <button
          onClick={handleToggleAutoFit}
          style={{
            padding: "2px 7px",
            borderRadius: 3,
            fontSize: 10,
            fontFamily: "JetBrains Mono, monospace",
            fontWeight: 700,
            cursor: "pointer",
            border: autoFit
              ? "1px solid rgba(56,189,248,0.6)"
              : "1px solid rgba(201,168,76,0.4)",
            background: autoFit
              ? "rgba(56,189,248,0.18)"
              : "rgba(201,168,76,0.15)",
            color: autoFit ? "#38bdf8" : "#e5d5a0",
          }}
          title={autoFit ? "AutoFit Enabled (Click for Live Auto-Scroll)" : "Live Auto-Scroll Enabled (Click to Fit All)"}
        >
          {autoFit ? "FIT" : "LIVE"}
        </button>

        {/* Layer Toggles: Heatmap, Bubbles, DOM */}
        <div className="flex items-center gap-0.5 bg-[#080c16]/90 p-0.5 rounded border border-white/10 backdrop-blur-sm">
          <button
            onClick={() => setShowHeatmap((v) => !v)}
            title={
              hasVolume
                ? "Traded volume at price, from bar data. NOT resting order-book liquidity - this feed has no depth."
                : "This feed publishes no volume, so the profile is built from TIME at price (every bar counts once). Not volume, and not order-book depth."
            }
            style={{
              padding: "2px 6px",
              borderRadius: 2,
              fontSize: 9,
              fontFamily: "JetBrains Mono, monospace",
              fontWeight: 700,
              cursor: "pointer",
              border: showHeatmap
                ? "1px solid rgba(56,189,248,0.6)"
                : "1px solid transparent",
              background: showHeatmap
                ? "rgba(56,189,248,0.15)"
                : "transparent",
              color: showHeatmap ? "#38bdf8" : "rgba(255,255,255,0.4)",
            }}
          >
            {hasVolume ? "VOLUME PROFILE" : "TIME PROFILE"}
          </button>
          <button
            onClick={() => hasVolume && setShowBubbles((v) => !v)}
            disabled={!hasVolume}
            title={
              hasVolume
                ? "Bars whose volume is at least 2x the trailing 30-bar median. Size is the multiple. NOT absorption and NOT delta - this feed has no bid/ask split."
                : "Unavailable: this feed publishes no volume, so there is no relative volume to mark."
            }
            style={{
              padding: "2px 6px",
              borderRadius: 2,
              fontSize: 9,
              fontFamily: "JetBrains Mono, monospace",
              fontWeight: 700,
              cursor: hasVolume ? "pointer" : "not-allowed",
              opacity: hasVolume ? 1 : 0.35,
              border: showBubbles && hasVolume
                ? "1px solid rgba(201,168,76,0.6)"
                : "1px solid transparent",
              background: showBubbles && hasVolume
                ? "rgba(201,168,76,0.15)"
                : "transparent",
              color: showBubbles && hasVolume ? "#e5d5a0" : "rgba(255,255,255,0.4)",
            }}
          >
            BUBBLES
          </button>
          <button
            onClick={() => hasVolume && setShowDOM((v) => !v)}
            disabled={!hasVolume}
            title={
              hasVolume
                ? "Modelled depth. This feed carries no order book - the ladder is derived from the volume profile, not received from an exchange."
                : "Unavailable: the modelled ladder is derived from volume, and this feed publishes none."
            }
            style={{
              padding: "2px 6px",
              borderRadius: 2,
              fontSize: 9,
              fontFamily: "JetBrains Mono, monospace",
              fontWeight: 700,
              cursor: hasVolume ? "pointer" : "not-allowed",
              opacity: hasVolume ? 1 : 0.35,
              border: showDOM && hasVolume
                ? "1px solid rgba(16,185,129,0.6)"
                : "1px solid transparent",
              background: showDOM && hasVolume
                ? "rgba(16,185,129,0.15)"
                : "transparent",
              color: showDOM && hasVolume ? "#34d399" : "rgba(255,255,255,0.4)",
            }}
          >
            DEPTH (MODELLED)
          </button>
        </div>

        {/* Reset Viewport */}
        <button
          onClick={handleResetZoom}
          style={{
            padding: "2px 6px",
            borderRadius: 3,
            fontSize: 9,
            fontFamily: "JetBrains Mono, monospace",
            fontWeight: 700,
            cursor: "pointer",
            border: "1px solid rgba(255,255,255,0.12)",
            background: "rgba(255,255,255,0.05)",
            color: "rgba(255,255,255,0.6)",
          }}
          title="Reset Zoom and Pan (Double-Click Canvas also resets)"
        >
          RESET
        </button>
      </div>

      {loading && (
        <div
          className="absolute inset-0 flex items-center justify-center z-10"
          style={{ background: "rgba(6,11,22,0.85)" }}
        >
          <div
            className="flex items-center gap-2 text-[13px] font-mono"
            style={{ color: "rgba(201,168,76,0.8)" }}
          >
            <span className="h-3 w-3 rounded-full border-2 border-amber-500/30 border-t-amber-500 animate-spin" />
            INITIALIZING ORDER FLOW FEED [{ticker}]...
          </div>
        </div>
      )}

      {feedUnavailable && (
        <div
          className="absolute inset-0 flex flex-col items-center justify-center p-6 text-center z-20 font-mono"
          style={{ background: "rgba(6,11,22,0.95)" }}
        >
          <div className="text-[11px] tracking-widest text-amber-400 border border-amber-500/30 bg-amber-500/10 px-2.5 py-1 mb-2 rounded-sm font-bold">
            FEED UNAVAILABLE
          </div>
          <div className="text-sm font-semibold text-foreground mb-1">{ticker}</div>
          <div className="text-xs text-muted-foreground max-w-md leading-relaxed">
            {feedUnavailable}
          </div>
        </div>
      )}

      <canvas
        ref={canvasRef}
        style={{ width: "100%", height: "100%", display: "block" }}
      />
    </div>
  );
}
