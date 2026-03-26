"""
ProfileManager — loads strategy profile YAML files and provides:
1. Profile prompt block for Trader Agent injection
2. Analyst weight multipliers for bullish/bearish contribution scaling
"""
import os
from pathlib import Path
from typing import Any

import yaml

_DEFINITIONS_DIR = Path(__file__).parent / "definitions"

# Default weights when a profile doesn't specify an agent
_DEFAULT_WEIGHT = 1.0

# All known analyst keys (must match graph.py wrapping keys)
_ANALYST_KEYS = [
    "fundamental", "technical", "sentiment", "macro",
    "order_flow", "regime_change", "correlation",
]


class Profile:
    """Loaded strategy profile."""

    __slots__ = ("name", "slug", "description", "weights", "prompt_block", "is_default")

    def __init__(self, data: dict[str, Any]):
        self.name: str = data["name"]
        self.slug: str = data["slug"]
        self.description: str = data.get("description", "")
        self.is_default: bool = data.get("default", False)
        self.prompt_block: str = data.get("prompt_block", "")
        raw_weights = data.get("weights", {})
        self.weights: dict[str, float] = {
            k: float(raw_weights.get(k, _DEFAULT_WEIGHT))
            for k in _ANALYST_KEYS
        }

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "slug": self.slug,
            "description": self.description,
            "weights": self.weights,
            "is_default": self.is_default,
        }


class ProfileManager:
    """Singleton that loads and caches all profile YAML files."""

    def __init__(self):
        self._profiles: dict[str, Profile] = {}
        self._default_slug: str = "balanced"
        self._load_all()

    def _load_all(self) -> None:
        if not _DEFINITIONS_DIR.exists():
            return
        for path in sorted(_DEFINITIONS_DIR.glob("*.yaml")):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                if not data or "slug" not in data:
                    continue
                profile = Profile(data)
                self._profiles[profile.slug] = profile
                if profile.is_default:
                    self._default_slug = profile.slug
            except Exception:
                continue  # Skip malformed YAML

    def get_profile(self, slug: str | None = None) -> Profile:
        """Return requested profile or the default."""
        if slug and slug in self._profiles:
            return self._profiles[slug]
        return self._profiles.get(self._default_slug, Profile({
            "name": "Balanced", "slug": "balanced",
            "description": "Default balanced profile",
            "prompt_block": "", "weights": {},
        }))

    def list_profiles(self) -> list[dict]:
        """Return all profiles as dicts for the API."""
        return [p.to_dict() for p in self._profiles.values()]

    def apply_weights(self, profile_slug: str | None, agent_results: dict[str, dict]) -> dict[str, dict]:
        """
        Apply profile weight multipliers to bullish_contribution and bearish_contribution
        for each analyst in agent_results.

        agent_results: {"fundamental_analysis": {...}, "technical_analysis": {...}, ...}
        Returns: same dict with contributions scaled.
        """
        profile = self.get_profile(profile_slug)
        for key in list(agent_results.keys()):
            # Extract analyst name from key: "fundamental_analysis" → "fundamental"
            agent_name = key.replace("_analysis", "")
            weight = profile.weights.get(agent_name, _DEFAULT_WEIGHT)
            if weight != _DEFAULT_WEIGHT and isinstance(agent_results[key], dict):
                result = agent_results[key]
                if "bullish_contribution" in result:
                    result["bullish_contribution"] = round(
                        result["bullish_contribution"] * weight, 3
                    )
                if "bearish_contribution" in result:
                    result["bearish_contribution"] = round(
                        result["bearish_contribution"] * weight, 3
                    )
        return agent_results


# Module-level singleton
profile_manager = ProfileManager()
