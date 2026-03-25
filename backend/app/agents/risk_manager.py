import json
import random
from app.agents.base import BaseAgent
from app.pipeline.state import TradingState


SYSTEM_PROMPT = """You are a quantitative risk manager enforcing strict portfolio constraints
from "151 Trading Strategies" (strategy 3.18 covariance framework):

Constraints:
- Max portfolio drawdown: 15% (circuit breaker)
- Max position size: 5% of equity (Kelly criterion half-Kelly)
- Max sector concentration: 30%
- New position correlation < 0.7 with existing holdings
- Target portfolio volatility: 10% annualized (strategy 6.5)
- Dollar neutrality for stat-arb positions

Respond ONLY with a valid JSON object:
{
  "approved": <bool>,
  "position_size_pct": <float 0-5>,
  "kelly_fraction": <float>,
  "stop_loss_adjustment": <float>,
  "portfolio_drawdown": <float 0-100>,
  "sector_concentration": <float 0-100>,
  "correlation_check": <float -1 to 1>,
  "vol_scalar": <float>,
  "warnings": [<string>, ...],
  "reasoning": "<string>"
}"""


def kelly_criterion(win_prob: float, reward_risk_ratio: float) -> float:
    """Kelly fraction f* = (p*b - q) / b where b = reward/risk, p = P(win), q = 1-p"""
    q = 1 - win_prob
    b = reward_risk_ratio
    if b <= 0:
        return 0.0
    return max(0, (win_prob * b - q) / b)


class RiskManager(BaseAgent):
    def __init__(self):
        super().__init__("RiskManager", tier="standard")

    async def analyze(self, state: TradingState) -> dict:
        ticker = state.get("ticker", "UNKNOWN")
        tech = state.get("technical_analysis", {})
        fund = state.get("fundamental_analysis", {})

        # Aggregate confidence from analysts
        confidences = [
            state.get("fundamental_analysis", {}).get("confidence", 50),
            state.get("technical_analysis", {}).get("confidence", 50),
            state.get("sentiment_analysis", {}).get("confidence", 50),
            state.get("macro_analysis", {}).get("confidence", 50),
        ]
        avg_confidence = sum(confidences) / len(confidences)
        win_prob = avg_confidence / 100

        entry = tech.get("support", 100) * 1.01 if tech else 100
        stop = tech.get("support", 95)
        tp1 = tech.get("resistance", 110)
        reward_risk = (tp1 - entry) / max(entry - stop, 0.01)

        kelly = kelly_criterion(win_prob, reward_risk)
        half_kelly = kelly / 2
        position_size = round(min(5.0, half_kelly * 100), 2)

        user_msg = f"""Validate risk for {ticker}.
Analyst confidence: {avg_confidence:.1f}%
Kelly fraction: {kelly:.3f} → Half-Kelly position size: {half_kelly * 100:.1f}%
Estimated reward/risk ratio: {reward_risk:.2f}
Simulated portfolio drawdown: 4.2%
Simulated sector exposure: 18%
Simulated correlation with existing positions: 0.45

Apply all risk constraints. Output JSON only."""

        raw = await self._call_claude(SYSTEM_PROMPT, user_msg)
        if raw:
            try:
                result = json.loads(raw)
                result.setdefault("kelly_fraction", round(kelly, 4))
                result.setdefault("position_size_pct", position_size)
                return result
            except json.JSONDecodeError:
                pass

        return self._mock_analysis(ticker, kelly, half_kelly, position_size, avg_confidence, reward_risk)

    def _mock_analysis(self, ticker, kelly, half_kelly, position_size, avg_confidence, reward_risk) -> dict:
        rng = random.Random(sum(ord(c) for c in ticker) + 77)
        drawdown = rng.uniform(1, 12)
        sector_conc = rng.uniform(5, 28)
        correlation = rng.uniform(0.1, 0.65)
        vol_scalar = rng.uniform(0.7, 1.2)

        warnings = []
        if drawdown > 10:
            warnings.append(f"Portfolio drawdown at {drawdown:.1f}%, approaching 15% limit")
        if sector_conc > 25:
            warnings.append(f"Sector concentration at {sector_conc:.1f}%, near 30% cap")
        if position_size < 0.5:
            warnings.append("Low Kelly fraction suggests weak edge — consider passing")

        approved = drawdown < 15 and sector_conc < 30 and correlation < 0.7 and avg_confidence > 40

        return {
            "approved": approved,
            "position_size_pct": position_size,
            "kelly_fraction": round(kelly, 4),
            "stop_loss_adjustment": round(rng.uniform(-0.5, 0.5), 2),
            "portfolio_drawdown": round(drawdown, 2),
            "sector_concentration": round(sector_conc, 1),
            "correlation_check": round(correlation, 3),
            "vol_scalar": round(vol_scalar, 3),
            "warnings": warnings,
            "reasoning": (
                f"Risk check for {ticker}: Kelly={kelly:.3f} → half-Kelly position size {position_size:.1f}%. "
                f"Portfolio drawdown {drawdown:.1f}% (limit 15%). "
                f"Sector concentration {sector_conc:.1f}% (limit 30%). "
                f"Correlation with existing positions {correlation:.2f} (limit 0.70). "
                f"Signal {'APPROVED' if approved else 'REJECTED'} by risk manager."
            ),
        }
