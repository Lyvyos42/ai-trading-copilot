import anthropic
import structlog
from app.config import settings
from app.pipeline.state import TradingState

log = structlog.get_logger()


class BaseAgent:
    def __init__(self, name: str, model: str = "claude-sonnet-4-6"):
        self.name = name
        self.model = model
        self._client: anthropic.AsyncAnthropic | None = None

    @property
    def client(self) -> anthropic.AsyncAnthropic:
        if self._client is None:
            self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key or None)
        return self._client

    async def _call_claude(self, system: str, user: str, max_tokens: int = 2000) -> str:
        if not settings.anthropic_api_key:
            return ""  # Signals mock path
        try:
            message = await self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            text = message.content[0].text.strip()
            # Strip markdown code fences that Claude often wraps JSON in
            if text.startswith("```"):
                # Remove opening fence (```json or ```)
                text = text.split("\n", 1)[-1] if "\n" in text else text
                # Remove closing fence
                if text.endswith("```"):
                    text = text[: text.rfind("```")]
                text = text.strip()
            return text
        except Exception as e:
            log.warning("claude_call_failed", agent=self.name, error=str(e))
            return ""

    async def analyze(self, state: TradingState) -> dict:
        raise NotImplementedError
