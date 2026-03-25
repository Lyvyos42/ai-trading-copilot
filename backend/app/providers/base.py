"""Abstract base class for LLM providers."""
from abc import ABC, abstractmethod


class ProviderBase(ABC):
    @abstractmethod
    async def complete(
        self,
        *,
        system: str | None,
        messages: list[dict],
        model: str,
        max_tokens: int,
    ) -> tuple[str, dict]:
        """Return (text, usage_dict).  usage_dict has input_tokens / output_tokens."""
        ...
