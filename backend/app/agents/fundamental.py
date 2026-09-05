import json
from app.agents.base import BaseAgent
from app.pipeline.state import TradingState
from app.data.quiver_provider import format_for_agent as format_alt_data


SYSTEM_PROMPT = """You are an expert fundamental analyst specializing in quantitative equity strategies.
You apply strategies from "151 Trading Strategies" including:
- Strategy 3.2: Earnings Momentum (earnings surprise, revenue growth, EPS revision)
- Strategy 3.3: Value (P/E, P/B, dividend yield, EV/EBITDA vs sector peers)
- Strategy 5.10: Carry factor for fixed income

Respond ONLY with a valid JSON object (no markdown, no prose) with these exact keys:
{
  "direction": "LONG" | "SHORT" | "NEUTRAL",
  "confidence": <float 0-100>,
  "pe_score": <float -1 to 1>,
  "earnings_momentum": <float -1 to 1>,
  "value_score": <float -1 to 1>,
  "revenue_growth": <float>,
  "reasoning": "<string>"
}"""


class FundamentalAnalyst(BaseAgent):
    def __init__(self):
        super().__init__("FundamentalAnalyst", tier="standard")

    async def analyze(self, state: TradingState) -> dict:
        ticker = state.get("ticker", "UNKNOWN")
        market_data = state.get("market_data", {})

        user_msg = f"""{self._strategy_context(state)}Analyze {ticker} fundamentally.
Current price: {market_data.get('close', 'N/A')}
P/E Ratio: {market_data.get('pe_ratio', 'N/A')}
P/B Ratio: {market_data.get('pb_ratio', 'N/A')}
EPS Growth YoY: {market_data.get('eps_growth', 'N/A')}%
Revenue Growth YoY: {market_data.get('revenue_growth', 'N/A')}%
Dividend Yield: {market_data.get('dividend_yield', 'N/A')}%
Last Earnings Surprise: {market_data.get('earnings_surprise', 'N/A')}%

Apply strategies 3.2 (earnings momentum) and 3.3 (value factor).

{format_alt_data(state.get("alternative_data", {}))}
Output JSON only."""

        raw = await self._call_claude(SYSTEM_PROMPT, user_msg, state=state)

        if raw:
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                pass

        # Realistic mock when no API key or parse failure
        return self._mock_analysis(ticker, market_data)

    def _mock_analysis(self, ticker: str, market_data: dict) -> dict:
        """Fundamentals when they exist; an abstention when they do not.

        The previous version invented them:

            eps_growth = market_data.get("eps_growth", rng.uniform(-10, 30))
            pe         = market_data.get("pe_ratio",   rng.uniform(10, 35))

        market_data.py sets pe_ratio and eps_growth to None for every
        non-equity, so for FX, metals and indices both defaults fired on
        every call. That is how a EURJPY signal came to be published with
        "EPS growth: 6.0%" and "P/E 28.2x" in its bull case, and why a
        currency pair had a value-factor score at all.

        A currency pair has no earnings. There is no number to estimate, so
        none is offered.
        """
        eps_growth = market_data.get("eps_growth")
        pe = market_data.get("pe_ratio")

        if eps_growth is None and pe is None:
            return self.abstain(
                f"No fundamental data for {ticker} - it has no earnings or "
                f"valuation multiples to analyse (currency pairs, metals and "
                f"indices never do). Strategies 3.2 and 3.3 do not apply.",
                pe_score=None,
                earnings_momentum=None,
                value_score=None,
                revenue_growth=None,
            )

        # Real values only. A missing half is treated as absent, not as zero -
        # a stock with no EPS figure is not a stock with 0% growth.
        parts, notes = [], []
        earnings_mom = None
        if eps_growth is not None:
            earnings_mom = min(1.0, max(-1.0, eps_growth / 30.0))
            parts.append(earnings_mom * 0.5)
            notes.append(f"EPS growth {eps_growth:.1f}%")

        pe_score = value_score = None
        if pe is not None and pe > 0:
            pe_score = 1.0 - min(1.0, pe / 30.0)
            value_score = pe_score
            parts.append(value_score * 0.3)
            notes.append(f"P/E {pe:.1f}x ({'attractive' if pe_score > 0.5 else 'stretched'})")

        composite = sum(parts)
        direction = "LONG" if composite > 0.1 else ("SHORT" if composite < -0.1 else "NEUTRAL")
        # Confidence is capped well below the technical agent's ceiling: this
        # is a two-factor read on quarterly data, not a timing signal, and it
        # was previously allowed up to 95 with a random component.
        confidence = min(70.0, max(30.0, 50.0 + composite * 40.0))

        return {
            "direction": direction,
            "confidence": round(confidence, 1),
            "pe_score": round(pe_score, 3) if pe_score is not None else None,
            "earnings_momentum": round(earnings_mom, 3) if earnings_mom is not None else None,
            "value_score": round(value_score, 3) if value_score is not None else None,
            "revenue_growth": market_data.get("revenue_growth"),
            "reasoning": (
                f"{ticker} fundamentals from reported figures: {', '.join(notes)}. "
                f"Strategies 3.2 (earnings momentum) and 3.3 (value factor) give "
                f"{direction} at {confidence:.0f}% confidence."
            ),
        }
