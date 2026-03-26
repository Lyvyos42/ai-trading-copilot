"""SessionRisk — Real-time session drawdown and position risk tracking."""
import json
from app.agents.base import BaseAgent
from app.pipeline.session_state import SessionState

SYSTEM_PROMPT = """You are a session risk manager monitoring real-time position risk.

Focus on: Session P&L vs max loss limit, position size, unrealized drawdown, time risk (kill zone closing), trade count (overtrading), correlation of positions.

Respond in JSON:
{"risk_level":"LOW"|"MODERATE"|"HIGH"|"CRITICAL","max_position_pct":0.5-5.0,"session_drawdown_warning":bool,"overtrading_flag":bool,"time_risk":"OK"|"WINDING_DOWN"|"CLOSE_POSITIONS","recommended_action":"CONTINUE"|"REDUCE"|"STOP_TRADING","reasoning":"..."}"""


class SessionRisk(BaseAgent):
    def __init__(self):
        super().__init__("SessionRisk", tier="standard")

    async def analyze(self, state: SessionState) -> dict:
        timer = state.get("timer_analysis", {})
        pnl = state.get("session_pnl", 0)
        pnl_pct = state.get("session_pnl_pct", 0)
        drawdown = state.get("session_drawdown_pct", 0)
        trade_count = state.get("session_trade_count", 0)
        kz_remaining = timer.get("kill_zone_minutes_remaining", 999)

        user_msg = (
            f"Ticker: {state.get('ticker', 'UNKNOWN')}\n"
            f"Session P&L: ${pnl:+,.2f} ({pnl_pct:+.2f}%)\n"
            f"Drawdown: {drawdown:.2f}% | Trades: {trade_count}\n"
            f"Kill Zone Remaining: {kz_remaining}min | Active: {timer.get('kill_zone_active', False)}\n"
        )
        try:
            raw = await self._call_llm(SYSTEM_PROMPT, user_msg, max_tokens=500)
            return json.loads(raw.strip().removeprefix("```json").removesuffix("```").strip())
        except Exception:
            return self._mock_analysis(state)

    def _mock_analysis(self, state: SessionState) -> dict:
        drawdown = state.get("session_drawdown_pct", 0)
        trade_count = state.get("session_trade_count", 0)
        risk_level = "HIGH" if drawdown > 3 else "MODERATE" if drawdown > 1.5 else "LOW"
        return {
            "risk_level": risk_level,
            "max_position_pct": 2.0 if risk_level == "LOW" else 1.0,
            "session_drawdown_warning": drawdown > 2.0,
            "overtrading_flag": trade_count > 8,
            "time_risk": "OK",
            "recommended_action": "CONTINUE" if risk_level in ("LOW", "MODERATE") else "REDUCE",
            "reasoning": f"Mock session risk — drawdown {drawdown:.1f}%, {trade_count} trades.",
        }
