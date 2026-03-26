"""SessionTrader — Session-context synthesis agent (Opus tier)."""
import json
import hashlib
from app.agents.base import BaseAgent
from app.pipeline.session_state import SessionState

BASE_SYSTEM_PROMPT = """You are the Session Trader for QuantNeuralEdge. You synthesize
real-time session analysis from 5 specialist agents into actionable intraday trade decisions.

You operate in KILL ZONE windows where institutional order flow is highest.

Input agents: SessionTechnical, SessionSentiment, SessionOrderFlow, SessionCorrelation, SessionRisk.

Rules:
- If SessionRisk says STOP_TRADING → direction must be NEUTRAL
- If kill zone closing (< 10 min) → tighten stops, no new entries
- If 3+ agents disagree on direction → NEUTRAL with reasoning
- Entry must be within 0.3% of current price
- Always provide SCALP levels — no swing levels in session mode

Respond in JSON:
{"direction":"LONG"|"SHORT"|"NEUTRAL","confidence":0-100,"entry":float,"stop_loss":float,"take_profit_1":float,"take_profit_2":float,"position_size_pct":0.5-3.0,"trade_type":"SCALP"|"INTRADAY"|"NO_TRADE","urgency":"EXECUTE_NOW"|"WAIT_FOR_LEVEL"|"NO_TRADE","agent_agreement":0-5,"reasoning":"...","risk_reward_ratio":float}"""


class SessionTrader(BaseAgent):
    def __init__(self):
        super().__init__("SessionTrader", tier="premium")

    def _build_system_prompt(self, profile_slug: str) -> str:
        try:
            from app.profiles.manager import profile_manager
            profile = profile_manager.get_profile(profile_slug)
            if profile.prompt_block:
                return f"{BASE_SYSTEM_PROMPT}\n\n=== STRATEGY PROFILE: {profile.name.upper()} ===\n{profile.prompt_block}"
        except Exception:
            pass
        return BASE_SYSTEM_PROMPT

    async def analyze(self, state: SessionState) -> dict:
        timer = state.get("timer_analysis", {})
        tech = state.get("session_technical", {})
        sent = state.get("session_sentiment", {})
        flow = state.get("session_order_flow", {})
        corr = state.get("session_correlation", {})
        risk = state.get("session_risk", {})
        market = state.get("market_data", {})
        profile = state.get("strategy_profile", "balanced")

        user_msg = (
            f"=== SESSION CONTEXT ===\n"
            f"Ticker: {state.get('ticker', 'UNKNOWN')}\n"
            f"Kill Zone: {timer.get('kill_zone', 'NONE')} ({timer.get('kill_zone_minutes_remaining', '?')}min)\n"
            f"Session P&L: {state.get('session_pnl_pct', 0):+.2f}% | Trades: {state.get('session_trade_count', 0)}\n"
            f"Price: {market.get('close', 'N/A')} | ATR: {market.get('atr', 'N/A')}\n"
            f"\n=== TECHNICAL ===\n{json.dumps(tech, indent=1, default=str)}\n"
            f"\n=== SENTIMENT ===\n{json.dumps(sent, indent=1, default=str)}\n"
            f"\n=== ORDER FLOW ===\n{json.dumps(flow, indent=1, default=str)}\n"
            f"\n=== CORRELATION ===\n{json.dumps(corr, indent=1, default=str)}\n"
            f"\n=== SESSION RISK ===\n{json.dumps(risk, indent=1, default=str)}\n"
        )

        try:
            raw = await self._call_llm(self._build_system_prompt(profile), user_msg, max_tokens=1200)
            data = json.loads(raw.strip().removeprefix("```json").removesuffix("```").strip())
            price = market.get("close", 0)
            entry = data.get("entry", price)
            if price and abs(entry - price) / price > 0.003:
                data["entry"] = price
            return data
        except Exception:
            return self._mock_signal(state)

    def _mock_signal(self, state: SessionState) -> dict:
        ticker = state.get("ticker", "X")
        seed = int(hashlib.md5(f"{ticker}_session_trader".encode()).hexdigest()[:8], 16)
        price = state.get("market_data", {}).get("close", 100)
        atr = state.get("market_data", {}).get("atr", price * 0.01)
        direction = ["LONG", "SHORT", "NEUTRAL"][seed % 3]
        sl = round(price - atr * 0.8, 2) if direction == "LONG" else round(price + atr * 0.8, 2)
        tp1 = round(price + atr * 1.0, 2) if direction == "LONG" else round(price - atr * 1.0, 2)
        tp2 = round(price + atr * 1.8, 2) if direction == "LONG" else round(price - atr * 1.8, 2)
        return {
            "direction": direction, "confidence": 40 + (seed % 35), "entry": price,
            "stop_loss": sl, "take_profit_1": tp1, "take_profit_2": tp2,
            "position_size_pct": 1.5, "trade_type": "SCALP" if direction != "NEUTRAL" else "NO_TRADE",
            "urgency": "WAIT_FOR_LEVEL" if direction != "NEUTRAL" else "NO_TRADE",
            "agent_agreement": 3, "reasoning": f"Mock session signal for {ticker}.",
            "risk_reward_ratio": 1.8,
        }
