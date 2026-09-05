import structlog
from app.providers.router import model_router
from app.pipeline.state import TradingState

log = structlog.get_logger()


class BaseAgent:
    def __init__(self, name: str, tier: str = "standard"):
        self.name = name
        self.tier = tier

    async def _call_llm(self, system: str, user: str, max_tokens: int = 2000) -> str:
        return await model_router.complete(
            system=system,
            user=user,
            tier=self.tier,
            max_tokens=max_tokens,
            agent_name=self.name,
        )

    # Alias — keeps existing call sites working during transition
    _call_claude = _call_llm

    _STRATEGY_GUIDANCE = {
        "scalper": "SCALPER: 1-5 minute charts. Focus on order flow, micro price action, bid-ask imbalance. Extremely tight stops (0.5-1 ATR). Fundamentals and macro are irrelevant at this timeframe. Targets within minutes.",
        "ict_smc": "ICT/SMART MONEY: 15m charts. Focus on fair value gaps, order blocks, liquidity sweeps, institutional footprint. Identify where smart money is positioned.",
        "orb": "OPENING RANGE BREAKOUT: 15-30m charts. Focus on first 15-30 min range, breakout direction, volume confirmation. Momentum-gated entries.",
        "vwap_pullback": "VWAP PULLBACK: 30m charts. Focus on mean reversion to VWAP, institutional entry zones. Strategy 3.9 core.",
        "news_catalyst": "NEWS CATALYST: 1h charts. Focus on event-driven moves — earnings, macro releases, breaking news. Sentiment and macro are primary.",
        "swing": "SWING: Daily/weekly charts. Focus on multi-day trends, patient entries, wider stops. Fundamentals and macro are key factors.",
    }

    @staticmethod
    def _strategy_context(state: TradingState) -> str:
        """Build a strategy/timeframe context block from the pipeline state."""
        profile = state.get("strategy_profile", "balanced")
        timeframe = state.get("timeframe", "1D")
        if profile == "balanced" and timeframe == "1D":
            return ""
        lines = [f"ACTIVE STRATEGY: {profile.upper()}",
                 f"ANALYSIS TIMEFRAME: {timeframe}"]
        guidance = BaseAgent._STRATEGY_GUIDANCE.get(profile, "")
        if guidance:
            lines.append(guidance)
        elif timeframe in ("1m", "5m"):
            lines.append("Focus on micro price action, order flow, and very tight levels. Fundamentals and macro are minimal factors.")
        elif timeframe in ("15m", "30m"):
            lines.append("Focus on intraday levels, session structure, and volume. Fundamentals are secondary.")
        elif timeframe in ("1h", "4h"):
            lines.append("Intraday-to-swing horizon. Balance technical levels with sentiment and macro context.")
        return "\n".join(lines) + "\n\n"

    @staticmethod
    def abstain(reason: str, **extra) -> dict:
        """No usable data — say so instead of inventing a number.

        Every agent used to answer a missing data source with
        `rng.uniform(...)`, seeded on the ticker and the date. That produced
        output which was stable within a day and therefore looked like
        analysis: a P/E for a currency pair, a geopolitical risk index, a win
        rate and a p-value computed from an invented sample size.

        An agent that cannot see anything has exactly one honest answer, and
        this is it. confidence 0 with direction NEUTRAL keeps it out of the
        trader's long/short sums, and `abstained` lets the pipeline count how
        many analysts actually saw data before it calls anything a signal.
        """
        return {
            "direction": "NEUTRAL",
            "confidence": 0.0,
            "abstained": True,
            "reasoning": reason,
            **extra,
        }

    async def analyze(self, state: TradingState) -> dict:
        raise NotImplementedError
