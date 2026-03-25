"""Universal output schema for all agents."""
from datetime import datetime, timezone
from pydantic import BaseModel


class AgentOutput(BaseModel):
    agent: str
    direction: str = "NEUTRAL"  # LONG / SHORT / NEUTRAL — kept for backward compat
    bullish_contribution: float = 0.0  # 0.0 - 1.0
    bearish_contribution: float = 0.0  # 0.0 - 1.0 (NOT 1 - bullish)
    confidence: float = 50.0
    reasoning: str = ""
    data_sources: list[str] = []
    timestamp: str = ""
    raw_data: dict = {}  # preserves all agent-specific fields

    @classmethod
    def from_analysis(
        cls,
        agent_name: str,
        result: dict,
        data_sources: list[str] | None = None,
    ) -> "AgentOutput":
        """Convert a legacy agent result dict into AgentOutput."""
        direction = result.get("direction", "NEUTRAL")
        confidence = float(result.get("confidence", 50))
        reasoning = result.get("reasoning", "")

        # Convert direction + confidence into bullish/bearish contributions
        conf_norm = confidence / 100.0
        if direction == "LONG":
            bullish = conf_norm
            bearish = (1 - conf_norm) * 0.3  # residual bearish uncertainty
        elif direction == "SHORT":
            bullish = (1 - conf_norm) * 0.3
            bearish = conf_norm
        else:
            bullish = conf_norm * 0.4
            bearish = conf_norm * 0.4

        return cls(
            agent=agent_name,
            direction=direction,
            bullish_contribution=round(bullish, 3),
            bearish_contribution=round(bearish, 3),
            confidence=confidence,
            reasoning=reasoning,
            data_sources=data_sources or [],
            timestamp=datetime.now(timezone.utc).isoformat() + "Z",
            raw_data=result,
        )

    def to_state_dict(self) -> dict:
        """Return a dict for TradingState — includes all raw_data fields
        plus the new schema fields, so downstream code can read either."""
        d = {**self.raw_data}
        d["bullish_contribution"] = self.bullish_contribution
        d["bearish_contribution"] = self.bearish_contribution
        d["data_sources"] = self.data_sources
        d["agent_timestamp"] = self.timestamp
        # Ensure direction/confidence/reasoning are always present
        d.setdefault("direction", self.direction)
        d.setdefault("confidence", self.confidence)
        d.setdefault("reasoning", self.reasoning)
        return d
