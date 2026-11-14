/**
 * Strategy Truth Lab + Live Terminal — API contract and client.
 *
 * This file is the single source of truth for the shapes the two pages
 * consume. Today every call is answered by mock route handlers under
 * `app/api/mock/...` (see lib/mock). The future FastAPI backend implements
 * the same shapes under `/api/v1/...`:
 *
 *   POST /api/v1/lab/parse                  LabParseRequest  -> LabParseResponse
 *   POST /api/v1/lab/run                    LabRunRequest    -> LabRunResponse
 *   GET  /api/v1/lab/{id}                   -> LabJobResponse
 *   GET  /api/v1/lab/library                -> LabLibraryResponse (addition, see docs)
 *   GET  /api/v1/terminal/noise-bands       ?symbol=USTEC|US500 -> NoiseBandsResponse
 *   GET  /api/v1/terminal/activity-windows  -> ActivityWindowsResponse
 *   GET  /api/v1/terminal/signals           -> SignalsResponse
 *   GET  /api/v1/terminal/positioning       -> PositioningResponse
 *   GET  /api/v1/terminal/odds              -> OddsResponse
 *   GET  /api/v1/terminal/calendar          -> CalendarResponse   (addition, see docs)
 *
 * To switch from mocks to the backend set NEXT_PUBLIC_TERMINAL_API_BASE to
 * the backend prefix (for example "/api/be/api/v1" to go through the
 * same-origin proxy). Nothing else changes.
 *
 * What the product is, so the contract stays honest:
 *  - the tests are rule-based Python. A language model only turns the
 *    trader's words into rules, and the trader confirms them before a run;
 *  - a verdict is a measured result, failures included. No field here is a
 *    forecast of direction or profit.
 */

// ─── Shared ──────────────────────────────────────────────────────────────────

/** Every response says whether it came from a mock, so the UI can label it. */
export interface Provenance {
  /** true while the frontend mock answers; the backend sends false. */
  is_mock: boolean;
  /** Where the numbers come from, in words. */
  source: string;
  /** ISO 8601 timestamp of the snapshot. */
  as_of: string;
}

// ─── Truth Lab ───────────────────────────────────────────────────────────────

export type VerdictLabel = "PASS" | "NEAR MISS" | "FAILED" | "REAL BUT NOT TRADABLE";

export const VERDICT_LABELS: VerdictLabel[] = ["PASS", "NEAR MISS", "REAL BUT NOT TRADABLE", "FAILED"];

/** One rule, as the parser understood it. The trader may edit `text`. */
export interface LabRule {
  id: string;
  text: string;
}

export interface LabParseRequest {
  /** The strategy in the trader's own words. */
  text: string;
}

export interface LabParseResponse {
  /** A short name for the strategy. */
  name: string;
  /** The exact rules that would be tested. Shown for confirmation. */
  rules: LabRule[];
  /** Anything the parser had to assume because the text did not say. */
  assumptions: string[];
}

export interface LabRunRequest {
  /** The rules exactly as the trader confirmed them. */
  rules: LabRule[];
  /** Optional: the original wording and name, stored with the result. */
  asked?: string;
  name?: string;
}

export interface LabRunResponse {
  job_id: string;
}

export type LabStageKey = "freeze" | "select" | "sealed" | "luck" | "direction";
export type LabStageState = "pending" | "running" | "done";

export interface LabStage {
  key: LabStageKey;
  state: LabStageState;
}

/** The measured result of one sealed test. Mirrors the lab's own record. */
export interface LabVerdict {
  id: string;
  name: string;
  /** The trader's wording. */
  asked: string;
  /** The rules that were tested. */
  rules: string[];
  verdict: VerdictLabel;
  symbols: string;
  period: string;
  /** The key measured numbers, in one line (pips, R or % per trade). */
  headline: string;
  /** Plain-English reason for the verdict. */
  why: string;
  trades_per_day?: number;
  /** Result per calendar year, in `years_unit`. */
  years?: Record<string, number>;
  years_unit?: string;
}

/**
 * queued | running : the test is in progress, see `stages`
 * done             : `verdict` is set
 * unavailable      : this deployment cannot test these rules (the mock
 *                    answers this for anything outside its six stored results)
 * error            : the run failed, see `message`
 */
export type LabJobStatus = "queued" | "running" | "done" | "unavailable" | "error";

export interface LabJobResponse {
  job_id: string;
  status: LabJobStatus;
  stages: LabStage[];
  verdict: LabVerdict | null;
  message?: string;
}

export interface LabLibraryResponse extends Provenance {
  examples: LabVerdict[];
}

// ─── Live Terminal: noise-area bands ─────────────────────────────────────────

export type TerminalSymbol = "USTEC" | "US500";
export const TERMINAL_SYMBOLS: TerminalSymbol[] = ["USTEC", "US500"];

export interface NoiseBandPoint {
  /** Minutes after the 09:30 New York open, 0..390. */
  minute: number;
  /** open * (1 + avg |move from open| at this minute, last 14 sessions) */
  upper: number;
  /** open * (1 - the same average) */
  lower: number;
  /** Last price of the minute; null for minutes that have not happened yet. */
  price: number | null;
  /** Session VWAP; null for minutes that have not happened yet. */
  vwap: number | null;
}

export type PositionState = "LONG" | "SHORT" | "FLAT";

export interface NoiseBandEvent {
  minute: number;
  kind: "ENTRY_LONG" | "ENTRY_SHORT" | "EXIT_STOP" | "EXIT_CLOSE";
  price: number;
}

export interface NoiseBandsResponse extends Provenance {
  symbol: TerminalSymbol;
  /** Session open price (09:30 New York). */
  open: number;
  /** Sessions in the band average. */
  lookback_days: number;
  /** The current minute after the open. */
  now_minute: number;
  points: NoiseBandPoint[];
  events: NoiseBandEvent[];
  state: {
    position: PositionState;
    /** Minute of the entry, when in a position. */
    since_minute: number | null;
    entry: number | null;
    /** Trailing stop: the band or VWAP, whichever is tighter. */
    stop: number | null;
    stop_basis: "BAND" | "VWAP" | null;
    /** Next HH:00 / HH:30 check, as a minute after the open; null after the last one. */
    next_check_minute: number | null;
    /** Always 390 (16:00 New York). */
    flat_minute: number;
  };
}

// ─── Live Terminal: big-move windows ─────────────────────────────────────────

export type ActivityLevel = "QUIET" | "NORMAL" | "ELEVATED" | "HIGH";

export interface ActivitySlot {
  /** New York wall time, "HH:MM", start of a 30-minute slot. */
  start: string;
  level: ActivityLevel;
  /** Expected range in the slot relative to a normal slot (1.0 = normal). */
  range_ratio: number;
}

export interface ActivityWindow {
  start: string;
  end: string;
  level: Exclude<ActivityLevel, "QUIET" | "NORMAL">;
  /** Why a larger move is likely: a release, an open, a close. */
  reason: string;
  /** Markets it applies to. */
  scope: string;
}

/** Timing only. There is deliberately no direction field. */
export interface ActivityWindowsResponse extends Provenance {
  horizon_hours: number;
  slots: ActivitySlot[];
  windows: ActivityWindow[];
}

// ─── Live Terminal: validated signals ────────────────────────────────────────

export interface SignalRecord {
  id: string;
  name: string;
  symbol: string;
  timeframe: string;
  /** The sealed-test verdict that put it on the terminal. */
  verdict: VerdictLabel;
  /** Deep link id into the Truth Lab library, when the test is published. */
  lab_example_id: string | null;
  state: "LONG" | "SHORT" | "FLAT" | "WAITING" | "ARMED";
  state_note: string;
  /** Unit of every result figure below, e.g. "pips" or "%". */
  unit: string;
  /** Average result per signal in the sealed test, with its period. */
  tested_avg: number;
  tested_period: string;
  live: {
    since: string;
    signals: number;
    winners: number;
    avg: number;
    total: number;
    /** Result of each closed signal, oldest first. */
    results: number[];
  };
}

export interface SignalsResponse extends Provenance {
  signals: SignalRecord[];
}

// ─── Live Terminal: crypto crowd positioning ─────────────────────────────────

export interface PositioningRow {
  symbol: "BTC" | "ETH";
  /** Share of accounts that are net long, 0..100. */
  long_pct: number;
  /** long accounts / short accounts */
  ratio: number;
  /** z-score of the ratio against the last 90 days. */
  z: number;
  /** |z| >= threshold is an extreme. */
  extreme: "LONG" | "SHORT" | null;
  /** Daily z-score, last 90 days, oldest first. */
  z_history: number[];
}

export interface PositioningResponse extends Provenance {
  threshold: number;
  rows: PositioningRow[];
}

// ─── Live Terminal: prediction-market odds ───────────────────────────────────

export interface OddsRow {
  id: string;
  category: "FED" | "MACRO" | "GEO";
  question: string;
  /** Market-implied probability, 0..100. */
  probability: number;
  /** Change over 7 days, in percentage points. */
  change_7d: number;
  venue: string;
}

/** Information only. Odds are market prices, not forecasts by this app. */
export interface OddsResponse extends Provenance {
  rows: OddsRow[];
}

// ─── Live Terminal: economic calendar ────────────────────────────────────────

export interface CalendarEvent {
  id: string;
  /** New York wall time, "HH:MM". */
  time: string;
  currency: string;
  title: string;
  impact: "LOW" | "MED" | "HIGH";
  actual: string | null;
  forecast: string | null;
  previous: string | null;
  status: "DONE" | "NEXT" | "LATER";
}

export interface CalendarResponse extends Provenance {
  events: CalendarEvent[];
}

// ─── Client ──────────────────────────────────────────────────────────────────

const BASE = (process.env.NEXT_PUBLIC_TERMINAL_API_BASE || "/api/mock").replace(/\/$/, "");

export class TerminalApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "TerminalApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    cache: "no-store",
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      if (body && typeof body.detail === "string") detail = body.detail;
    } catch {
      /* body was not JSON; keep the status text */
    }
    throw new TerminalApiError(res.status, detail);
  }
  return (await res.json()) as T;
}

export const terminalApi = {
  lab: {
    parse: (body: LabParseRequest) =>
      request<LabParseResponse>("/lab/parse", { method: "POST", body: JSON.stringify(body) }),
    run: (body: LabRunRequest) =>
      request<LabRunResponse>("/lab/run", { method: "POST", body: JSON.stringify(body) }),
    job: (id: string) => request<LabJobResponse>(`/lab/${encodeURIComponent(id)}`),
    library: () => request<LabLibraryResponse>("/lab/library"),
  },
  terminal: {
    noiseBands: (symbol: TerminalSymbol) =>
      request<NoiseBandsResponse>(`/terminal/noise-bands?symbol=${symbol}`),
    activityWindows: () => request<ActivityWindowsResponse>("/terminal/activity-windows"),
    signals: () => request<SignalsResponse>("/terminal/signals"),
    positioning: () => request<PositioningResponse>("/terminal/positioning"),
    odds: () => request<OddsResponse>("/terminal/odds"),
    calendar: () => request<CalendarResponse>("/terminal/calendar"),
  },
};

// ─── Small shared helpers ────────────────────────────────────────────────────

/** Minutes after 09:30 New York -> "HH:MM". */
export function minuteToClock(minute: number): string {
  const total = 9 * 60 + 30 + minute;
  const h = Math.floor(total / 60);
  const m = total % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}
