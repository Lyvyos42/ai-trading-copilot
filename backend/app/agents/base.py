import anthropic
import structlog
from app.config import settings
from app.pipeline.state import TradingState

log = structlog.get_logger()


class BaseAgent:
    def __init__(self, name: str, model: str = "claude-sonnet-4-6"):
        self.name = name
        self.model = model
        self._client: anthropic.Anthropic | None = None

    @property
    def client(self) -> anthropic.Anthropic:
        if self._client is None:
            self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key or None)
        return self._client

    def _call_claude(self, system: str, user: str, max_tokens: int = 2000) -> str:
        if not settings.anthropic_api_key:
            return ""  # Signals mock path
        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            return message.content[0].text
        except Exception as e:
            log.warning("claude_call_failed", agent=self.name, error=str(e))
            return ""

    async def analyze(self, state: TradingState) -> dict:
        raise NotImplementedError
