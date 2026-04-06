"""Anthropic (Claude) provider with automatic fallback detection.

When the API returns a rate-limit (429), credit-exhaustion, or auth error,
the provider enters 'circuit-breaker' mode and immediately returns empty
for all subsequent calls until the cooldown expires. This prevents 9 agents
from each waiting 30+ seconds for timeout when credits are exhausted.
"""
import time
import anthropic
import structlog
from app.config import settings
from app.providers.base import ProviderBase

log = structlog.get_logger()

# Circuit breaker: skip API calls for this many seconds after a fatal error
_CIRCUIT_BREAKER_COOLDOWN = 300  # 5 minutes


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
        self._circuit_open_until: float = 0.0  # timestamp when circuit breaker resets
        self._fallback_reason: str = ""

    @property
    def client(self) -> anthropic.AsyncAnthropic:
        if self._client is None:
            self._client = anthropic.AsyncAnthropic(
                api_key=settings.anthropic_api_key or None,
            )
        return self._client

    @property
    def is_fallback_mode(self) -> bool:
        """True if the circuit breaker is open (API unavailable)."""
        return time.monotonic() < self._circuit_open_until

    def _trip_circuit(self, reason: str) -> None:
        """Open the circuit breaker — all calls skip API for the cooldown period."""
        self._circuit_open_until = time.monotonic() + _CIRCUIT_BREAKER_COOLDOWN
        self._fallback_reason = reason
        log.warning(
            "anthropic_circuit_breaker_tripped",
            reason=reason,
            cooldown_seconds=_CIRCUIT_BREAKER_COOLDOWN,
        )

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

        # Circuit breaker: skip immediately if API is known to be down
        if self.is_fallback_mode:
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

            # Success — reset circuit breaker if it was set
            self._circuit_open_until = 0.0
            self._fallback_reason = ""

            text = _strip_code_fences(message.content[0].text.strip())
            usage = {
                "input_tokens": message.usage.input_tokens,
                "output_tokens": message.usage.output_tokens,
            }
            return text, usage

        except anthropic.RateLimitError as e:
            self._trip_circuit(f"Rate limited: {e}")
            return "", {}
        except anthropic.AuthenticationError as e:
            self._trip_circuit(f"Auth/credit error: {e}")
            return "", {}
        except anthropic.APIStatusError as e:
            if e.status_code in (429, 402, 529):
                self._trip_circuit(f"API status {e.status_code}: {e}")
            else:
                log.warning("anthropic_call_failed", model=model, error=str(e))
            return "", {}
        except Exception as e:
            log.warning("anthropic_call_failed", model=model, error=str(e))
            return "", {}
