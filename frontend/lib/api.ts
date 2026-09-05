import { supabase } from "./supabase";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";

export { API_URL, WS_URL };

/** localStorage token, if any. The fallback for every getToken failure path. */
function storedToken(): string | null {
  try {
    return typeof window !== "undefined" ? localStorage.getItem("token") : null;
  } catch {
    return null;
  }
}

export async function getToken(): Promise<string | null> {
  // Prefer live Supabase session (handles refresh automatically).
  //
  // Raced against a timeout because getSession() is NOT reliably quick. It
  // takes a navigator.locks lock, so concurrent tabs serialise on it, and when
  // the stored session has expired it makes a network call to refresh. Either
  // can hang - and this runs BEFORE apiFetch's retry loop, so a hang here
  // stalls the request with no error, no retry and no timeout, which from the
  // outside is indistinguishable from a dead endpoint. 8s is far longer than a
  // healthy refresh needs; past that, fall through to the stored token.
  try {
    const session = await Promise.race([
      supabase.auth.getSession().then(r => r.data.session),
      new Promise<null>(resolve => setTimeout(() => resolve(null), 8_000)),
    ]);
    if (session?.access_token) return session.access_token;
  } catch {}
  // Fallback: manually stored token (demo user / legacy)
  return storedToken();
}

/** Turn an opaque fetch TypeError into a message that names a cause.
 *
 *  "Failed to fetch" is the browser's single word for offline, DNS failure,
 *  TLS failure, a blocked request, a CORS rejection and a killed connection.
 *  It names none of them, so it reads like a broken endpoint - which cost two
 *  rounds of investigating a server that was answering in 0.3s the whole time.
 */
function networkErrorMessage(path: string, err: unknown, delays: number[],
                            triedProxy = false): string {
  const detail = err instanceof Error ? err.message : String(err);
  const tries = delays.length + 1;
  const secs = Math.round(delays.reduce((a, b) => a + b, 0) / 1000);

  if (typeof navigator !== "undefined" && navigator.onLine === false) {
    return "You are offline - the browser reports no network connection.";
  }
  if (API_URL.startsWith("http://localhost")) {
    return `NEXT_PUBLIC_API_URL is not set on this deployment, so the page is `
         + `calling ${API_URL}. Set it in the Vercel environment and redeploy.`;
  }

  let host = API_URL;
  try { host = new URL(API_URL).host; } catch {}
  return `Cannot reach ${host}${path} - ${tries} attempt${tries === 1 ? "" : "s"} over ~${secs}s, no reply`
       + (triedProxy ? ", including a same-origin retry through this site itself" : "")
       + `. The API answers from outside the browser, so this is local: a blocking `
       + `extension (adblocker / privacy shield), a VPN or proxy, or DNS. [${detail}]`;
}

export async function apiFetch<T>(
  path: string,
  options?: RequestInit,
  opts?: { delays?: number[]; viaProxy?: boolean },
): Promise<T> {
  const token = await getToken();
  const reqOptions: RequestInit = {
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options?.headers,
    },
    ...options,
  };

  // Exponential backoff on network errors, sized to outlast a Render cold start.
  // Render's own free-tier banner says a spun-down instance "can delay requests
  // by 50 seconds or more" - and the previous budget was 2+6+18 = 26s, so it
  // gave up BEFORE the server could possibly answer. That surfaced as
  // "Failed to fetch", which reads like a broken endpoint rather than a
  // sleeping one. 2+5+12+25+30 = 74s now covers it.
  //
  // Overridable, so a caller that has a working fallback can fail fast and use
  // it rather than making the user sit through the full cold-start budget for
  // an attempt it already expects to lose. See resetSignals.
  const DELAYS = opts?.delays ?? [2_000, 5_000, 12_000, 25_000, 30_000];
  // `base` is normally the API's own origin. When a cross-origin request has
  // already failed at the network layer, the caller retries through
  // `/api/be` - this app's own origin - which Next forwards server-side.
  // See app/api/be/[...path]/route.ts for the measurements behind it.
  const base = opts?.viaProxy ? "/api/be" : API_URL;
  let lastError: unknown;
  for (let attempt = 0; attempt <= DELAYS.length; attempt++) {
    try {
      // A hung connection had no timeout at all, so it could sit forever and
      // consume the whole retry budget without ever producing an error.
      const res = await fetch(`${base}${path}`, {
        ...reqOptions,
        signal: (reqOptions as any).signal ?? AbortSignal.timeout(45_000),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Request failed" }));
        let msg = err.detail || `HTTP ${res.status}`;
        // This page can be browsed signed-out, but writes cannot be done
        // signed-out. Say which it is rather than repeating the bare detail.
        if (res.status === 401) msg = `${msg} - sign in again, your session has expired.`;
        // Tag HTTP errors so we can distinguish from network failures
        const httpErr = new Error(msg);
        (httpErr as any)._httpStatus = res.status;
        throw httpErr;
      }
      return await res.json();
    } catch (err) {
      lastError = err;
      // Only retry on network-level failures (no _httpStatus), not on HTTP 4xx/5xx
      const isHttpError = (err as any)?._httpStatus != null;
      if (!isHttpError && err instanceof Error && attempt < DELAYS.length) {
        await new Promise(r => setTimeout(r, DELAYS[attempt]));
        continue;
      }
      // Every retry is spent, and the request never reached the server.
      //
      // If this was a cross-origin WRITE, try once more through our own
      // origin. Reads were succeeding at the same moment writes were being
      // dropped, which is what a privacy extension or endpoint-security web
      // shield does to cross-origin state-changing requests. The proxy makes
      // the request same-origin, so there is nothing for it to object to.
      if (!isHttpError) {
        const method = (reqOptions.method || "GET").toUpperCase();
        if (!opts?.viaProxy && method !== "GET" && method !== "HEAD") {
          return apiFetch<T>(path, options, { ...opts, viaProxy: true });
        }
        throw new Error(networkErrorMessage(path, err, DELAYS, !!opts?.viaProxy));
      }
      throw err;
    }
  }
  throw lastError;
}

/** Clear the caller's signals. Tries DELETE, falls back to POST.
 *
 *  Measured 2026-09-05, from the browser that was failing: GET to this host
 *  succeeded and populated the panel, while DELETE to the same host failed six
 *  times over 74s with a bare "Failed to fetch". From outside that browser the
 *  endpoint answers a browser-shaped DELETE in 0.30s and its preflight returns
 *  200 with DELETE in allow-methods - so nothing between here and the server
 *  objects to the verb. Something in the client does: security-suite web
 *  shields, corporate proxies and some content blockers pass GET and POST and
 *  drop DELETE.
 *
 *  The DELETE gets ONE fast attempt rather than the full cold-start budget,
 *  because when it is being filtered locally no amount of waiting helps, and
 *  74s of waiting before trying the thing that works is just a slower failure.
 *  An HTTP answer - 401, 500, anything - means the request did arrive, so it
 *  is reported as-is rather than retried under a different verb.
 */
export async function resetSignals(): Promise<{ deleted: number }> {
  try {
    return await apiFetch<{ deleted: number }>(
      "/api/v1/signals/reset", { method: "DELETE" }, { delays: [1_500] },
    );
  } catch (err) {
    if ((err as any)?._httpStatus != null) throw err;
    // DELETE-blocking is real, so POST is tried next; apiFetch will itself
    // fall back to the same-origin proxy if that is also dropped.
    return await apiFetch<{ deleted: number }>("/api/v1/signals/reset", { method: "POST" });
  }
}

/** Fire-and-forget: ping the backend health endpoint to wake Render from sleep.
 *  Call on page mount so the backend is warm before the user clicks anything. */
export function wakeBackend(): void {
  fetch(`${API_URL}/health`, { method: "GET" }).catch(() => {});
}

// ─── Signals ──────────────────────────────────────────────────────────────────

export interface TimeframeLevels {
  entry: number;
  stop_loss: number;
  take_profit_1: number;
  take_profit_2: number;
  take_profit_3?: number;
  atr: number;
  risk_pct: number;
  label: string;
}

export interface AgentVote {
  direction?: string;
  confidence?: number;
  bullish_contribution?: number;
  bearish_contribution?: number;
}

export interface Signal {
  signal_id: string;
  ticker: string;
  asset_class: string;
  direction: "LONG" | "SHORT" | "NEUTRAL";
  entry_price?: number | null;
  current_price?: number | null;
  stop_loss?: number | null;
  take_profit_1?: number | null;
  take_profit_2?: number | null;
  take_profit_3?: number | null;
  confidence_score: number;
  agent_votes: Record<string, AgentVote | boolean | null>;
  reasoning_chain: string[];
  status_reasons?: string[];
  timeframe: string;
  strategy_sources: string[];
  timeframe_levels?: { scalp?: TimeframeLevels; swing?: TimeframeLevels };
  status: string;
  outcome?: string | null;
  exit_price?: number | null;
  resolved_at?: string | null;
  pnl_pct?: number | null;
  // Probability model fields
  probability_score?: number | null;
  bullish_pct?: number | null;
  bearish_pct?: number | null;
  research_target?: number | null;
  invalidation_level?: number | null;
  risk_reward_ratio?: number | null;
  position_size_pct?: number | null;
  analytical_window?: string | null;
  bull_case?: string | null;
  bear_case?: string | null;
  conviction_tier?: string | null;
  timestamp: string;
  expiry_time: string;
  signal_mode?: string | null;
  pipeline_latency_ms?: number;
  agent_detail?: Record<string, unknown>;
}

function inferAssetClass(ticker: string): string {
  const u = ticker.toUpperCase();
  if (u.endsWith("-USD") || ["BTC","ETH","SOL","BNB","XRP","ADA","DOGE","AVAX","DOT","LINK","UNI","MATIC","ATOM","LTC","BCH","SHIB","PEPE","WIF","OP","ARB","SUI","NEAR","APT"].some(c => u.startsWith(c))) return "crypto";
  if (["XAUUSD","XAGUSD","XPTUSD","XPDUSD","HG=F"].includes(u)) return "commodities";
  if (u.endsWith("=X") || /^(EUR|GBP|USD|AUD|NZD|CAD|CHF|JPY|NOK|SEK|DKK|SGD|HKD|CNH|INR|BRL|KRW|TRY|ZAR|MXN|PLN|HUF|CZK|THB)/.test(u)) return "fx";
  if (["US500","US100","US30","US2000","UK100","GER40","FRA40","JPN225","HK50","AUS200","ESP35","ITA40","STOXX50","SPX","NDX","DJIA","DAX","CAC40"].includes(u)) return "indices";
  if (["USOIL","UKOIL","NATGAS","RBOB","HEATOIL","CL=F","RB=F","HO=F","NG=F"].includes(u)) return "commodities";
  if (["CORN","WHEAT","SOYBEAN","COFFEE","SUGAR","COTTON","COCOA"].includes(u)) return "commodities";
  if (u.endsWith("=F")) return "futures";
  return "stocks";
}

export async function generateSignal(ticker: string, assetClass?: string, timeframe = "1D", profile = "balanced"): Promise<Signal> {
  return apiFetch<Signal>("/api/v1/signals/generate", {
    method: "POST",
    body: JSON.stringify({ ticker, asset_class: assetClass ?? inferAssetClass(ticker), timeframe, profile }),
  });
}

export async function getSignal(id: string): Promise<Signal> {
  return apiFetch<Signal>(`/api/v1/signals/${id}`);
}

export async function listSignals(limit = 20): Promise<Signal[]> {
  return apiFetch<Signal[]>(`/api/v1/signals?limit=${limit}`);
}

// ─── Portfolio ────────────────────────────────────────────────────────────────

export interface Position {
  id: string;
  ticker: string;
  direction: "LONG" | "SHORT";
  entry_price: number;
  current_price: number;
  quantity: number;
  unrealized_pnl: number;
  unrealized_pnl_pct: number;
  status: string;
  opened_at: string;
  is_paper: boolean;
}

export interface PortfolioSummary {
  open_positions: number;
  total_trades: number;
  win_rate_pct: number;
  total_realized_pnl: number;
  equity: number;
  paper_mode: boolean;
}

export async function getPositions(): Promise<Position[]> {
  return apiFetch<Position[]>("/api/v1/portfolio/positions");
}

export async function getPortfolioSummary(): Promise<PortfolioSummary> {
  return apiFetch<PortfolioSummary>("/api/v1/portfolio/summary");
}

export async function resolveSignal(signalId: string, outcome: "WIN" | "LOSS"): Promise<Signal> {
  if (!signalId) throw new Error("Invalid signal ID");
  return apiFetch<Signal>(`/api/v1/signals/${signalId}/outcome`, {
    method: "PATCH",
    body: JSON.stringify({ outcome }),
  });
}

export interface ScanResult {
  signal_id: string;
  ticker: string;
  direction: "LONG" | "SHORT" | "NEUTRAL";
  confidence_score: number;
  entry_price: number;
  stop_loss: number;
  signal_mode: string;
  confluence_score: number;
  summary: string;
  timestamp: string;
}

export async function scanNow(
  symbols?: string[],
  replaceActive = true,
  profile = "balanced"
): Promise<{ symbols_scanned: number; signals_generated: number; signals: ScanResult[] }> {
  return apiFetch("/api/v1/scanner/scan-now", {
    method: "POST",
    body: JSON.stringify({
      symbols: symbols || [],
      replace_active: replaceActive,
      profile,
    }),
  });
}


export async function executePosition(signalId: string, quantity = 1): Promise<{ id: string }> {
  return apiFetch("/api/v1/portfolio/execute", {
    method: "POST",
    body: JSON.stringify({ signal_id: signalId, quantity, is_paper: true }),
  });
}

export async function closePosition(positionId: string): Promise<unknown> {
  return apiFetch(`/api/v1/portfolio/close/${positionId}`, { method: "POST" });
}

// ─── Agents ───────────────────────────────────────────────────────────────────

export interface AgentStatus {
  name: string;
  role: string;
  model: string;
  tier?: string;
  stage?: string;
  strategies: string[];
  status: string;
  avg_latency_ms: number;
  signals_today: number;
  accuracy_7d: number | null;
  /** How many resolved signals that accuracy is computed from. 0 = unmeasured. */
  accuracy_sample?: number;
  last_active: string;
}

export async function getAgentStatus(): Promise<{ agents: AgentStatus[]; all_healthy: boolean }> {
  return apiFetch("/api/v1/agents/status");
}

// ─── Profiles ────────────────────────────────────────────────────────────────

export interface StrategyProfile {
  name: string;
  slug: string;
  description: string;
  weights: Record<string, number>;
  is_default: boolean;
  default_timeframe: string;
  recommended_chart: string;
}

export async function listProfiles(): Promise<StrategyProfile[]> {
  const res = await apiFetch<{ profiles: StrategyProfile[] }>("/api/v1/profiles");
  return res.profiles;
}

export async function getActiveProfile(): Promise<StrategyProfile> {
  const res = await apiFetch<{ profile: StrategyProfile }>("/api/v1/profiles/active");
  return res.profile;
}

export async function setActiveProfile(profile: string): Promise<StrategyProfile> {
  const res = await apiFetch<{ profile: StrategyProfile }>("/api/v1/profiles/active", {
    method: "PUT",
    body: JSON.stringify({ profile }),
  });
  return res.profile;
}

// ─── Backtest ─────────────────────────────────────────────────────────────────

export async function runBacktest(strategy: string, ticker: string, period: string) {
  return apiFetch(`/api/v1/backtest/${strategy}?ticker=${ticker}&period=${period}`);
}

export async function listStrategies() {
  return apiFetch<{ strategies: { name: string; ref: string; description: string }[] }>("/api/v1/backtest");
}

// ─── Debate ───────────────────────────────────────────────────────────────────

export async function triggerDebate(ticker: string, assetClass = "stocks") {
  return apiFetch("/api/v1/debate/trigger", {
    method: "POST",
    body: JSON.stringify({ ticker, asset_class: assetClass }),
  });
}

// ─── Auth ─────────────────────────────────────────────────────────────────────

export async function login(email: string, password: string): Promise<{ access_token: string; tier: string }> {
  // Demo user → use legacy backend token (avoids needing demo user in Supabase)
  if (email === "demo@tradingcopilot.ai") {
    const form = new URLSearchParams({ username: email, password });
    const res = await fetch(`${API_URL}/api/v1/auth/token`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: form.toString(),
    });
    if (!res.ok) throw new Error("Invalid credentials");
    const data = await res.json();
    localStorage.setItem("token", data.access_token);
    return data;
  }

  // All other users → Supabase
  const { data, error } = await supabase.auth.signInWithPassword({ email, password });
  if (error) throw new Error(error.message);
  const token = data.session!.access_token;
  localStorage.setItem("token", token);
  return { access_token: token, tier: "free" };
}

export async function register(email: string, password: string): Promise<{ access_token?: string; tier: string }> {
  const { data, error } = await supabase.auth.signUp({ email, password });
  if (error) throw new Error(error.message);
  // signUp may return session immediately or require email confirmation
  if (data.session) {
    localStorage.setItem("token", data.session.access_token);
    return { access_token: data.session.access_token, tier: "free" };
  }
  // Email confirmation required — no session yet
  return { tier: "free" };
}

export async function loginWithGoogle(): Promise<void> {
  const { error } = await supabase.auth.signInWithOAuth({
    provider: "google",
    options: { redirectTo: `${typeof window !== "undefined" ? window.location.origin : ""}/auth/callback` },
  });
  if (error) throw new Error(error.message);
}

export async function logout(): Promise<void> {
  await supabase.auth.signOut();
  localStorage.removeItem("token");
  localStorage.removeItem("dashboard_ticker");
}

export async function getMe() {
  return apiFetch<{ id: string; email: string; tier: string }>("/api/v1/auth/me");
}

// ─── Session Mode ─────────────────────────────────────────────────────────────

export interface SessionSignal {
  direction: string;
  confidence: number;
  entry: number;
  stop_loss: number;
  take_profit_1: number;
  take_profit_2: number;
  position_size_pct?: number | null;
  trade_type: string;
  urgency: string;
  agent_agreement: number;
  reasoning: string;
  risk_reward_ratio: number;
  ticker: string;
  mode: string;
  strategy_profile: string;
  kill_zone: string;
  kill_zone_active: boolean;
  kill_zone_minutes_remaining: number;
  market_phase: string;
  risk_gate_passed: boolean;
  risk_gate_mode: string;
  risk_gate_rules: { rule: number; name: string; reason: string }[];
  coach: {
    tilt_detected: boolean;
    tilt_type: string;
    tilt_severity: number;
    message: string;
    recommendation: string;
    positive_note: string | null;
  };
  session_risk: {
    risk_level: string;
    recommended_action: string;
  };
  agent_votes: { agent: string; direction: string; confidence: number }[];
  reasoning_chain: string[];
  pipeline_latency_ms: number;
  timestamp: string;
}

export interface SessionStatus {
  active: boolean;
  session_id?: string;
  ticker?: string;
  profile?: string;
  started_at?: string;
  analysis_count?: number;
  trade_count?: number;
  pnl?: number;
  pnl_pct?: number;
}

export async function startSession(ticker: string, profile: string = "balanced") {
  return apiFetch("/api/v1/session/start", {
    method: "POST",
    body: JSON.stringify({ ticker, profile }),
  });
}

export async function runSessionAnalysis(ticker?: string) {
  return apiFetch("/api/v1/session/analyze", {
    method: "POST",
    body: JSON.stringify({ ticker }),
  }) as Promise<SessionSignal>;
}

export async function getSessionStatus(): Promise<SessionStatus> {
  return apiFetch("/api/v1/session/status");
}

export async function stopSession() {
  return apiFetch("/api/v1/session/stop", { method: "POST" });
}

// ─── Performance (Public) ─────────────────────────────────────────────────────

export interface PerformanceSummary {
  total_signals: number;
  resolved_signals: number;
  active_signals: number;
  expired_signals: number;
  wins: number;
  losses: number;
  win_rate_pct: number;
  avg_confidence: number;
  avg_pnl_pct: number;
}

export interface EquityCurvePoint {
  date: string;
  pnl_pct: number;
  cumulative_pnl_pct: number;
}

export interface AssetClassPerformance {
  asset_class: string;
  total: number;
  wins: number;
  win_rate_pct: number;
  avg_pnl_pct: number;
  avg_confidence: number;
}

export interface AgentPerformance {
  agent: string;
  total_signals: number;
  correct_calls: number;
  accuracy_pct: number;
  avg_confidence: number;
}

export interface CalibrationBucket {
  confidence_range: string;
  confidence_midpoint: number;
  total: number;
  wins: number;
  actual_win_rate_pct: number;
}

export interface MonthlyReturn {
  month: string;
  total_pnl_pct: number;
  signal_count: number;
  wins: number;
  losses: number;
  win_rate_pct: number;
}

async function publicFetch<T>(path: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Request failed" }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function getPerformanceSummary(): Promise<PerformanceSummary> {
  return apiFetch("/api/v1/performance/summary");
}

export async function getEquityCurve(): Promise<{ curve: EquityCurvePoint[] }> {
  return apiFetch("/api/v1/performance/equity-curve");
}

export async function getByAssetClass(): Promise<{ asset_classes: AssetClassPerformance[] }> {
  return apiFetch("/api/v1/performance/by-asset-class");
}

export async function getByAgent(): Promise<{ agents: AgentPerformance[] }> {
  return apiFetch("/api/v1/performance/by-agent");
}

export async function getCalibration(): Promise<{ calibration: CalibrationBucket[] }> {
  return apiFetch("/api/v1/performance/calibration");
}

export async function getMonthlyReturns(): Promise<{ months: MonthlyReturn[] }> {
  return apiFetch("/api/v1/performance/monthly");
}

// ─── Evaluation ───────────────────────────────────────────────────────────────

export async function evaluateSignals() {
  return apiFetch("/api/v1/signals/evaluate", { method: "POST" });
}

// ─── Journal ──────────────────────────────────────────────────────────────────

export async function getJournalSignals(params: {
  limit?: number;
  offset?: number;
  ticker?: string;
  outcome?: string;
  asset_class?: string;
  min_confidence?: number;
  max_confidence?: number;
}): Promise<Signal[]> {
  const searchParams = new URLSearchParams();
  if (params.limit) searchParams.set("limit", String(params.limit));
  if (params.offset) searchParams.set("offset", String(params.offset));
  if (params.ticker) searchParams.set("ticker", params.ticker);
  if (params.outcome) searchParams.set("outcome", params.outcome);
  if (params.asset_class) searchParams.set("asset_class", params.asset_class);
  if (params.min_confidence) searchParams.set("min_confidence", String(params.min_confidence));
  if (params.max_confidence) searchParams.set("max_confidence", String(params.max_confidence));
  return apiFetch(`/api/v1/signals/journal?${searchParams.toString()}`);
}

// ─── Economic Calendar ────────────────────────────────────────────────────────

export interface CalendarEvent {
  date: string;
  time: string;
  name: string;
  country: string;
  impact: "HIGH" | "MEDIUM" | "LOW";
  category: string;
  previous: string | null;
  forecast: string | null;
  actual: string | null;
}

export async function getCalendarEvents(weeks = 2): Promise<{ events: CalendarEvent[]; start: string; end: string }> {
  return publicFetch(`/api/v1/calendar/events?weeks=${weeks}`);
}

// ─── Correlation Map ──────────────────────────────────────────────────────────

export interface CorrelationMatrix {
  tickers: string[];
  matrix: (number | null)[][];
  period_days: number;
  data_points: number;
  error?: string;
  detail?: string;
}

export interface CorrelationPair {
  t1: string;
  t2: string;
  series: { date: string; v1: number; v2: number }[];
  correlation: number;
}

export async function getCorrelationMatrix(tickers?: string[], period = 90): Promise<CorrelationMatrix> {
  const params = new URLSearchParams({ period: String(period) });
  if (tickers?.length) params.set("tickers", tickers.join(","));
  return publicFetch(`/api/v1/correlations/matrix?${params.toString()}`);
}

export async function getCorrelationPair(t1: string, t2: string, period = 90): Promise<CorrelationPair> {
  return publicFetch(`/api/v1/correlations/pair?t1=${t1}&t2=${t2}&period=${period}`);
}

// ─── Memory Layer ────────────────────────────────────────────────────────────

export interface Memory {
  memory: string;
  type: string;
  importance: string;
  created_at: string;
  relevance_score?: number;
}

export interface MemoryStats {
  memory_count: number;
  interaction_count: number;
  correction_count: number;
  status: string;
}

export interface AgentCorrectionItem {
  id: string;
  agent_name: string;
  correction_type: string;
  lesson: string;
  ticker: string | null;
  created_at: string | null;
}

export interface UserPreferences {
  favorite_tickers: string[];
  favorite_asset_classes: string[];
  avg_risk_tolerance: number | null;
  preferred_timeframe: string | null;
  preferred_direction: string | null;
  signal_count: number;
  win_rate: number | null;
  avg_confidence_pref: number | null;
  last_computed: string | null;
}

export async function trackEvent(eventType: string, ticker?: string, signalId?: string, payload?: Record<string, unknown>): Promise<void> {
  apiFetch("/api/v1/memory/track", {
    method: "POST",
    body: JSON.stringify({ event_type: eventType, ticker, signal_id: signalId, payload }),
  }).catch(() => {}); // fire-and-forget
}

export async function sendSignalFeedback(signalId: string, feedback: "THUMBS_UP" | "THUMBS_DOWN", ticker?: string, note?: string): Promise<void> {
  await apiFetch("/api/v1/memory/feedback", {
    method: "POST",
    body: JSON.stringify({ signal_id: signalId, feedback, ticker, note }),
  });
}

export async function getMemories(): Promise<{ memories: Memory[]; total: number }> {
  return apiFetch("/api/v1/memory/memories");
}

export async function deleteMemory(memoryId: string): Promise<void> {
  await apiFetch(`/api/v1/memory/${memoryId}`, { method: "DELETE" });
}

export async function getMemoryPreferences(): Promise<{ preferences: UserPreferences | null }> {
  return apiFetch("/api/v1/memory/preferences");
}

export async function getAgentCorrections(limit = 50): Promise<{ corrections: AgentCorrectionItem[] }> {
  return apiFetch(`/api/v1/memory/corrections?limit=${limit}`);
}

export async function getAgentCorrectionsByName(agentName: string): Promise<{ corrections: AgentCorrectionItem[] }> {
  return apiFetch(`/api/v1/memory/corrections/${agentName}`);
}

export async function getMemoryStats(): Promise<MemoryStats> {
  return apiFetch("/api/v1/memory/stats");
}

// ─── Billing ─────────────────────────────────────────────────────────────────

export async function createCheckout(tier: string): Promise<{ checkout_url: string; session_id: string }> {
  return apiFetch("/api/v1/billing/checkout", {
    method: "POST",
    body: JSON.stringify({
      tier,
      success_url: `${typeof window !== "undefined" ? window.location.origin : ""}/dashboard?checkout=success`,
      cancel_url: `${typeof window !== "undefined" ? window.location.origin : ""}/pricing?checkout=cancelled`,
    }),
  });
}

export async function createPortal(): Promise<{ portal_url: string }> {
  return apiFetch("/api/v1/billing/portal", { method: "POST" });
}

export async function getBillingStatus(): Promise<{ tier: string; has_billing: boolean; stripe_customer_id: string | null }> {
  return apiFetch("/api/v1/billing/status");
}
