import json
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

        # A missing VIX used to default to 18.0 - a specific, plausible,
        # entirely invented level that then drove regime classification. None
        # means "not observed", and the classifier treats it that way.
        vix = market_data.get("vix")
        price_change = market_data.get("price_change_pct", 0.0)
        atr = market_data.get("atr", 0)
        close = market_data.get("close")

        # Volatility ratio as regime indicator. This one IS real: ATR and
        # close both come from actual bars. It falls back to None rather than
        # the old 1.2, which was a made-up volatility for any symbol whose
        # price failed to load.
        vol_ratio = (atr / close * 100) if (close and atr) else None

        # Macro context, only where the macro agent actually produced it.
        # `geopolitical_risk` was renamed to geo_article_volume because it
        # counted scraped articles rather than risk; reading the old key here
        # would have silently returned the 40.0 default on every call.
        macro_regime = macro.get("macro_regime")
        fed_stance = macro.get("fed_stance")

        # Crisis headlines from news context
        crisis_hl = news_ctx.get("crisis_headlines", [])

        strategy_ctx = self._strategy_context(state)
        user_msg = f"""{strategy_ctx}Detect regime state for {ticker}.
VIX level: {vix if vix is not None else "not observed"}
Price change today: {price_change:+.2f}%
Volatility (ATR/price): {f"{vol_ratio:.3f}%" if vol_ratio is not None else "unavailable"}
Macro regime (from macro agent): {macro_regime or "not assessed"}
Fed stance: {fed_stance or "not assessed"}
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

        return self._mock_analysis(ticker, vix, price_change, vol_ratio, macro_regime, crisis_hl)

    def _mock_analysis(self, ticker: str, vix: float | None, price_change: float,
                       vol_ratio: float | None, macro_regime: str | None,
                       crisis_hl: list) -> dict:
        """Regime from realised volatility, which is real, or an abstention.

        The old version drew everything it reported from a seeded RNG:

            stability   = rng.uniform(0.6, 0.9)      # per branch
            change_prob = rng.uniform(0.05, 0.25)
            vix_term    = rng.choice(["CONTANGO", "FLAT"])
            confidence  = rng.uniform(55, 85)

        VIX term structure in particular was a coin flip printed as a market
        observation - this feed carries no VIX futures curve at all.

        What IS available is ATR/close, computed from real bars, and that is
        a legitimate realised-volatility regime proxy. So the classification
        is built from that alone, and everything the data cannot support is
        reported as None instead of being filled in.
        """
        if vol_ratio is None:
            return self.abstain(
                f"No usable price data for {ticker}, so no volatility regime can be "
                f"classified. Neither realised volatility nor VIX was observed.",
                current_regime=None,
                regime_stability=None,
                change_probability=None,
                vix_term_structure=None,
            )

        # Realised-volatility bands. ATR/close near 0.5% is a quiet FX tape,
        # 1-2% is a normal equity tape, and above 3% is genuinely disturbed.
        if vol_ratio < 0.8:
            regime, stability = "LOW_VOLATILITY", 0.80
        elif vol_ratio < 2.0:
            regime, stability = "NORMAL", 0.65
        elif vol_ratio < 3.5:
            regime, stability = "ELEVATED_VOLATILITY", 0.45
        else:
            regime, stability = "HIGH_VOLATILITY", 0.25

        # Crisis headlines and a large daily move both argue the current
        # regime is less likely to persist.
        change_probability = round(min(0.75, (1.0 - stability) * 0.6
                                       + (0.15 if crisis_hl else 0.0)
                                       + min(0.2, abs(price_change) / 25.0)), 3)

        # Confidence reflects how much corroboration exists, not a random draw.
        confidence = 55.0
        if vix is not None:
            confidence += 10.0
        if macro_regime:
            confidence += 5.0

        notes = [f"realised volatility (ATR/close) {vol_ratio:.2f}%"]
        if vix is not None:
            notes.append(f"VIX {vix:.1f}")
        if macro_regime:
            notes.append(f"macro regime {macro_regime}")
        if crisis_hl:
            notes.append(f"{len(crisis_hl)} crisis headlines")

        return {
            # Regime is a state description, not a directional call. It used
            # to vote LONG/SHORT off the same RNG; it now stays out of the
            # direction sum and informs sizing and conviction instead.
            "direction": "NEUTRAL",
            "confidence": round(confidence, 1),
            "current_regime": regime,
            "regime_stability": stability,
            "change_probability": change_probability,
            # No VIX futures curve in this feed, so no term structure claim.
            "vix_term_structure": None,
            "reasoning": (
                f"{ticker} regime: {regime} from {', '.join(notes)}. "
                f"Estimated probability of regime change within 5 sessions: "
                f"{change_probability:.0%}. Regime is context for sizing and "
                f"conviction; it does not itself vote a direction."
            ),
        }
