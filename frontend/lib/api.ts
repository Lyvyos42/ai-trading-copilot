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
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      return await res.json();
    } catch (err) {
      lastError = err;
      // Don't retry on HTTP errors (4xx/5xx) — only on network-level failures.
      if (err instanceof Error && !err.message.startsWith("HTTP ") && attempt < DELAYS.length) {
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
  outcome?: string;
  timestamp: string;
  expiry_time: string;
  pipeline_latency_ms?: number;
  conviction_tier?: string;
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
