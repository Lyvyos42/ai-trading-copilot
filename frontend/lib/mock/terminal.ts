/**
 * MOCK — Live Terminal data.
 *
 * EVERYTHING in this file is invented for layout and interaction work. None
 * of it is market data, a live record or a real quote. Each response carries
 * `is_mock: true` and the pages label themselves "DEMO DATA".
 *
 * The series are generated from fixed seeds, so the server render, the
 * client render and every screenshot agree.
 *
 * The mock session is frozen at 13:40 New York (minute 250 after the open).
 */
import type {
  ActivityWindowsResponse,
  CalendarResponse,
  NoiseBandEvent,
  NoiseBandPoint,
  NoiseBandsResponse,
  OddsResponse,
  PositioningResponse,
  PositioningRow,
  Provenance,
  SignalsResponse,
  TerminalSymbol,
} from "@/lib/terminal-api";

export const MOCK_NOW_MINUTE = 250; // 13:40 New York
export const MOCK_NOW_CLOCK = "13:40";

const PROVENANCE: Provenance = {
  is_mock: true,
  source: "frontend mock (lib/mock/terminal.ts)",
  as_of: "2026-11-13T18:40:00Z",
};

/** Small deterministic PRNG (mulberry32). */
function rng(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Standard normal from two uniforms. */
function gauss(r: () => number): number {
  const u = Math.max(r(), 1e-9);
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * r());
}

function lerpPath(path: [number, number][], m: number): number {
  for (let i = 1; i < path.length; i++) {
    if (m <= path[i][0]) {
      const [m0, v0] = path[i - 1];
      const [m1, v1] = path[i];
      return v0 + ((m - m0) / (m1 - m0)) * (v1 - v0);
    }
  }
  return path[path.length - 1][1];
}

interface NoiseConfig {
  open: number;
  decimals: number;
  /** Average |move from open| at the close, as a fraction. */
  scale: number;
  seed: number;
  jitter: number;
  /** MOCK intraday path, as fraction-from-open at given minutes. */
  path: [number, number][];
}

const NOISE: Record<TerminalSymbol, NoiseConfig> = {
  // Breaks the upper band before the 11:00 check and holds: a LONG day.
  USTEC: {
    open: 24186.5,
    decimals: 1,
    scale: 0.0092,
    seed: 20261113,
    jitter: 0.00012,
    path: [
      [0, 0], [25, 0.0012], [45, -0.0008], [62, 0.001], [80, 0.0036], [90, 0.0056],
      [100, 0.0064], [120, 0.0068], [150, 0.0079], [175, 0.0075], [205, 0.0091],
      [230, 0.0098], [250, 0.0106],
    ],
  },
  // Pokes above the band at 12:14, between checks, and falls back: a FLAT day.
  US500: {
    open: 6712.25,
    decimals: 2,
    scale: 0.0064,
    seed: 7120501,
    jitter: 0.00007,
    path: [
      [0, 0], [30, -0.0011], [60, 0.0004], [90, 0.0016], [110, 0.0012], [135, 0.0024],
      [158, 0.004], [164, 0.0046], [170, 0.0041], [180, 0.0028], [200, 0.0019],
      [230, 0.0028], [250, 0.0024],
    ],
  },
};

function round(v: number, d: number): number {
  const f = 10 ** d;
  return Math.round(v * f) / f;
}

/**
 * MOCK noise-area session. The band, price and VWAP are invented; the
 * position state is then derived from them with the real rule set, so the
 * panel is at least internally consistent:
 *   - checks at HH:00 / HH:30 only; long above the upper band, short below
 *     the lower band;
 *   - stop = the band or VWAP, whichever is tighter; flat at 16:00.
 */
export function mockNoiseBands(symbol: TerminalSymbol): NoiseBandsResponse {
  const cfg = NOISE[symbol];
  const r = rng(cfg.seed);
  const points: NoiseBandPoint[] = [];
  const events: NoiseBandEvent[] = [];

  let dev = 0;
  let pv = 0;
  let vol = 0;
  let position: "LONG" | "SHORT" | "FLAT" = "FLAT";
  let since: number | null = null;
  let entry: number | null = null;
  let stop: number | null = null;
  let basis: "BAND" | "VWAP" | null = null;

  for (let m = 0; m <= 390; m++) {
    const wobble = 1 + 0.06 * Math.sin(m / 23) + 0.04 * Math.sin(m / 7.3);
    const sigma = cfg.scale * Math.sqrt(m / 390) * wobble;
    const upper = round(cfg.open * (1 + sigma), cfg.decimals);
    const lower = round(cfg.open * (1 - sigma), cfg.decimals);

    if (m > MOCK_NOW_MINUTE) {
      points.push({ minute: m, upper, lower, price: null, vwap: null });
      continue;
    }

    dev = m === 0 ? 0 : 0.9 * dev + cfg.jitter * gauss(r);
    const price = round(cfg.open * (1 + lerpPath(cfg.path, m) + dev), cfg.decimals);
    const w = 1 + 1.6 * Math.exp(-m / 28); // heavier volume near the open
    pv += price * w;
    vol += w;
    const vwap = round(pv / vol, cfg.decimals);
    points.push({ minute: m, upper, lower, price, vwap });

    if (position === "LONG") {
      basis = vwap > upper ? "VWAP" : "BAND";
      stop = Math.max(upper, vwap);
      if (price < stop) {
        events.push({ minute: m, kind: "EXIT_STOP", price });
        position = "FLAT";
        since = null;
        entry = null;
        stop = null;
        basis = null;
      }
    } else if (position === "SHORT") {
      basis = vwap < lower ? "VWAP" : "BAND";
      stop = Math.min(lower, vwap);
      if (price > stop) {
        events.push({ minute: m, kind: "EXIT_STOP", price });
        position = "FLAT";
        since = null;
        entry = null;
        stop = null;
        basis = null;
      }
    }

    if (position === "FLAT" && m > 0 && m < 390 && m % 30 === 0) {
      if (price > upper) {
        position = "LONG";
        since = m;
        entry = price;
        stop = Math.max(upper, vwap);
        basis = vwap > upper ? "VWAP" : "BAND";
        events.push({ minute: m, kind: "ENTRY_LONG", price });
      } else if (price < lower) {
        position = "SHORT";
        since = m;
        entry = price;
        stop = Math.min(lower, vwap);
        basis = vwap < lower ? "VWAP" : "BAND";
        events.push({ minute: m, kind: "ENTRY_SHORT", price });
      }
    }
  }

  const next = Math.ceil((MOCK_NOW_MINUTE + 1) / 30) * 30;
  return {
    ...PROVENANCE,
    symbol,
    open: cfg.open,
    lookback_days: 14,
    now_minute: MOCK_NOW_MINUTE,
    points,
    events,
    state: {
      position,
      since_minute: since,
      entry,
      stop,
      stop_basis: basis,
      next_check_minute: next < 390 ? next : null,
      flat_minute: 390,
    },
  };
}

/** MOCK: the next 8 hours in 30-minute slots, from 13:30 New York. */
export function mockActivityWindows(): ActivityWindowsResponse {
  const ratios: [string, number][] = [
    ["13:30", 0.8], ["14:00", 2.3], ["14:30", 1.6], ["15:00", 1.0],
    ["15:30", 1.5], ["16:00", 1.2], ["16:30", 0.6], ["17:00", 0.4],
    ["17:30", 0.4], ["18:00", 0.7], ["18:30", 0.5], ["19:00", 1.1],
    ["19:30", 1.5], ["20:00", 1.2], ["20:30", 0.8], ["21:00", 0.6],
  ];
  return {
    ...PROVENANCE,
    horizon_hours: 8,
    slots: ratios.map(([start, range_ratio]) => ({
      start,
      range_ratio,
      level: range_ratio >= 2 ? "HIGH" : range_ratio >= 1.4 ? "ELEVATED" : range_ratio >= 0.7 ? "NORMAL" : "QUIET",
    })),
    windows: [
      { start: "14:00", end: "15:00", level: "HIGH", reason: "FOMC minutes release", scope: "Indices, gold, USD pairs" },
      { start: "15:30", end: "16:00", level: "ELEVATED", reason: "US cash close, closing auction", scope: "USTEC, US500" },
      { start: "19:30", end: "20:00", level: "ELEVATED", reason: "Tokyo open, Japan trade data", scope: "JPY pairs" },
    ],
  };
}

/** MOCK: three signals with invented live records. Not real track records. */
export function mockSignals(): SignalsResponse {
  return {
    ...PROVENANCE,
    signals: [
      {
        id: "gold-breakout-h4",
        name: "Gold breakout",
        symbol: "XAUUSD",
        timeframe: "H4",
        verdict: "PASS",
        lab_example_id: null,
        state: "WAITING",
        state_note: "No H4 close beyond the 20-bar range.",
        unit: "pips",
        tested_avg: 36,
        tested_period: "2022-2026",
        live: { since: "2026-11-07", signals: 4, winners: 2, avg: 31, total: 124, results: [142, -68, -55, 105] },
      },
      {
        id: "sp-overnight-dip",
        name: "S&P overnight dip",
        symbol: "US500",
        timeframe: "D1",
        verdict: "PASS",
        lab_example_id: null,
        state: "ARMED",
        state_note: "Entry at the 16:00 close if today's dip rule holds.",
        unit: "%",
        tested_avg: 0.11,
        tested_period: "2015-2026",
        live: { since: "2026-11-08", signals: 3, winners: 2, avg: 0.09, total: 0.27, results: [0.31, -0.22, 0.18] },
      },
      {
        id: "ustec-noise-area",
        name: "Noise-area momentum",
        symbol: "USTEC",
        timeframe: "M1",
        verdict: "PASS",
        lab_example_id: "noise-area-ustec",
        state: "LONG",
        state_note: "Long since the 11:00 check. Stop trails the band.",
        unit: "%",
        tested_avg: 0.049,
        tested_period: "2025",
        live: { since: "2026-11-10", signals: 4, winners: 3, avg: 0.12, total: 0.48, results: [0.41, -0.28, 0.13, 0.22] },
      },
    ],
  };
}

/** MOCK: crowd positioning. z history is a seeded walk ending at today's z. */
export function mockPositioning(): PositioningResponse {
  const build = (symbol: "BTC" | "ETH", long_pct: number, z: number, seed: number): PositioningRow => {
    const r = rng(seed);
    const hist: number[] = [];
    let v = -0.4;
    for (let i = 0; i < 90; i++) {
      v = 0.93 * v + 0.33 * gauss(r);
      hist.push(v);
    }
    // bend the last three weeks toward today's reading
    for (let i = 0; i < 21; i++) {
      const k = (i + 1) / 21;
      const idx = 69 + i;
      hist[idx] = hist[idx] * (1 - k) + z * k + (i < 20 ? 0.12 * gauss(r) : 0);
    }
    return {
      symbol,
      long_pct,
      ratio: Math.round((long_pct / (100 - long_pct)) * 100) / 100,
      z,
      extreme: z >= 1.5 ? "LONG" : z <= -1.5 ? "SHORT" : null,
      z_history: hist.map((x) => Math.round(x * 100) / 100),
    };
  };
  return {
    ...PROVENANCE,
    threshold: 1.5,
    rows: [build("BTC", 71.8, 1.92, 4411), build("ETH", 63.2, 0.58, 9082)],
  };
}

/** MOCK: prediction-market odds. Invented quotes. */
export function mockOdds(): OddsResponse {
  return {
    ...PROVENANCE,
    rows: [
      { id: "fed-dec-cut", category: "FED", question: "Fed cuts rates at the December meeting", probability: 62, change_7d: 4, venue: "Polymarket" },
      { id: "fed-q1-two", category: "FED", question: "Two or more Fed cuts by end of March", probability: 38, change_7d: -3, venue: "Kalshi" },
      { id: "us-recession-27", category: "MACRO", question: "US recession declared before 2028", probability: 24, change_7d: 1, venue: "Kalshi" },
      { id: "cpi-above-3", category: "MACRO", question: "US CPI above 3.0 % in the next print", probability: 41, change_7d: 6, venue: "Kalshi" },
      { id: "geo-ceasefire", category: "GEO", question: "Ukraine ceasefire agreed before July", probability: 29, change_7d: -2, venue: "Polymarket" },
      { id: "geo-oil-90", category: "GEO", question: "Brent crude above $90 before year end", probability: 9, change_7d: 0, venue: "Polymarket" },
    ],
  };
}

/** MOCK: today's calendar, New York time. Invented figures. */
export function mockCalendar(): CalendarResponse {
  return {
    ...PROVENANCE,
    events: [
      { id: "c1", time: "08:30", currency: "USD", title: "Retail sales m/m", impact: "HIGH", actual: "0.4 %", forecast: "0.3 %", previous: "0.1 %", status: "DONE" },
      { id: "c2", time: "10:00", currency: "USD", title: "Business inventories", impact: "LOW", actual: "0.2 %", forecast: "0.2 %", previous: "0.3 %", status: "DONE" },
      { id: "c3", time: "10:30", currency: "USD", title: "Crude oil inventories", impact: "MED", actual: "-1.8M", forecast: "0.9M", previous: "2.4M", status: "DONE" },
      { id: "c4", time: "14:00", currency: "USD", title: "FOMC minutes", impact: "HIGH", actual: null, forecast: null, previous: null, status: "NEXT" },
      { id: "c5", time: "16:30", currency: "USD", title: "API crude stocks", impact: "LOW", actual: null, forecast: null, previous: "1.1M", status: "LATER" },
      { id: "c6", time: "19:50", currency: "JPY", title: "Trade balance", impact: "MED", actual: null, forecast: "-0.31T", previous: "-0.23T", status: "LATER" },
    ],
  };
}
