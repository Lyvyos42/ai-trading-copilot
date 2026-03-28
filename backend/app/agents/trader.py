import json
import random
from app.agents.base import BaseAgent
from app.pipeline.state import TradingState


def _price_decimals(price: float) -> int:
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
        _dec = _price_decimals(current_price)
        _pfmt = f".{_dec}f"

        # Vote aggregation from all 7 analysts
        all_analyses = [fund, tech, sent, macro, oflow, regime, corr]
        votes = []
        for analysis in all_analyses:
            d = analysis.get("direction", "NEUTRAL")
            c = analysis.get("confidence", 50)
            votes.append((d, c))

        long_score = sum(c for d, c in votes if d == "LONG")
        short_score = sum(c for d, c in votes if d == "SHORT")
        direction = "LONG" if long_score >= short_score else "SHORT"

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
Set research_target near resistance level and invalidation_level near support.
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
                result.setdefault("analytical_window", "3-7 DAY")
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

                if not rt or abs(rt - current_price) / max(current_price, 1e-9) > 0.30:
                    # Compute from ATR if hallucinated
                    result = self._compute_probability_signal(ticker, current_price, direction, votes, tech, risk, fund, sent, macro, market_data)
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

        return self._compute_probability_signal(ticker, current_price, direction, votes, tech, risk, fund, sent, macro, market_data)

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

    def _compute_probability_signal(self, ticker, price, direction, votes, tech, risk, fund, sent, macro, market_data=None) -> dict:
        if market_data is None:
            market_data = {}
        rng = random.Random(sum(ord(c) for c in ticker) + 13)

        dec = _price_decimals(price)
        atr = tech.get("atr", market_data.get("atr", price * 0.012))
        if atr <= 0:
            atr = price * 0.012
        atr_15m = market_data.get("atr_15m", atr * 0.196)

        entry = round(price, dec)

        # Compute probability from vote weights
        long_weight = sum(c for d, c in votes if d == "LONG")
        short_weight = sum(c for d, c in votes if d == "SHORT")
        total = sum(c for _, c in votes) or 100
        bullish_pct = round(long_weight / total * 100, 1)
        bearish_pct = round(100 - bullish_pct, 1)
        probability_score = bullish_pct

        conviction = max(long_weight, short_weight) / total
        confidence = min(92, max(35, 45 + conviction * 50))

        # Research target & invalidation level (replaces TP/SL)
        if direction == "LONG":
            research_target = round(entry + atr * 3.5, dec)
            invalidation_level = round(entry - atr * 1.5, dec)
            # Backward compat fields
            stop = invalidation_level
            risk_amt = entry - stop
            tp1 = research_target
            tp2 = round(entry + risk_amt * 2.5, dec)
            tp3 = round(entry + risk_amt * 4.0, dec)
        else:
            research_target = round(entry - atr * 3.5, dec)
            invalidation_level = round(entry + atr * 1.5, dec)
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
            "analytical_window": "3-7 DAY",
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
            "position_size_pct": risk.get("position_size_pct", round(rng.uniform(1, 3), 2)),
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
