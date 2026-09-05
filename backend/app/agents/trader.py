import json
from app.agents.base import BaseAgent
from app.pipeline.state import TradingState


_FOREX_5DP = {"EURUSD", "GBPUSD", "AUDUSD", "NZDUSD", "USDCHF", "USDCAD",
               "EURGBP", "EURJPY", "GBPJPY", "EURAUD", "EURCHF", "AUDCAD",
               "AUDNZD", "GBPAUD", "GBPCHF", "NZDCAD", "CADJPY", "CHFJPY",
               "EURCAD", "EURNZD", "GBPCAD", "GBPNZD", "AUDCHF", "NZDCHF"}
_FOREX_3DP = {"USDJPY", "EURJPY", "GBPJPY", "CADJPY", "CHFJPY", "AUDJPY", "NZDJPY"}


def _price_decimals(price: float, ticker: str = "") -> int:
    """Return appropriate decimal places for price formatting.
    Forex pairs get standard pip precision (5dp or 3dp for JPY pairs).
    """
    t = ticker.upper().replace("/", "").replace("-", "").replace("=X", "")
    if t in _FOREX_3DP:  return 3
    if t in _FOREX_5DP:  return 5
    # Fallback: price-magnitude based
    if price < 0.001:  return 6
    if price < 0.1:    return 5
    if price < 10:     return 4
    if price < 100:    return 3
    return 2


BASE_SYSTEM_PROMPT = """You are an elite quantitative research analyst and portfolio strategist with 20+ years of experience.
You synthesize analysis from 7 specialized AI analysts, a quant validation, and a bull/bear debate
to produce probability-weighted market research. You apply the mathematical frameworks from "151 Trading Strategies".

IMPORTANT: You do NOT produce buy/sell signals. You produce PROBABILITY ASSESSMENTS.

Your job:
1. Weigh analyst consensus (fundamental, technical, sentiment, macro, order flow, regime change, correlation)
2. Evaluate the bull vs bear debate quality and arguments
3. Consider the Quant analyst's statistical validation (p-value, win rate, Sharpe)
4. Compute the probability score (0-100) representing bullish probability
5. Set a RESEARCH TARGET (price the thesis points to) and INVALIDATION LEVEL (price where thesis breaks)
6. Write concise bull case and bear case summaries
7. Identify which of the 151 strategies support the thesis
8. Build a clear reasoning chain

Respond ONLY with a valid JSON object:
{
  "probability_score": <float 0-100, where >50 = bullish lean, <50 = bearish lean>,
  "bullish_pct": <float 0-100>,
  "bearish_pct": <float 0-100>,
  "research_target": <float — price target if thesis plays out>,
  "invalidation_level": <float — price where thesis is invalidated>,
  "analytical_window": "<string, e.g. '3-7 DAY' or '1-3 DAY'>,
  "bull_case": "<string — 2-3 sentence bull thesis>",
  "bear_case": "<string — 2-3 sentence bear thesis>",
  "confidence_score": <float 0-100>,
  "position_size_pct": <float 0-5>,
  "strategy_sources": [<string>, ...],
  "reasoning_chain": [<string>, ...],
  "trade_rationale": "<string>"
}"""

# Keep for backward compat (mock path uses this)
SYSTEM_PROMPT = BASE_SYSTEM_PROMPT


class TraderAgent(BaseAgent):
    def __init__(self):
        # Use the most capable model for the final decision
        super().__init__("TraderAgent", tier="premium")

    async def analyze(self, state: TradingState) -> dict:
        ticker = state.get("ticker", "UNKNOWN")
        fund = state.get("fundamental_analysis", {})
        tech = state.get("technical_analysis", {})
        sent = state.get("sentiment_analysis", {})
        macro = state.get("macro_analysis", {})
        oflow = state.get("order_flow_analysis", {})
        regime = state.get("regime_change_analysis", {})
        corr = state.get("correlation_analysis", {})
        quant = state.get("quant_validation", {})
        risk = state.get("risk_assessment", {})
        bull = state.get("bull_case", "")
        bear = state.get("bear_case", "")
        market_data = state.get("market_data", {})

        current_price = market_data.get("close", 100.0)
        _dec = _price_decimals(current_price, ticker)
        _pfmt = f".{_dec}f"

        # Vote aggregation across the 7 analysts.
        #
        # An analyst that abstained saw no data. Its opinion is not NEUTRAL -
        # it has none - so it is excluded from the tally entirely rather than
        # contributing a `.get("confidence", 50)` default, which is what used
        # to happen and which quietly manufactured a vote for every agent
        # whose output was missing a field.
        all_analyses = [fund, tech, sent, macro, oflow, regime, corr]
        votes = []
        for analysis in all_analyses:
            if not analysis or analysis.get("abstained"):
                continue
            d = analysis.get("direction", "NEUTRAL")
            c = analysis.get("confidence", 0)
            if c <= 0:
                continue
            votes.append((d, c))

        # How many analysts actually formed a directional opinion. This is the
        # number that decides whether there is a signal at all.
        directional_votes = [(d, c) for d, c in votes if d in ("LONG", "SHORT")]

        long_score = sum(c for d, c in votes if d == "LONG")
        short_score = sum(c for d, c in votes if d == "SHORT")
        # Ties and empty tallies used to resolve to LONG through `>=`. With
        # abstentions now possible that would have turned "nobody knows" into
        # a buy recommendation, so the tie is explicitly NEUTRAL and the
        # no-signal case is handled by MIN_DIRECTIONAL_VOTES below.
        if long_score > short_score:
            direction = "LONG"
        elif short_score > long_score:
            direction = "SHORT"
        else:
            direction = "NEUTRAL"

        # Build system prompt with profile injection
        profile_slug = state.get("strategy_profile", "balanced")
        system_prompt = self._build_system_prompt(profile_slug)

        # ── Memory context injection ────────────────────────────────────
        memory_block = state.get("memory_context", "")

        timeframe = state.get("timeframe", "1D")
        user_msg = f"""{memory_block}{self._strategy_context(state)}Produce a probability assessment for {ticker}.

ANALYSIS TIMEFRAME: {timeframe}
CURRENT PRICE: {current_price:{_pfmt}}
Base your research_target and invalidation_level on this exact current price.
Set analytical_window appropriate for the {timeframe} timeframe.

ANALYST CONSENSUS (7 agents):
- Fundamental: {fund.get('direction')} ({fund.get('confidence', 0):.0f}%) — {fund.get('reasoning', '')[:200]}
- Technical: {tech.get('direction')} ({tech.get('confidence', 0):.0f}%) — {tech.get('reasoning', '')[:200]}
- Sentiment: {sent.get('direction')} ({sent.get('confidence', 0):.0f}%) — {sent.get('reasoning', '')[:200]}
- Macro: {macro.get('direction')} ({macro.get('confidence', 0):.0f}%) — {macro.get('reasoning', '')[:200]}
- OrderFlow: {oflow.get('direction')} ({oflow.get('confidence', 0):.0f}%) — {oflow.get('reasoning', '')[:200]}
- RegimeChange: {regime.get('direction')} ({regime.get('confidence', 0):.0f}%) — {regime.get('reasoning', '')[:200]}
- Correlation: {corr.get('direction')} ({corr.get('confidence', 0):.0f}%) — {corr.get('reasoning', '')[:200]}

QUANT VALIDATION:
- Statistical edge: {quant.get('statistical_edge', 'N/A')}
- p-value: {quant.get('p_value', 'N/A')}
- Win rate: {quant.get('backtest_win_rate', 'N/A')}
- Sharpe: {quant.get('sharpe_estimate', 'N/A')}

DEBATE:
Bull case: {bull[:300]}
Bear case: {bear[:300]}

RISK PARAMETERS:
- Support: {tech.get('support', current_price * 0.95):{_pfmt}}
- Resistance: {tech.get('resistance', current_price * 1.06):{_pfmt}}

STRATEGY PROFILE: {profile_slug.upper()}
DIRECTION LEAN: {direction} (based on analyst vote aggregation)
{"If BEARISH/SHORT: set research_target BELOW current price (near support) and invalidation_level ABOVE current price (near resistance)." if direction == "SHORT" else "If BULLISH/LONG: set research_target ABOVE current price (near resistance) and invalidation_level BELOW current price (near support)."}
Output JSON only."""

        raw = await self._call_claude(system_prompt, user_msg, max_tokens=3000)
        if raw:
            try:
                result = json.loads(raw)
                # Ensure probability fields exist
                prob = result.get("probability_score", result.get("confidence_score", 50))
                result["probability_score"] = prob
                result.setdefault("bullish_pct", round(prob, 1))
                result.setdefault("bearish_pct", round(100 - prob, 1))
                _profile_params = self._PROFILE_PARAMS.get(profile_slug, self._PROFILE_PARAMS["balanced"])
                result.setdefault("analytical_window", _profile_params["window"])
                result.setdefault("bull_case", "")
                result.setdefault("bear_case", "")

                # Derive direction from probability for backward compat
                direction = "LONG" if prob >= 50 else "SHORT"
                result["direction"] = direction

                # Validate research_target / invalidation_level
                rt = result.get("research_target", 0)
                il = result.get("invalidation_level", 0)
                atr = tech.get("atr", market_data.get("atr", current_price * 0.012))
                if atr <= 0:
                    atr = current_price * 0.012

                # Validate direction coherence: target must be on the correct side of price
                direction_valid = True
                if rt and direction == "LONG" and rt < current_price:
                    direction_valid = False
                elif rt and direction == "SHORT" and rt > current_price:
                    direction_valid = False
                if il and direction == "LONG" and il > current_price:
                    direction_valid = False
                elif il and direction == "SHORT" and il < current_price:
                    direction_valid = False

                if not rt or abs(rt - current_price) / max(current_price, 1e-9) > 0.30 or not direction_valid:
                    # Compute from ATR if hallucinated or directionally inverted
                    result = self._compute_probability_signal(ticker, current_price, direction, votes, tech, risk, fund, sent, macro, market_data, profile_slug, timeframe)
                else:
                    # Map to backward-compat fields
                    result["entry_price"] = current_price
                    result["stop_loss"] = il if il else round(current_price - atr * 1.5, _dec) if direction == "LONG" else round(current_price + atr * 1.5, _dec)
                    result["take_profit_1"] = rt
                    result["take_profit_2"] = round(rt + (rt - current_price) * 0.5, _dec) if rt != current_price else rt
                    result["take_profit_3"] = round(rt + (rt - current_price) * 1.0, _dec) if rt != current_price else rt
                    result["risk_reward_ratio"] = round(abs(rt - current_price) / max(abs(current_price - result["stop_loss"]), 1e-9), 1)

                    atr_15m = market_data.get("atr_15m", atr * 0.196)
                    result["timeframe_levels"] = self._compute_timeframe_levels(current_price, direction, atr, atr_15m, _dec)

                return result
            except json.JSONDecodeError:
                pass

        return self._compute_probability_signal(ticker, current_price, direction, votes, tech, risk, fund, sent, macro, market_data, profile_slug, timeframe)

    def _build_system_prompt(self, profile_slug: str) -> str:
        """Build system prompt with strategy profile injection."""
        from app.profiles.manager import profile_manager
        profile = profile_manager.get_profile(profile_slug)
        if profile.prompt_block:
            return f"{BASE_SYSTEM_PROMPT}\n\n=== STRATEGY PROFILE: {profile.name.upper()} ===\n{profile.prompt_block}"
        return BASE_SYSTEM_PROMPT

    def _pin_entry_and_recompute(self, result: dict, price: float, direction: str, atr: float, atr_15m: float, dec: int) -> dict:
        """Pin entry to exact current price and recompute SL/TP from ATR."""
        entry = round(price, dec)
        result["entry_price"] = entry

        if direction == "LONG":
            stop     = round(entry - atr * 1.5, dec)
            risk_amt = entry - stop
            result["stop_loss"]      = stop
            result["take_profit_1"] = round(entry + risk_amt * 1.5, dec)
            result["take_profit_2"] = round(entry + risk_amt * 2.5, dec)
            result["take_profit_3"] = round(entry + risk_amt * 4.0, dec)
        else:
            stop     = round(entry + atr * 1.5, dec)
            risk_amt = stop - entry
            result["stop_loss"]      = stop
            result["take_profit_1"] = round(entry - risk_amt * 1.5, dec)
            result["take_profit_2"] = round(entry - risk_amt * 2.5, dec)
            result["take_profit_3"] = round(entry - risk_amt * 4.0, dec)

        result["timeframe_levels"] = self._compute_timeframe_levels(entry, direction, atr, atr_15m, dec)
        return result

    def _compute_timeframe_levels(self, entry: float, direction: str, atr_daily: float, atr_15m: float, dec: int) -> dict:
        """Compute SCALP (1-15min) and SWING (30min-1D) entry/SL/TP levels."""
        scalp_atr = atr_15m if atr_15m > 0 else atr_daily * 0.196

        def _levels(atr_used: float, swing_tp3: bool = False) -> dict:
            if direction == "LONG":
                sl       = round(entry - atr_used * 2.0, dec)
                risk     = entry - sl
                tp1      = round(entry + risk * 1.5, dec)
                tp2      = round(entry + risk * 2.5, dec)
                tp3      = round(entry + risk * 4.0, dec) if swing_tp3 else None
            else:
                sl       = round(entry + atr_used * 2.0, dec)
                risk     = sl - entry
                tp1      = round(entry - risk * 1.5, dec)
                tp2      = round(entry - risk * 2.5, dec)
                tp3      = round(entry - risk * 4.0, dec) if swing_tp3 else None
            risk_pct = round(abs(sl - entry) / entry * 100, 3)
            out = {"entry": entry, "stop_loss": sl, "take_profit_1": tp1,
                   "take_profit_2": tp2, "atr": round(atr_used, dec), "risk_pct": risk_pct}
            if tp3 is not None:
                out["take_profit_3"] = tp3
            return out

        scalp = _levels(scalp_atr, swing_tp3=False)
        scalp["label"] = "SCALP · 1–15M"
        swing = _levels(atr_daily, swing_tp3=True)
        swing["label"] = "SWING · 30M–1D"
        return {"scalp": scalp, "swing": swing}

    # Keep old name as alias for backward compat
    def _compute_signal(self, ticker, price, direction, votes, tech, risk, fund, sent, macro, market_data=None) -> dict:
        return self._compute_probability_signal(ticker, price, direction, votes, tech, risk, fund, sent, macro, market_data)

    # Minimum analysts that must have data AND a direction before a signal
    # is published at all. See the NO_SIGNAL branch below.
    MIN_DIRECTIONAL_VOTES = 2

    # Profile → analytical window and ATR multipliers
    _PROFILE_PARAMS = {
        "scalper":       {"window": "5-30 MIN",  "target_atr": 1.0,  "stop_atr": 0.5},
        "ict_smc":       {"window": "1-4 HOUR",  "target_atr": 2.0,  "stop_atr": 1.0},
        "orb":           {"window": "1-4 HOUR",  "target_atr": 2.0,  "stop_atr": 1.0},
        "vwap_pullback": {"window": "1-4 HOUR",  "target_atr": 2.0,  "stop_atr": 1.0},
        "news_catalyst": {"window": "1-3 DAY",   "target_atr": 2.5,  "stop_atr": 1.2},
        "swing":         {"window": "5-15 DAY",  "target_atr": 4.0,  "stop_atr": 2.0},
        # Balanced geometry is the one the auto-scanner ships on, so it is the one
        # that was measured. scripts/backtest_screener.py over 3y of real bars on a
        # 20-symbol universe: tp 3.5 / sl 1.0 / 10-bar hold was the best of 54
        # configurations at +0.265R expectancy, and the previous 1.5 stop with a
        # 7-day window returned +0.148R. The window is stated in calendar days and
        # 10 trading bars is ~14 of them.
        "balanced":      {"window": "5-14 DAY",  "target_atr": 3.5,  "stop_atr": 1.0},
    }

    def _compute_probability_signal(self, ticker, price, direction, votes, tech, risk, fund, sent, macro, market_data=None, profile: str = "balanced", timeframe: str = "1D") -> dict:
        if market_data is None:
            market_data = {}
        dec = _price_decimals(price, ticker)
        # Forex pairs have much smaller ATR (~0.5%) vs stocks (~1.2%)
        t_upper = ticker.upper().replace("/", "").replace("-", "").replace("=X", "")
        is_forex = t_upper in _FOREX_5DP or t_upper in _FOREX_3DP
        default_atr_pct = 0.005 if is_forex else 0.012
        atr = tech.get("atr", market_data.get("atr", price * default_atr_pct))
        if atr <= 0:
            atr = price * default_atr_pct
        atr_15m = market_data.get("atr_15m", atr * 0.196)

        entry = round(price, dec)

        # Profile-aware parameters
        params = self._PROFILE_PARAMS.get(profile, self._PROFILE_PARAMS["balanced"])
        target_atr_mult = params["target_atr"]
        stop_atr_mult = params["stop_atr"]
        analytical_window = params["window"]

        # For scalper, use 15m ATR instead of daily
        if profile in ("scalper",) and atr_15m > 0:
            atr = atr_15m

        # Compute probability from vote weights (exclude NEUTRAL from denominator)
        long_weight = sum(c for d, c in votes if d == "LONG")
        short_weight = sum(c for d, c in votes if d == "SHORT")
        directional_total = long_weight + short_weight
        n_directional = len([1 for d, _ in votes if d in ("LONG", "SHORT")])

        # Not enough analysts saw data to call anything.
        #
        # `direction = "LONG" if probability_score >= 50 else "SHORT"` cannot
        # return "no opinion": with an empty tally bullish_pct defaulted to
        # 50.0 and the >= sent it to LONG. That was harmless while every agent
        # always answered - they answered with RNG. Now that agents abstain,
        # it would have converted silence into a buy recommendation, which is
        # a worse failure than the one being fixed.
        #
        # Two independent directional votes is the floor. One agent agreeing
        # with itself is not a consensus, and the technical agent alone is a
        # single indicator set, not a nine-agent pipeline.
        # Synthetic price data can never become a published signal.
        #
        # market_data.py falls back to _mock_market_data when BOTH the
        # TradingView and yfinance feeds fail. That builds 260 bars from
        # `rng.gauss(0.0001, 0.012)` - a random walk - and tags the result
        # data_source="mock". Every downstream number is then computed
        # correctly from fabricated bars: the technical agent's EMA crossover
        # and RSI are real arithmetic on invented prices, and the entry,
        # research target and invalidation level below would be derived from
        # a synthetic ATR around a synthetic price.
        #
        # The tag was already being recorded and simply never checked.
        if market_data.get("data_source") == "mock":
            return {
                "direction": "NEUTRAL",
                "status": "NO_SIGNAL",
                "probability_score": None,
                "confidence_score": 0.0,
                "confidence": 0.0,
                "entry_price": None,
                "research_target": None,
                "invalidation_level": None,
                "risk_reward_ratio": None,
                "position_size_pct": None,
                "status_reasons": [
                    "Live price feed unavailable - both TradingView and Yahoo failed.",
                    "Bars for this symbol are synthetic, so no tradeable level can be quoted.",
                ],
                "reasoning_chain": [
                    f"{ticker}: no live market data.",
                    "Prices came from the offline generator, not the market.",
                    "No signal is published on synthetic bars.",
                ],
                "strategy_sources": [],
                "agent_attribution": [],
            }

        if n_directional < self.MIN_DIRECTIONAL_VOTES or directional_total <= 0:
            # Only the analyses passed into this method are in scope here;
            # order_flow, regime and correlation are aggregated into `votes`
            # upstream and are reflected in n_directional.
            abstained_names = [n for n, a in (("fundamental", fund), ("technical", tech),
                                              ("sentiment", sent), ("macro", macro))
                               if not a or a.get("abstained")]
            return {
                "direction": "NEUTRAL",
                "status": "NO_SIGNAL",
                "probability_score": None,
                "confidence_score": 0.0,
                "confidence": 0.0,
                "entry_price": entry,
                "research_target": None,
                "invalidation_level": None,
                "risk_reward_ratio": None,
                "position_size_pct": None,
                "status_reasons": [
                    f"Only {n_directional} analyst(s) formed a directional view; "
                    f"{self.MIN_DIRECTIONAL_VOTES} are required.",
                    f"Abstained (no data): {', '.join(abstained_names) or 'none'}.",
                ],
                "reasoning_chain": [
                    f"{ticker}: insufficient evidence for a signal.",
                    f"{n_directional} of 7 analysts had data and a direction.",
                    "No trade idea is published rather than one built on a thin tally.",
                ],
                "strategy_sources": [],
                "agent_attribution": [],
            }

        bullish_pct = round(long_weight / directional_total * 100, 1)
        bearish_pct = round(100 - bullish_pct, 1)
        probability_score = bullish_pct
        direction = "LONG" if probability_score >= 50 else "SHORT"

        conviction = max(long_weight, short_weight) / directional_total
        # Confidence is capped by how many analysts actually contributed. Two
        # agreeing agents out of seven should not read like seven agreeing:
        # the old formula could return 92 on a single unopposed vote.
        coverage = n_directional / 7.0
        confidence = min(92, max(35, 45 + conviction * 50)) * (0.55 + 0.45 * coverage)

        # Research target & invalidation level (replaces TP/SL)
        if direction == "LONG":
            research_target = round(entry + atr * target_atr_mult, dec)
            invalidation_level = round(entry - atr * stop_atr_mult, dec)
            stop = invalidation_level
            risk_amt = entry - stop
            tp1 = research_target
            tp2 = round(entry + risk_amt * 2.5, dec)
            tp3 = round(entry + risk_amt * 4.0, dec)
        else:
            research_target = round(entry - atr * target_atr_mult, dec)
            invalidation_level = round(entry + atr * stop_atr_mult, dec)
            stop = invalidation_level
            risk_amt = stop - entry
            tp1 = research_target
            tp2 = round(entry - risk_amt * 2.5, dec)
            tp3 = round(entry - risk_amt * 4.0, dec)

        risk_reward_ratio = round(abs(research_target - entry) / max(abs(entry - invalidation_level), 1e-9), 1)
        target_pct = round(abs(research_target - entry) / entry * 100, 1)

        # Determine strategy sources
        strategy_sources = []
        if tech.get("ema_crossover") in ["BULLISH", "BEARISH"]:
            strategy_sources.append("ema_crossover_3.11-3.13")
        if abs(tech.get("momentum_score", 0)) > 0.2:
            strategy_sources.append("price_momentum_3.1")
        if abs(tech.get("mean_reversion_signal", 0)) > 0.3:
            strategy_sources.append("mean_reversion_3.9")
        if fund.get("earnings_momentum", 0) > 0.2:
            strategy_sources.append("earnings_momentum_3.2")
        if abs(fund.get("value_score", 0)) > 0.3:
            strategy_sources.append("value_factor_3.3")
        if macro.get("macro_regime") in ["RISK_ON", "RISK_OFF"]:
            strategy_sources.append("macro_momentum_19.2")
        if sent.get("news_sentiment") and abs(sent.get("news_sentiment", 0)) > 0.2:
            strategy_sources.append("sentiment_nlp_18.3")
        if not strategy_sources:
            strategy_sources = ["multi_factor_alpha_3.20"]

        fmt = f".{dec}f"
        lean = "BULLISH" if probability_score >= 50 else "BEARISH"
        reasoning_chain = [
            f"Probability assessment: {probability_score:.0f}% {lean} ({bullish_pct:.0f}% bull / {bearish_pct:.0f}% bear)",
            f"Technical: EMA crossover {tech.get('ema_crossover', 'N/A')}, RSI {tech.get('rsi', 50):.0f}",
            f"Fundamental: Earnings momentum {fund.get('earnings_momentum', 0):+.2f}, value score {fund.get('value_score', 0):+.2f}",
            f"Sentiment: News {sent.get('news_sentiment', 0):+.2f}, social {sent.get('social_sentiment', 0):+.2f}",
            f"Macro regime: {macro.get('macro_regime', 'N/A')}, Fed {macro.get('fed_stance', 'N/A')}",
            f"Research target {research_target:{fmt}} (+{target_pct:.1f}%), invalidation below {invalidation_level:{fmt}}",
            f"Potential R/R: {risk_reward_ratio:.1f}:1",
        ]

        return {
            # Probability model fields
            "probability_score": probability_score,
            "bullish_pct": bullish_pct,
            "bearish_pct": bearish_pct,
            "research_target": round(research_target, dec),
            "invalidation_level": round(invalidation_level, dec),
            "risk_reward_ratio": risk_reward_ratio,
            "analytical_window": analytical_window,
            "bull_case": f"{fund.get('reasoning', '')[:150]}. {sent.get('reasoning', '')[:100]}",
            "bear_case": f"{macro.get('reasoning', '')[:150]}. {tech.get('reasoning', '')[:100]}",
            # Backward compat fields (DB model still uses these)
            "direction": direction,
            "entry_price": round(entry, dec),
            "stop_loss": round(stop, dec),
            "take_profit_1": round(tp1, dec),
            "take_profit_2": round(tp2, dec),
            "take_profit_3": round(tp3, dec),
            "confidence_score": round(confidence, 1),
            # Was `risk.get("position_size_pct", round(rng.uniform(1, 3), 2))`
            # - a random 1-3% of equity presented to the user as a sizing
            # recommendation whenever the risk manager had not produced one.
            # None means "size this yourself"; it is not filled in.
            "position_size_pct": risk.get("position_size_pct"),
            "strategy_sources": strategy_sources,
            "reasoning_chain": reasoning_chain,
            "trade_rationale": (
                f"{probability_score:.0f}% {lean} on {ticker} @ {entry:{fmt}}. "
                f"Research target {research_target:{fmt}} (+{target_pct:.1f}%). "
                f"Invalidation below {invalidation_level:{fmt}}. "
                f"R/R: {risk_reward_ratio:.1f}:1. Strategies: {', '.join(strategy_sources[:3])}."
            ),
            "timeframe_levels": self._compute_timeframe_levels(entry, direction, atr, atr_15m, dec),
        }
