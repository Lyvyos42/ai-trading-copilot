import { supabase } from "./supabase";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";

export { API_URL, WS_URL };

async function getToken(): Promise<string | null> {
  // Prefer live Supabase session (handles refresh automatically)
  try {
    const { data: { session } } = await supabase.auth.getSession();
    if (session?.access_token) return session.access_token;
  } catch {}
  // Fallback: manually stored token (demo user / legacy)
  return typeof window !== "undefined" ? localStorage.getItem("token") : null;
}

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const token = await getToken();
  const reqOptions: RequestInit = {
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options?.headers,
    },
    ...options,
  };

  // Exponential backoff — 3 retries on network errors (handles Render cold-start).
  // Delays: 2s → 6s → 18s. Total max wait ~26s vs the old 50s single retry.
  const DELAYS = [2_000, 6_000, 18_000];
  let lastError: unknown;
  for (let attempt = 0; attempt <= DELAYS.length; attempt++) {
    try {
      const res = await fetch(`${API_URL}${path}`, reqOptions);
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Request failed" }));
        const msg = err.detail || `HTTP ${res.status}`;
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
      throw err;
    }
  }
  throw lastError;
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
  direction: "LONG" | "SHORT";
  entry_price: number;
  stop_loss: number;
  take_profit_1: number;
  take_profit_2: number;
  take_profit_3: number;
  confidence_score: number;
  agent_votes: Record<string, AgentVote | boolean | null>;
  reasoning_chain: string[];
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
  analytical_window?: string | null;
  bull_case?: string | null;
  bear_case?: string | null;
  conviction_tier?: string | null;
  timestamp: string;
  expiry_time: string;
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
  return apiFetch<Signal>(`/api/v1/signals/${signalId}/outcome`, {
    method: "PATCH",
    body: JSON.stringify({ outcome }),
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
  accuracy_7d: number;
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
  position_size_pct: number;
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
  return publicFetch("/api/v1/performance/summary");
}

export async function getEquityCurve(): Promise<{ curve: EquityCurvePoint[] }> {
  return publicFetch("/api/v1/performance/equity-curve");
}

export async function getByAssetClass(): Promise<{ asset_classes: AssetClassPerformance[] }> {
  return publicFetch("/api/v1/performance/by-asset-class");
}

export async function getByAgent(): Promise<{ agents: AgentPerformance[] }> {
  return publicFetch("/api/v1/performance/by-agent");
}

export async function getCalibration(): Promise<{ calibration: CalibrationBucket[] }> {
  return publicFetch("/api/v1/performance/calibration");
}

export async function getMonthlyReturns(): Promise<{ months: MonthlyReturn[] }> {
  return publicFetch("/api/v1/performance/monthly");
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
  matrix: number[][];
  period_days: number;
  data_points: number;
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
