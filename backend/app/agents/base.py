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

    @staticmethod
    def _strategy_context(state: TradingState) -> str:
        """Build a strategy/timeframe context block from the pipeline state."""
        profile = state.get("strategy_profile", "balanced")
        timeframe = state.get("timeframe", "1D")
        if profile == "balanced" and timeframe == "1D":
            return ""
        lines = [f"ACTIVE STRATEGY: {profile.upper()}",
                 f"ANALYSIS TIMEFRAME: {timeframe}"]
        if timeframe in ("1m", "5m"):
            lines.append("Focus on micro price action, order flow, and very tight levels. Fundamentals and macro are minimal factors.")
        elif timeframe in ("15m", "30m"):
            lines.append("Focus on intraday levels, session structure, and volume. Fundamentals are secondary.")
        elif timeframe in ("1h", "4h"):
            lines.append("Intraday-to-swing horizon. Balance technical levels with sentiment and macro context.")
        return "\n".join(lines) + "\n\n"

    async def analyze(self, state: TradingState) -> dict:
        raise NotImplementedError
