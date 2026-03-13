import json
import random
from app.agents.base import BaseAgent
from app.pipeline.state import TradingState


SYSTEM_PROMPT = """You are an expert macro economist applying global macro trading strategies:
- Strategy 19.2: Macro momentum using 4 state variables (GDP, CPI, CB policy, geopolitics)
- Strategy 8.2: FX carry trade (long high-yield, short low-yield currencies)
- Strategy 19.5: Announcement/event day alpha (FOMC, NFP, CPI releases)

Respond ONLY with a valid JSON object:
{
  "direction": "LONG" | "SHORT" | "NEUTRAL",
  "confidence": <float 0-100>,
  "gdp_signal": "EXPANSIONARY" | "CONTRACTIONARY" | "STABLE",
  "inflation_signal": "RISING" | "FALLING" | "STABLE",
  "fed_stance": "HAWKISH" | "DOVISH" | "NEUTRAL",
  "geopolitical_risk": <float 0-100>,
  "carry_signal": <float -1 to 1>,
  "macro_regime": "RISK_ON" | "RISK_OFF" | "TRANSITIONAL",
  "upcoming_events": [<string>, ...],
  "reasoning": "<string>"
}"""

MACRO_REGIMES = [
    {
        "regime": "RISK_ON",
        "gdp": "EXPANSIONARY",
        "inflation": "STABLE",
        "fed": "DOVISH",
        "geo_risk": 25.0,
        "direction_bias": "LONG",
    },
    {
        "regime": "RISK_OFF",
        "gdp": "CONTRACTIONARY",
        "inflation": "RISING",
        "fed": "HAWKISH",
        "geo_risk": 70.0,
        "direction_bias": "SHORT",
    },
    {
        "regime": "TRANSITIONAL",
        "gdp": "STABLE",
        "inflation": "FALLING",
        "fed": "NEUTRAL",
        "geo_risk": 45.0,
        "direction_bias": "NEUTRAL",
    },
]

UPCOMING_EVENTS = [
    "FOMC Rate Decision",
    "Non-Farm Payrolls",
    "CPI Report",
    "GDP Advance Estimate",
    "Fed Chair Press Conference",
    "ECB Policy Meeting",
    "PCE Inflation Data",
]


class MacroAnalyst(BaseAgent):
    def __init__(self):
        super().__init__("MacroAnalyst", model="claude-sonnet-4-6")

    async def analyze(self, state: TradingState) -> dict:
        ticker = state.get("ticker", "UNKNOWN")
        asset_class = state.get("asset_class", "stocks")

        rng = random.Random(sum(ord(c) for c in ticker) + 99)
        regime_data = rng.choice(MACRO_REGIMES)
        events = rng.sample(UPCOMING_EVENTS, 2)

        user_msg = f"""Assess macro environment for {ticker} ({asset_class}).
Current macro regime indicators:
- GDP signal: {regime_data['gdp']} (Strategy 19.2 state variable 1)
- Inflation: {regime_data['inflation']} (Strategy 19.2 state variable 2)
- Fed stance: {regime_data['fed']} (Strategy 19.2 state variable 3)
- Geopolitical risk: {regime_data['geo_risk']}/100 (Strategy 19.2 state variable 4)
- FX Carry: USD vs G10 high-yield spread {rng.uniform(-0.5, 0.5):.2f}% (Strategy 8.2)
- Upcoming events: {', '.join(events)} (Strategy 19.5)

Output JSON only."""

        raw = self._call_claude(SYSTEM_PROMPT, user_msg)
        if raw:
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                pass

        return self._mock_analysis(ticker, regime_data, events, rng)

    def _mock_analysis(self, ticker: str, regime_data: dict, events: list, rng: random.Random) -> dict:
        geo_risk = regime_data["geo_risk"] + rng.uniform(-10, 10)
        carry = rng.uniform(-0.3, 0.3)
        direction = regime_data["direction_bias"]
        confidence = rng.uniform(45, 80)

        return {
            "direction": direction,
            "confidence": round(confidence, 1),
            "gdp_signal": regime_data["gdp"],
            "inflation_signal": regime_data["inflation"],
            "fed_stance": regime_data["fed"],
            "geopolitical_risk": round(geo_risk, 1),
            "carry_signal": round(carry, 3),
            "macro_regime": regime_data["regime"],
            "upcoming_events": events,
            "reasoning": (
                f"Macro regime is {regime_data['regime']}. GDP is {regime_data['gdp'].lower()}, "
                f"inflation {regime_data['inflation'].lower()}, Fed is {regime_data['fed'].lower()}. "
                f"Geopolitical risk at {geo_risk:.0f}/100. "
                f"Upcoming catalysts: {', '.join(events)}. "
                f"Strategy 19.2 macro momentum yields {direction} bias with {confidence:.0f}% confidence."
            ),
        }
