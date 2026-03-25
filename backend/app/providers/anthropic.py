"""Anthropic (Claude) provider — the only provider for now."""
import anthropic
import structlog
from app.config import settings
from app.providers.base import ProviderBase

log = structlog.get_logger()


def _strip_code_fences(text: str) -> str:
    """Remove markdown code fences that Claude often wraps JSON in."""
    if text.startswith("```"):
        text = text.split("\n", 1)[-1] if "\n" in text else text
        if text.endswith("```"):
            text = text[: text.rfind("```")]
        text = text.strip()
    return text


class AnthropicProvider(ProviderBase):
    def __init__(self) -> None:
        self._client: anthropic.AsyncAnthropic | None = None

    @property
    def client(self) -> anthropic.AsyncAnthropic:
        if self._client is None:
            self._client = anthropic.AsyncAnthropic(
                api_key=settings.anthropic_api_key or None,
            )
        return self._client

    async def complete(
        self,
        *,
        system: str | None,
        messages: list[dict],
        model: str,
        max_tokens: int,
    ) -> tuple[str, dict]:
        if not settings.anthropic_api_key:
            return "", {}

        try:
            kwargs: dict = dict(
                model=model,
                max_tokens=max_tokens,
                messages=messages,
            )
            if system:
                kwargs["system"] = system

            message = await self.client.messages.create(**kwargs)
            text = _strip_code_fences(message.content[0].text.strip())
            usage = {
                "input_tokens": message.usage.input_tokens,
                "output_tokens": message.usage.output_tokens,
            }
            return text, usage
        except Exception as e:
            log.warning("anthropic_call_failed", model=model, error=str(e))
            return "", {}
