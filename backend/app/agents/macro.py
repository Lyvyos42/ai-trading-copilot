import json
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


# One macro regime does NOT mean one direction.
#
# Until now this agent emitted a single direction for the whole market, so
# every symbol in a scan received an identical macro vote. That is how EURUSD
# and GBPUSD came back with byte-identical signals, and BTC-USD and ETH-USD
# likewise: two of the four voters were the same market-wide opinion applied
# undifferentiated.
#
# A risk-off regime is not bearish for everything. It is bearish for equities,
# crypto and high-beta currencies, and BULLISH for the classic havens - gold,
# the dollar, the yen, the franc, Treasuries. Translating one regime through
# the asset being analysed produces genuine per-symbol differentiation from a
# single honest macro read, rather than manufacturing diversity that is not
# there.
_HAVEN_PREFIXES = ("XAU", "XAG", "XPT")          # precious metals
_HAVEN_CCY = ("USD", "JPY", "CHF")               # funding / safe-haven currencies
_HIGH_BETA_CCY = ("AUD", "NZD", "ZAR", "MXN", "TRY", "BRL", "NOK", "SEK")


def _risk_off_bias(ticker: str, asset_class: str) -> int:
    """+1 if a RISK-OFF regime is BULLISH for this instrument, -1 if bearish.

    Returns 0 when the mapping is genuinely ambiguous, in which case the macro
    agent declines to take a directional view on this symbol rather than
    guessing - a cross like EURGBP has no clean haven interpretation.
    """
    t = (ticker or "").upper().replace("=X", "").replace("-USD", "")

    if any(t.startswith(p) for p in _HAVEN_PREFIXES):
        return +1                                  # gold rallies in risk-off
    if asset_class in ("crypto",):
        return -1                                  # crypto trades as high beta
    if asset_class in ("stocks", "etfs", "indices", "futures"):
        return -1                                  # equities sell off
    if asset_class == "fixed_income":
        return +1                                  # bonds bid

    if asset_class == "fx" and len(t) == 6:
        base, quote = t[:3], t[3:]
        base_haven = base in _HAVEN_CCY
        quote_haven = quote in _HAVEN_CCY
        base_beta = base in _HIGH_BETA_CCY
        quote_beta = quote in _HIGH_BETA_CCY
        # The pair rises when the BASE strengthens.
        if base_haven and not quote_haven:
            return +1
        if quote_haven and not base_haven:
            return -1
        if base_beta and not quote_beta:
            return -1
        if quote_beta and not base_beta:
            return +1
        return 0                                   # haven-vs-haven, or neither

    if asset_class == "commodities":
        return -1                                  # industrial demand proxy

    return 0


class MacroAnalyst(BaseAgent):
    def __init__(self):
        super().__init__("MacroAnalyst", tier="standard")

    async def analyze(self, state: TradingState) -> dict:
        ticker      = state.get("ticker", "UNKNOWN")
        asset_class = state.get("asset_class", "stocks")
        strategy_ctx = self._strategy_context(state)

        # 1. Retrieve FRED data from state or fetch on-demand
        fred_data = state.get("fred_data")
        if not fred_data:
            try:
                from app.data.fred_provider import get_macro_snapshot
                fred_data = await get_macro_snapshot()
            except Exception:
                fred_data = {}

        # 2. Retrieve news context from state or fetch on-demand
        news_ctx = state.get("news_context")
        if not news_ctx or not news_ctx.get("has_news"):
            try:
                from app.services.news_context import get_news_context
                news_ctx = await get_news_context(ticker)
            except Exception:
                news_ctx = {}

        has_news = bool(news_ctx and news_ctx.get("has_news") and news_ctx.get("article_count", 0) > 0)
        has_fred = bool(fred_data and any(k in fred_data for k in (
            "yield_curve_spread", "cpi_yoy", "fed_funds", "gdp_growth", "unemployment", "pce_inflation"
        )))

        if not has_news and not has_fred:
            return self.abstain(
                f"No live economic data (FRED) or scraped news headlines available for {ticker}. "
                f"MacroAnalyst abstains rather than estimating a regime without real inputs.",
                gdp_signal=None,
                inflation_signal=None,
                fed_stance=None,
                geo_article_volume=0,
                carry_signal=None,
                macro_regime=None,
                upcoming_events=[],
                key_news_drivers=[],
                symbol_specific=False,
                _live_news=False,
            )

        fred_block = format_fred(fred_data)
        return await self._analyze_with_real_data(ticker, asset_class, news_ctx or {}, fred_data or {}, fred_block, strategy_ctx)

    # ── Real data analysis path ───────────────────────────────────────────────

    async def _analyze_with_real_data(
        self, ticker: str, asset_class: str, news_ctx: dict, fred_data: dict,
        fred_block: str = "", strategy_ctx: str = ""
    ) -> dict:
        macro_hl   = news_ctx.get("macro_headlines", [])
        geo_hl     = news_ctx.get("geo_headlines", [])
        crisis_hl  = news_ctx.get("crisis_headlines", [])
        avg_sent   = news_ctx.get("avg_sentiment", 0.0)
        art_count  = news_ctx.get("article_count", 0)

        # Volume of geo/crisis articles
        geo_count    = len(geo_hl) + len(crisis_hl) * 2
        geo_risk_est = min(95, max(10, geo_count * 8 + 20)) if art_count > 0 else 20

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
CRISIS / SYSTEMIC RISK HEADLINES ({len(crisis_hl)} articles):
{chr(10).join(f'  • {h}' for h in crisis_hl)}
"""

        user_msg = f"""{strategy_ctx}Assess macro environment for {ticker} ({asset_class}) using LIVE economic and news data.

=== LIVE MACRO INTELLIGENCE (Real headlines, scraped in last 24h) ===
{macro_section}
{geo_section}
{crisis_section}
=== DERIVED INDICATORS (from {art_count} scraped articles) ===
• Overall news sentiment: {avg_sent:+.3f}
• Estimated geopolitical news volume: {geo_risk_est}/100
• Crisis alert level: {"HIGH" if len(crisis_hl) >= 2 else "ELEVATED" if crisis_hl else "NORMAL"}

{fred_block}

Strategy 19.2: Determine current macro regime from the real indicators and headlines above.
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
                result["symbol_specific"] = False
                return result
            except json.JSONDecodeError:
                pass

        return self._derive_from_macro_and_news(
            ticker, macro_hl, geo_hl, crisis_hl, avg_sent, geo_risk_est, fred_data,
            asset_class,
        )

    def _derive_from_macro_and_news(
        self, ticker: str, macro_hl: list, geo_hl: list, crisis_hl: list,
        avg_sent: float, geo_risk: float, fred_data: dict,
        asset_class: str = "stocks",
    ) -> dict:
        """Deterministic derivation using verified FRED indicators and news headlines."""
        all_text = " ".join(macro_hl + geo_hl + crisis_hl).lower()

        # 1. Fed stance: FRED fed_funds trend + news text
        fed_funds_info = fred_data.get("fed_funds", {})
        fed_funds_trend = fed_funds_info.get("trend", "STABLE")
        if fed_funds_trend == "RISING" or any(w in all_text for w in ["rate hike", "hawkish", "tighten", "inflation concern"]):
            fed_stance = "HAWKISH"
        elif fed_funds_trend == "FALLING" or any(w in all_text for w in ["rate cut", "dovish", "ease", "pivot", "pause"]):
            fed_stance = "DOVISH"
        else:
            fed_stance = "NEUTRAL"

        # 2. Inflation signal: FRED CPI/PCE trend + news text
        cpi_info = fred_data.get("cpi_yoy", {}) or fred_data.get("pce_inflation", {})
        cpi_trend = cpi_info.get("trend", "STABLE")
        if cpi_trend == "RISING" or any(w in all_text for w in ["inflation surge", "cpi rises", "price increase", "hot inflation"]):
            inflation = "RISING"
        elif cpi_trend == "FALLING" or any(w in all_text for w in ["inflation eases", "cpi falls", "disinflation", "deflation"]):
            inflation = "FALLING"
        else:
            inflation = "STABLE"

        # 3. GDP signal: FRED real GDP growth + news text
        gdp_info = fred_data.get("gdp_growth", {})
        gdp_val = gdp_info.get("value")
        gdp_trend = gdp_info.get("trend", "STABLE")
        if (gdp_val is not None and gdp_val < 0) or gdp_trend == "FALLING" or any(w in all_text for w in ["recession", "contraction", "gdp falls", "economic slowdown"]):
            gdp = "CONTRACTIONARY"
        elif (gdp_val is not None and gdp_val > 2.0) or gdp_trend == "RISING" or any(w in all_text for w in ["strong growth", "gdp beats", "expansion", "boom"]):
            gdp = "EXPANSIONARY"
        else:
            gdp = "STABLE"

        # 4. Yield curve spread (10Y - 2Y)
        yc_info = fred_data.get("yield_curve_spread", {})
        yc_val = yc_info.get("value")
        yc_trend = yc_info.get("trend", "")
        yield_curve_inverted = (yc_val is not None and yc_val < 0) or (yc_trend == "INVERTED")

        # 5. Unemployment trend.
        #
        # Both directions are read. Rising unemployment used to be a risk-off
        # reason with no risk-on counterpart, so a labour market that was
        # visibly improving contributed nothing while a deteriorating one
        # voted SHORT. That is the same one-sided-ledger defect that produced
        # 50 consecutive shorts, in miniature: with every other indicator
        # neutral, RISING returned RISK_OFF/SHORT at 55 while FALLING returned
        # TRANSITIONAL/NEUTRAL at 50.
        unemp_info = fred_data.get("unemployment", {})
        unemp_rising = unemp_info.get("trend") == "RISING"
        unemp_falling = unemp_info.get("trend") == "FALLING"

        # 6. Regime evaluation: symmetric comparison grounded in verified indicators
        risk_off_reasons = []
        if crisis_hl:
            risk_off_reasons.append("crisis_headlines")
        if fed_stance == "HAWKISH":
            risk_off_reasons.append("hawkish_fed")
        if inflation == "RISING":
            risk_off_reasons.append("rising_inflation")
        if gdp == "CONTRACTIONARY":
            risk_off_reasons.append("contractionary_gdp")
        if yield_curve_inverted:
            risk_off_reasons.append("yield_curve_inverted")
        if unemp_rising:
            risk_off_reasons.append("rising_unemployment")
        if avg_sent < -0.1:
            risk_off_reasons.append("bearish_news_sentiment")

        risk_on_reasons = []
        if fed_stance == "DOVISH":
            risk_on_reasons.append("dovish_fed")
        if inflation == "FALLING":
            risk_on_reasons.append("falling_inflation")
        if gdp == "EXPANSIONARY":
            risk_on_reasons.append("expansionary_gdp")
        if yc_val is not None and yc_val > 0.5:
            risk_on_reasons.append("steep_yield_curve")
        if unemp_falling:
            risk_on_reasons.append("falling_unemployment")
        if avg_sent > 0.1:
            risk_on_reasons.append("bullish_news_sentiment")

        risk_off = len(risk_off_reasons)
        risk_on = len(risk_on_reasons)

        # The regime is market-wide; the DIRECTION is per-instrument.
        # See _risk_off_bias: risk-off is bearish for equities and crypto and
        # bullish for gold, the dollar and the yen, so one honest macro read
        # now produces different calls for different assets instead of the
        # same vote on every symbol in a scan.
        bias = _risk_off_bias(ticker, asset_class)
        if risk_off > risk_on:
            regime, strength = "RISK_OFF", risk_off - risk_on
        elif risk_on > risk_off:
            regime, strength = "RISK_ON", risk_on - risk_off
        else:
            regime, strength = "TRANSITIONAL", 0

        if regime == "TRANSITIONAL" or bias == 0:
            # No regime, or no clean read for this instrument - a haven-vs-haven
            # cross like USDCHF has no unambiguous risk-off interpretation, and
            # guessing one would be exactly the fabrication we removed.
            direction = "NEUTRAL"
            confidence = 50.0
        else:
            lean = bias if regime == "RISK_OFF" else -bias
            direction = "LONG" if lean > 0 else "SHORT"
            confidence = min(70.0, 50.0 + strength * 5.0)

        events = []
        if "fomc" in all_text or "federal reserve" in all_text:
            events.append("FOMC Meeting / Fed Communication")
        if "nonfarm" in all_text or "jobs report" in all_text:
            events.append("Non-Farm Payrolls")
        if "cpi" in all_text:
            events.append("CPI Release")
        if not events:
            events = ["Monitor macro calendar"]

        fed_rate = fed_funds_info.get("value", 0.0)
        carry_signal = round(min(1.0, max(-1.0, (fed_rate - 2.0) * 0.1 + avg_sent * 0.2)), 3) if fed_rate else round(avg_sent * 0.3, 3)

        evidence_pieces = []
        if fred_data:
            evidence_pieces.append(f"FRED data ({len(fred_data)} series)")
            if yield_curve_inverted:
                evidence_pieces.append(f"inverted yield curve ({yc_val:+.2f}%)")
        if macro_hl or geo_hl or crisis_hl:
            evidence_pieces.append(f"{len(macro_hl) + len(geo_hl) + len(crisis_hl)} scraped headlines")

        evidence_str = " + ".join(evidence_pieces) if evidence_pieces else "market indicators"

        reasoning = (
            f"Macro regime from real data ({evidence_str}): {regime}. "
            f"Fed stance: {fed_stance}. Inflation: {inflation}. GDP: {gdp}. "
            f"For {ticker} ({asset_class}) this regime reads {direction} - "
            f"{'treated as a haven' if bias > 0 else 'treated as a risk asset' if bias < 0 else 'no clean haven mapping, so no directional call'}. "
            f"Signals favoring risk-off: {risk_off} ({', '.join(risk_off_reasons) or 'none'}), "
            f"risk-on: {risk_on} ({', '.join(risk_on_reasons) or 'none'}). "
            f"{'Crisis headlines present. ' if crisis_hl else ''}"
            f"Strategy 19.2 macro momentum: {direction} at {confidence:.0f}% confidence."
        )

        return {
            "direction": direction,
            "confidence": round(confidence, 1),
            "gdp_signal": gdp,
            "inflation_signal": inflation,
            "fed_stance": fed_stance,
            "geo_article_volume": round(geo_risk, 1),
            "carry_signal": carry_signal,
            "macro_regime": regime,
            "upcoming_events": events,
            "key_news_drivers": (macro_hl + geo_hl)[:3],
            "symbol_specific": False,
            "reasoning": reasoning,
            "_live_news": True,
        }
