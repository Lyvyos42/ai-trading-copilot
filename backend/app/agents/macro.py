import json
import random
from app.agents.base import BaseAgent
from app.pipeline.state import TradingState
from app.data.fred_provider import format_for_agent as format_fred


SYSTEM_PROMPT = """You are an expert macro economist applying global macro trading strategies:
- Strategy 19.2: Macro momentum using 4 state variables (GDP, CPI, CB policy, geopolitics)
- Strategy 8.2: FX carry trade (long high-yield, short low-yield currencies)
- Strategy 19.5: Announcement/event day alpha (FOMC, NFP, CPI releases)

You have access to REAL, LIVE scraped news from Reuters, CNBC, BBC, AP, the Federal Reserve, and other sources.
These are actual current headlines — use them to determine the true macro regime.

Consider:
1. Federal Reserve communications and rate signals (highest macro weight)
2. Economic data releases mentioned in headlines (CPI, GDP, jobs, PMI)
3. Geopolitical tensions and their risk-off implications
4. Crisis signals that demand immediate regime reclassification

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
  "key_news_drivers": [<string>, ...],
  "reasoning": "<string>"
}

The "key_news_drivers" field must list the 2-3 real headlines that most shaped your regime assessment."""


class MacroAnalyst(BaseAgent):
    def __init__(self):
        super().__init__("MacroAnalyst", tier="standard")

    async def analyze(self, state: TradingState) -> dict:
        ticker     = state.get("ticker", "UNKNOWN")
        asset_class = state.get("asset_class", "stocks")
        news_ctx   = state.get("news_context", {})
        has_news   = news_ctx.get("has_news", False)
        fred_block = format_fred(state.get("fred_data", {}))

        if has_news:
            return await self._analyze_with_live_news(ticker, asset_class, news_ctx, fred_block)
        else:
            return await self._analyze_with_mock(ticker, asset_class, fred_block)

    # ── Live news path ────────────────────────────────────────────────────────

    async def _analyze_with_live_news(self, ticker: str, asset_class: str, news_ctx: dict, fred_block: str = "") -> dict:
        macro_hl   = news_ctx.get("macro_headlines", [])
        geo_hl     = news_ctx.get("geo_headlines", [])
        crisis_hl  = news_ctx.get("crisis_headlines", [])
        avg_sent   = news_ctx.get("avg_sentiment", 0.0)
        art_count  = news_ctx.get("article_count", 0)

        # Derive geopolitical risk score from volume of geo/crisis articles
        geo_count    = len(geo_hl) + len(crisis_hl) * 2
        geo_risk_est = min(95, max(10, geo_count * 8 + 20))

        macro_section = ""
        if macro_hl:
            macro_section = f"""
MACRO / CENTRAL BANK HEADLINES ({len(macro_hl)} articles):
{chr(10).join(f'  • {h}' for h in macro_hl)}
"""
        else:
            macro_section = "\nMACRO / CENTRAL BANK HEADLINES: None in current feed.\n"

        geo_section = ""
        if geo_hl:
            geo_section = f"""
GEOPOLITICAL HEADLINES ({len(geo_hl)} articles):
{chr(10).join(f'  • {h}' for h in geo_hl)}
"""

        crisis_section = ""
        if crisis_hl:
            crisis_section = f"""
⚠ CRISIS / SYSTEMIC RISK HEADLINES ({len(crisis_hl)} articles):
{chr(10).join(f'  • {h}' for h in crisis_hl)}
"""

        user_msg = f"""Assess macro environment for {ticker} ({asset_class}) using LIVE news data.

=== LIVE MACRO INTELLIGENCE (Real headlines, scraped in last 24h) ===
{macro_section}
{geo_section}
{crisis_section}
=== DERIVED INDICATORS (from {art_count} scraped articles) ===
• Overall news sentiment: {avg_sent:+.3f}
• Estimated geopolitical risk index: {geo_risk_est}/100
• Crisis alert level: {"HIGH" if len(crisis_hl) >= 2 else "ELEVATED" if crisis_hl else "NORMAL"}

{fred_block}

Strategy 19.2: Determine the current macro regime from the real headlines above.
Strategy 8.2: Assess FX carry implications.
Strategy 19.5: Identify any upcoming catalyst events mentioned.
Output JSON only."""

        raw = await self._call_claude(SYSTEM_PROMPT, user_msg)
        if raw:
            try:
                result = json.loads(raw)
                result["_live_news"] = True
                result["_macro_headlines"] = macro_hl[:3]
                result["_geo_headlines"] = geo_hl[:2]
                return result
            except json.JSONDecodeError:
                pass

        return self._derive_from_news(ticker, macro_hl, geo_hl, crisis_hl, avg_sent, geo_risk_est)

    def _derive_from_news(
        self, ticker: str, macro_hl: list, geo_hl: list, crisis_hl: list,
        avg_sent: float, geo_risk: float
    ) -> dict:
        """Fallback: derive macro regime directly from news content."""
        all_text = " ".join(macro_hl + geo_hl + crisis_hl).lower()

        # Fed stance detection
        if any(w in all_text for w in ["rate hike", "hawkish", "tighten", "inflation concern"]):
            fed_stance = "HAWKISH"
        elif any(w in all_text for w in ["rate cut", "dovish", "ease", "pivot", "pause"]):
            fed_stance = "DOVISH"
        else:
            fed_stance = "NEUTRAL"

        # Inflation signal
        if any(w in all_text for w in ["inflation surge", "cpi rises", "price increase", "hot inflation"]):
            inflation = "RISING"
        elif any(w in all_text for w in ["inflation eases", "cpi falls", "disinflation", "deflation"]):
            inflation = "FALLING"
        else:
            inflation = "STABLE"

        # GDP signal
        if any(w in all_text for w in ["recession", "contraction", "gdp falls", "economic slowdown"]):
            gdp = "CONTRACTIONARY"
        elif any(w in all_text for w in ["strong growth", "gdp beats", "expansion", "boom"]):
            gdp = "EXPANSIONARY"
        else:
            gdp = "STABLE"

        # Regime
        if crisis_hl or geo_risk > 65 or fed_stance == "HAWKISH":
            regime = "RISK_OFF"
            direction = "SHORT"
            confidence = 65.0
        elif avg_sent > 0.1 and fed_stance != "HAWKISH":
            regime = "RISK_ON"
            direction = "LONG"
            confidence = 60.0
        else:
            regime = "TRANSITIONAL"
            direction = "NEUTRAL"
            confidence = 50.0

        events = []
        if "fomc" in all_text or "federal reserve" in all_text:
            events.append("FOMC Meeting / Fed Communication")
        if "nonfarm" in all_text or "jobs report" in all_text:
            events.append("Non-Farm Payrolls")
        if "cpi" in all_text:
            events.append("CPI Release")
        if not events:
            events = ["Monitor macro calendar"]

        return {
            "direction": direction,
            "confidence": round(confidence, 1),
            "gdp_signal": gdp,
            "inflation_signal": inflation,
            "fed_stance": fed_stance,
            "geopolitical_risk": round(geo_risk, 1),
            "carry_signal": round(avg_sent * 0.3, 3),
            "macro_regime": regime,
            "upcoming_events": events,
            "key_news_drivers": (macro_hl + geo_hl)[:3],
            "reasoning": (
                f"Live macro analysis: regime is {regime}. "
                f"Fed stance: {fed_stance}. Inflation: {inflation}. GDP: {gdp}. "
                f"Geopolitical risk index: {geo_risk:.0f}/100. "
                f"{'CRISIS alert active. ' if crisis_hl else ''}"
                f"Strategy 19.2 macro momentum: {direction} at {confidence:.0f}% confidence."
            ),
            "_live_news": True,
        }

    # ── Mock path (no news in DB yet) ─────────────────────────────────────────

    MACRO_REGIMES = [
        {"regime": "RISK_ON",      "gdp": "EXPANSIONARY",  "inflation": "STABLE",  "fed": "DOVISH",  "geo_risk": 25.0, "direction_bias": "LONG"},
        {"regime": "RISK_OFF",     "gdp": "CONTRACTIONARY", "inflation": "RISING", "fed": "HAWKISH", "geo_risk": 70.0, "direction_bias": "SHORT"},
        {"regime": "TRANSITIONAL", "gdp": "STABLE",         "inflation": "FALLING","fed": "NEUTRAL", "geo_risk": 45.0, "direction_bias": "NEUTRAL"},
    ]
    UPCOMING_EVENTS = [
        "FOMC Rate Decision", "Non-Farm Payrolls", "CPI Report",
        "GDP Advance Estimate", "Fed Chair Press Conference",
        "ECB Policy Meeting", "PCE Inflation Data",
    ]

    async def _analyze_with_mock(self, ticker: str, asset_class: str, fred_block: str = "") -> dict:
        rng = random.Random(sum(ord(c) for c in ticker) + 99)
        regime_data = rng.choice(self.MACRO_REGIMES)
        events = rng.sample(self.UPCOMING_EVENTS, 2)

        user_msg = f"""Assess macro environment for {ticker} ({asset_class}).
NOTE: Live news scraper is warming up — using estimated macro regime.
Current macro regime indicators:
- GDP signal: {regime_data['gdp']} (Strategy 19.2 state variable 1)
- Inflation: {regime_data['inflation']} (Strategy 19.2 state variable 2)
- Fed stance: {regime_data['fed']} (Strategy 19.2 state variable 3)
- Geopolitical risk: {regime_data['geo_risk']}/100 (Strategy 19.2 state variable 4)
- FX Carry: USD vs G10 high-yield spread {rng.uniform(-0.5, 0.5):.2f}% (Strategy 8.2)
- Upcoming events: {', '.join(events)} (Strategy 19.5)

{fred_block}
Output JSON only."""

        raw = await self._call_claude(SYSTEM_PROMPT, user_msg)
        if raw:
            try:
                result = json.loads(raw)
                result["_live_news"] = False
                return result
            except json.JSONDecodeError:
                pass

        return self._mock_fallback(ticker, regime_data, events, rng)

    def _mock_fallback(self, ticker: str, regime_data: dict, events: list, rng: random.Random) -> dict:
        geo_risk   = regime_data["geo_risk"] + rng.uniform(-10, 10)
        carry      = rng.uniform(-0.3, 0.3)
        direction  = regime_data["direction_bias"]
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
            "key_news_drivers": [],
            "reasoning": (
                f"Macro regime is {regime_data['regime']} (estimated). GDP {regime_data['gdp'].lower()}, "
                f"inflation {regime_data['inflation'].lower()}, Fed {regime_data['fed'].lower()}. "
                f"Geopolitical risk {geo_risk:.0f}/100. "
                f"Strategy 19.2: {direction} at {confidence:.0f}% confidence."
            ),
            "_live_news": False,
        }
