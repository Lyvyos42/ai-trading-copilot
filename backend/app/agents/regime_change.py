import json
import random
from app.agents.base import BaseAgent
from app.pipeline.state import TradingState


SYSTEM_PROMPT = """You are an expert regime change detector specializing in cross-asset signals:
- VIX term structure analysis (contango vs backwardation)
- Cross-asset correlation regime shifts
- Credit spread widening/tightening (HY vs IG, TED spread)
- Sector rotation patterns (defensive vs cyclical leadership)
- Strategy 19.2: Macro regime classification
- Strategy 6.1: Volatility regime switching

Respond ONLY with a valid JSON object:
{
  "direction": "LONG" | "SHORT" | "NEUTRAL",
  "confidence": <float 0-100>,
  "current_regime": "RISK_ON" | "RISK_OFF" | "TRANSITIONAL" | "CRISIS",
  "regime_stability": <float 0 to 1>,
  "vix_term_structure": "CONTANGO" | "BACKWARDATION" | "FLAT",
  "credit_spread_signal": "TIGHTENING" | "WIDENING" | "STABLE",
  "sector_rotation": "CYCLICAL_LEADING" | "DEFENSIVE_LEADING" | "MIXED",
  "regime_change_probability": <float 0 to 1>,
  "reasoning": "<string>"
}"""


class RegimeChangeAnalyst(BaseAgent):
    def __init__(self):
        super().__init__("RegimeChangeAnalyst", tier="standard")

    async def analyze(self, state: TradingState) -> dict:
        ticker = state.get("ticker", "UNKNOWN")
        market_data = state.get("market_data", {})
        macro = state.get("macro_analysis", {})
        news_ctx = state.get("news_context", {})

        vix = market_data.get("vix", 18.0)
        price_change = market_data.get("price_change_pct", 0.0)
        atr = market_data.get("atr", 0)
        close = market_data.get("close", 100)

        # Volatility ratio as regime indicator
        vol_ratio = (atr / close * 100) if close else 1.2

        # Use macro regime if available
        macro_regime = macro.get("macro_regime", "TRANSITIONAL")
        geo_risk = macro.get("geopolitical_risk", 40.0)
        fed_stance = macro.get("fed_stance", "NEUTRAL")

        # Crisis headlines from news context
        crisis_hl = news_ctx.get("crisis_headlines", [])

        user_msg = f"""Detect regime state for {ticker}.
VIX level: {vix}
Price change today: {price_change:+.2f}%
Volatility (ATR/price): {vol_ratio:.3f}%
Macro regime (from macro agent): {macro_regime}
Fed stance: {fed_stance}
Geopolitical risk: {geo_risk}/100
Crisis headlines: {len(crisis_hl)} detected

Apply strategy 19.2 (regime classification) and 6.1 (vol regime switching).
Assess VIX term structure, credit spreads, and sector rotation signals.
Determine probability of regime change within next 5 sessions. Output JSON only."""

        raw = await self._call_claude(SYSTEM_PROMPT, user_msg)
        if raw:
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                pass

        return self._mock_analysis(ticker, vix, price_change, vol_ratio, macro_regime, geo_risk, crisis_hl)

    def _mock_analysis(self, ticker: str, vix: float, price_change: float,
                       vol_ratio: float, macro_regime: str, geo_risk: float,
                       crisis_hl: list) -> dict:
        seed = sum(ord(c) for c in ticker) + 88
        rng = random.Random(seed)

        # Regime determination
        if vix > 35 or crisis_hl:
            regime = "CRISIS"
            stability = rng.uniform(0.1, 0.3)
        elif vix > 25 or geo_risk > 65:
            regime = "RISK_OFF"
            stability = rng.uniform(0.3, 0.5)
        elif vix < 15 and geo_risk < 35:
            regime = "RISK_ON"
            stability = rng.uniform(0.6, 0.9)
        else:
            regime = "TRANSITIONAL"
            stability = rng.uniform(0.3, 0.6)

        # VIX term structure
        if vix > 25:
            vix_term = "BACKWARDATION"
        elif vix < 15:
            vix_term = "CONTANGO"
        else:
            vix_term = rng.choice(["CONTANGO", "FLAT"])

        # Credit spreads
        if regime in ("CRISIS", "RISK_OFF"):
            credit = "WIDENING"
        elif regime == "RISK_ON":
            credit = "TIGHTENING"
        else:
            credit = "STABLE"

        # Sector rotation
        if regime == "RISK_ON":
            rotation = "CYCLICAL_LEADING"
        elif regime in ("RISK_OFF", "CRISIS"):
            rotation = "DEFENSIVE_LEADING"
        else:
            rotation = "MIXED"

        # Regime change probability (higher when transitional or vol is shifting)
        change_prob = rng.uniform(0.05, 0.25)
        if regime == "TRANSITIONAL":
            change_prob = rng.uniform(0.3, 0.6)
        elif abs(price_change) > 2.0:
            change_prob = min(0.8, change_prob + 0.2)

        # Direction based on regime
        if regime == "RISK_ON":
            direction = "LONG"
            confidence = rng.uniform(55, 80)
        elif regime in ("RISK_OFF", "CRISIS"):
            direction = "SHORT"
            confidence = rng.uniform(55, 85)
        else:
            direction = "NEUTRAL"
            confidence = rng.uniform(40, 60)

        return {
            "direction": direction,
            "confidence": round(confidence, 1),
            "current_regime": regime,
            "regime_stability": round(stability, 3),
            "vix_term_structure": vix_term,
            "credit_spread_signal": credit,
            "sector_rotation": rotation,
            "regime_change_probability": round(change_prob, 3),
            "reasoning": (
                f"{ticker} regime analysis: current regime is {regime} "
                f"(stability {stability:.2f}). VIX at {vix:.1f} ({vix_term}). "
                f"Credit spreads {credit.lower()}. Sector rotation: {rotation.lower().replace('_', ' ')}. "
                f"Regime change probability: {change_prob:.0%}. "
                f"Strategy 6.1/19.2: {direction} at {confidence:.0f}%."
            ),
        }
