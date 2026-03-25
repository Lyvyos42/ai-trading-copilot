"""
ModelRouter — single entry point for all LLM calls.

Every agent and service calls `model_router.complete()` with a tier name.
The router maps tier → provider + model, handles logging, and (future) fallback.
"""
import structlog
from app.config import settings
from app.providers.anthropic import AnthropicProvider

log = structlog.get_logger()

# Default tier → provider:model mappings
_DEFAULT_TIERS: dict[str, str] = {
    "premium":     "anthropic:claude-opus-4-6",
    "standard":    "anthropic:claude-sonnet-4-6",
    "lightweight": "anthropic:claude-haiku-4-5-20251001",
}


def _parse_tier_spec(spec: str) -> tuple[str, str]:
    """Parse 'provider:model' string into (provider, model)."""
    parts = spec.split(":", 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid tier spec '{spec}' — expected 'provider:model'")
    return parts[0], parts[1]


class ModelRouter:
    def __init__(self) -> None:
        # Build tier map from config (env-var overridable) or defaults
        self._tiers: dict[str, tuple[str, str]] = {}
        for tier, default in _DEFAULT_TIERS.items():
            spec = getattr(settings, f"provider_tier_{tier}", default)
            self._tiers[tier] = _parse_tier_spec(spec)

        # Provider singletons — only Anthropic for now
        self._providers = {
            "anthropic": AnthropicProvider(),
        }

    def _get_provider(self, provider_name: str):
        provider = self._providers.get(provider_name)
        if not provider:
            raise ValueError(f"Unknown provider '{provider_name}'")
        return provider

    async def complete(
        self,
        *,
        system: str | None = None,
        user: str,
        tier: str = "standard",
        max_tokens: int = 2000,
        agent_name: str = "",
    ) -> str:
        provider_name, model = self._tiers.get(tier, self._tiers["standard"])
        provider = self._get_provider(provider_name)

        text, usage = await provider.complete(
            system=system,
            messages=[{"role": "user", "content": user}],
            model=model,
            max_tokens=max_tokens,
        )

        if usage:
            log.info(
                "llm_call",
                agent=agent_name or "unknown",
                tier=tier,
                model=model,
                input_tokens=usage.get("input_tokens", 0),
                output_tokens=usage.get("output_tokens", 0),
            )

        return text


# Module-level singleton — import this from anywhere
model_router = ModelRouter()
