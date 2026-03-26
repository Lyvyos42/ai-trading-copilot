"""SessionCoach — Psychological monitoring, tilt detection, behavioral coaching."""
import json
from app.agents.base import BaseAgent
from app.pipeline.session_state import SessionState

SYSTEM_PROMPT = """You are a trading psychology coach monitoring a live trading session.

Detect: Revenge trading, overtrading, FOMO, hesitation, position escalation, off-hours trading.
Reinforce: Good discipline, proper sizing, plan adherence.

Be direct but supportive. Max 2-3 sentences. No fluff.

Respond in JSON:
{"tilt_detected":bool,"tilt_type":"REVENGE"|"FOMO"|"OVERTRADING"|"HESITATION"|"ESCALATION"|"OFF_HOURS"|"NONE","tilt_severity":0-10,"message":"...","recommendation":"CONTINUE"|"PAUSE_5MIN"|"REDUCE_SIZE"|"END_SESSION","positive_note":"..."|null}"""


class SessionCoach(BaseAgent):
    def __init__(self):
        super().__init__("SessionCoach", tier="lightweight")

    async def analyze(self, state: SessionState) -> dict:
        timer = state.get("timer_analysis", {})
        trade_count = state.get("session_trade_count", 0)
        pnl = state.get("session_pnl", 0)
        pnl_pct = state.get("session_pnl_pct", 0)
        drawdown = state.get("session_drawdown_pct", 0)
        trades = state.get("session_trades", [])
        elapsed = timer.get("session_elapsed_minutes", 0)
        kz_active = timer.get("kill_zone_active", False)

        recent_trades = trades[-5:] if trades else []
        trade_summary = ""
        for t in recent_trades:
            trade_summary += f"  {t.get('direction','?')} {t.get('ticker','?')} -> {t.get('result','?')} ({t.get('pnl', 0):+.2f})\n"

        user_msg = (
            f"Session Duration: {elapsed}min | Kill Zone Active: {kz_active}\n"
            f"Trades: {trade_count} | P&L: ${pnl:+,.2f} ({pnl_pct:+.2f}%) | Drawdown: {drawdown:.2f}%\n"
            f"\nRecent trades:\n{trade_summary or '  No trades yet.'}\n"
        )
        try:
            raw = await self._call_llm(SYSTEM_PROMPT, user_msg, max_tokens=400)
            return json.loads(raw.strip().removeprefix("```json").removesuffix("```").strip())
        except Exception:
            return self._mock_coaching(state)

    def _mock_coaching(self, state: SessionState) -> dict:
        trade_count = state.get("session_trade_count", 0)
        drawdown = state.get("session_drawdown_pct", 0)
        kz_active = state.get("timer_analysis", {}).get("kill_zone_active", False)

        tilt, severity, message = "NONE", 0, "Session looking good. Stay disciplined."
        recommendation, positive = "CONTINUE", None

        if trade_count > 8:
            tilt, severity = "OVERTRADING", 6
            message = f"{trade_count} trades this session. Slow down — quality over quantity."
            recommendation = "PAUSE_5MIN"
        elif drawdown > 3:
            tilt, severity = "REVENGE", 7
            message = f"Down {drawdown:.1f}% — don't chase it back. Take a break."
            recommendation = "REDUCE_SIZE"
        elif not kz_active:
            tilt, severity = "OFF_HOURS", 4
            message = "No kill zone active. Low-probability environment."
            recommendation = "PAUSE_5MIN"
        elif trade_count == 0:
            positive = "Patience is a position. Wait for the setup."

        return {
            "tilt_detected": tilt != "NONE", "tilt_type": tilt, "tilt_severity": severity,
            "message": message, "recommendation": recommendation, "positive_note": positive,
        }
