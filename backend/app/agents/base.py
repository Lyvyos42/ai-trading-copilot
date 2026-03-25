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

    async def analyze(self, state: TradingState) -> dict:
        raise NotImplementedError
