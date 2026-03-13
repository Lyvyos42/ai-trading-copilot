const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";

export { API_URL, WS_URL };

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
  const res = await fetch(`${API_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options?.headers,
    },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Request failed" }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

// ─── Signals ──────────────────────────────────────────────────────────────────

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
  agent_votes: Record<string, { direction?: string; confidence?: number } | boolean>;
  reasoning_chain: string[];
  strategy_sources: string[];
  status: string;
  timestamp: string;
  expiry_time: string;
  pipeline_latency_ms?: number;
  agent_detail?: Record<string, unknown>;
}

export async function generateSignal(ticker: string, assetClass = "stocks", timeframe = "1D"): Promise<Signal> {
  return apiFetch<Signal>("/api/v1/signals/generate", {
    method: "POST",
    body: JSON.stringify({ ticker, asset_class: assetClass, timeframe }),
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

export async function executePosition(signalId: string, quantity = 1): Promise<{ id: string }> {
  return apiFetch("/api/v1/portfolio/execute", {
    method: "POST",
    body: JSON.stringify({ signal_id: signalId, quantity, is_paper: true }),
  });
}

// ─── Agents ───────────────────────────────────────────────────────────────────

export interface AgentStatus {
  name: string;
  role: string;
  model: string;
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
  const form = new URLSearchParams({ username: email, password });
  const res = await fetch(`${API_URL}/api/v1/auth/token`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: form.toString(),
  });
  if (!res.ok) throw new Error("Invalid credentials");
  return res.json();
}

export async function register(email: string, password: string) {
  return apiFetch("/api/v1/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export async function getMe() {
  return apiFetch<{ id: string; email: string; tier: string }>("/api/v1/auth/me");
}
