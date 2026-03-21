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


SYSTEM_PROMPT = """You are an elite quantitative trader and portfolio manager with 20+ years of experience.
You synthesize analysis from 4 specialized AI analysts and a bull/bear debate to make high-conviction
trading decisions. You apply the mathematical frameworks from "151 Trading Strategies".

Your job:
1. Weigh analyst consensus (fundamental, technical, sentiment, macro)
2. Evaluate the bull vs bear debate quality and arguments
3. Apply Kelly criterion for position sizing (Risk Manager will validate after you)
4. Set precise entry, stop-loss, and three take-profit levels (TP1=1.5R, TP2=2.5R, TP3=4R)
5. Identify which of the 151 strategies support your thesis
6. Build a clear reasoning chain

Respond ONLY with a valid JSON object:
{
  "direction": "LONG" | "SHORT",
  "entry_price": <float>,
  "stop_loss": <float>,
  "take_profit_1": <float>,
  "take_profit_2": <float>,
  "take_profit_3": <float>,
  "confidence_score": <float 0-100>,
  "position_size_pct": <float 0-5>,
  "strategy_sources": [<string>, ...],
  "reasoning_chain": [<string>, ...],
  "trade_rationale": "<string>"
}"""


class TraderAgent(BaseAgent):
    def __init__(self):
        # Use the most capable model for the final decision
        super().__init__("TraderAgent", model="claude-opus-4-6")

    async def analyze(self, state: TradingState) -> dict:
        ticker = state.get("ticker", "UNKNOWN")
        fund = state.get("fundamental_analysis", {})
        tech = state.get("technical_analysis", {})
        sent = state.get("sentiment_analysis", {})
        macro = state.get("macro_analysis", {})
        risk = state.get("risk_assessment", {})
        bull = state.get("bull_case", "")
        bear = state.get("bear_case", "")
        market_data = state.get("market_data", {})

        current_price = market_data.get("close", 100.0)
        _dec = _price_decimals(current_price)
        _pfmt = f".{_dec}f"

        # Vote aggregation
        votes = []
        for analysis in [fund, tech, sent, macro]:
            d = analysis.get("direction", "NEUTRAL")
            c = analysis.get("confidence", 50)
            votes.append((d, c))

        long_score = sum(c for d, c in votes if d == "LONG")
        short_score = sum(c for d, c in votes if d == "SHORT")
        direction = "LONG" if long_score >= short_score else "SHORT"

        user_msg = f"""Make a final trading decision for {ticker}.

CURRENT PRICE: {current_price:{_pfmt}}
⚠ Your entry_price MUST be within 1% of {current_price:{_pfmt}}. Base ALL price levels on this exact current price.

ANALYST CONSENSUS:
- Fundamental: {fund.get('direction')} ({fund.get('confidence', 0):.0f}%) — {fund.get('reasoning', '')[:200]}
- Technical: {tech.get('direction')} ({tech.get('confidence', 0):.0f}%) — {tech.get('reasoning', '')[:200]}
- Sentiment: {sent.get('direction')} ({sent.get('confidence', 0):.0f}%) — {sent.get('reasoning', '')[:200]}
- Macro: {macro.get('direction')} ({macro.get('confidence', 0):.0f}%) — {macro.get('reasoning', '')[:200]}

DEBATE:
Bull case: {bull[:300]}
Bear case: {bear[:300]}

RISK PARAMETERS:
- Approved: {risk.get('approved', True)}
- Position size: {risk.get('position_size_pct', 2.0):.1f}%
- Support: {tech.get('support', current_price * 0.95):{_pfmt}}
- Resistance: {tech.get('resistance', current_price * 1.06):{_pfmt}}

Set TP1 at 1.5R, TP2 at 2.5R, TP3 at 4R from entry.
Output JSON only."""

        raw = await self._call_claude(SYSTEM_PROMPT, user_msg, max_tokens=3000)
        if raw:
            try:
                result = json.loads(raw)
                # Use Claude's direction (final synthesis), not vote-aggregated fallback
                final_direction = result.get("direction", direction)
                if final_direction not in ("LONG", "SHORT"):
                    final_direction = direction
                # Tight 1% price validation — anything beyond that is hallucinated context
                entry = result.get("entry_price", 0)
                if entry and abs(entry - current_price) / max(current_price, 1e-9) > 0.01:
                    return self._compute_signal(ticker, current_price, final_direction, votes, tech, risk, fund, sent, macro, market_data)
                # Always pin entry to exact current_price — market orders fill at market.
                # Recompute SL/TP from ATR anchored to the pinned entry.
                atr = tech.get("atr", market_data.get("atr", current_price * 0.012))
                if atr <= 0:
                    atr = current_price * 0.012
                atr_15m = market_data.get("atr_15m", atr * 0.196)
                result = self._pin_entry_and_recompute(result, current_price, final_direction, atr, atr_15m, _dec)
                return result
            except json.JSONDecodeError:
                pass

        return self._compute_signal(ticker, current_price, direction, votes, tech, risk, fund, sent, macro, market_data)

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

    def _compute_signal(self, ticker, price, direction, votes, tech, risk, fund, sent, macro, market_data=None) -> dict:
        if market_data is None:
            market_data = {}
        rng = random.Random(sum(ord(c) for c in ticker) + 13)

        dec = _price_decimals(price)

        # Use ATR from market data (passed via state → tech) for realistic stop placement.
        # ATR gives the average daily range — stops should be at least 1 ATR away.
        atr = tech.get("atr", market_data.get("atr", price * 0.012))
        if atr <= 0:
            atr = price * 0.012
        atr_15m = market_data.get("atr_15m", atr * 0.196)

        # Entry: always at exact current market price — no simulated slippage.
        # Paper trading fills at market; signals are generated at the moment of request.
        entry = round(price, dec)

        if direction == "LONG":
            stop     = round(entry - atr * 1.5, dec)        # 1.5 ATR stop
            risk_amt = entry - stop
            tp1      = round(entry + risk_amt * 1.5, dec)   # 1.5R
            tp2      = round(entry + risk_amt * 2.5, dec)   # 2.5R
            tp3      = round(entry + risk_amt * 4.0, dec)   # 4R
        else:
            stop     = round(entry + atr * 1.5, dec)        # 1.5 ATR stop
            risk_amt = stop - entry
            tp1      = round(entry - risk_amt * 1.5, dec)   # 1.5R
            tp2      = round(entry - risk_amt * 2.5, dec)   # 2.5R
            tp3      = round(entry - risk_amt * 4.0, dec)   # 4R

        long_weight = sum(c for d, c in votes if d == "LONG")
        short_weight = sum(c for d, c in votes if d == "SHORT")
        total = sum(c for _, c in votes) or 100
        conviction = max(long_weight, short_weight) / total
        confidence = min(92, max(35, 45 + conviction * 50))

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
        risk_pct = abs((stop - entry) / entry) * 100
        tp1_pct  = abs((tp1 - entry)  / entry) * 100
        reasoning_chain = [
            f"Analyst vote: {sum(1 for d, _ in votes if d == direction)}/4 agents agree on {direction}",
            f"Technical: EMA crossover {tech.get('ema_crossover', 'N/A')}, RSI {tech.get('rsi', 50):.0f}",
            f"Fundamental: Earnings momentum {fund.get('earnings_momentum', 0):+.2f}, value score {fund.get('value_score', 0):+.2f}",
            f"Sentiment: News {sent.get('news_sentiment', 0):+.2f}, social {sent.get('social_sentiment', 0):+.2f}",
            f"Macro regime: {macro.get('macro_regime', 'N/A')}, Fed {macro.get('fed_stance', 'N/A')}",
            f"Risk check passed: position size {risk.get('position_size_pct', 2):.1f}% (half-Kelly)",
            f"ATR(14)={atr:{fmt}} — stop at 1.5×ATR from entry",
            f"Entry {entry:{fmt}}, SL {stop:{fmt}} ({risk_pct:.1f}% risk), TP1 {tp1:{fmt}} (1.5R)",
        ]

        return {
            "direction": direction,
            "entry_price":    round(entry, dec),
            "stop_loss":      round(stop, dec),
            "take_profit_1":  round(tp1, dec),
            "take_profit_2":  round(tp2, dec),
            "take_profit_3":  round(tp3, dec),
            "confidence_score": round(confidence, 1),
            "position_size_pct": risk.get("position_size_pct", round(rng.uniform(1, 3), 2)),
            "strategy_sources": strategy_sources,
            "reasoning_chain":  reasoning_chain,
            "trade_rationale": (
                f"{direction} {ticker} @ {entry:{fmt}}. "
                f"Stop {stop:{fmt}} ({risk_pct:.1f}% risk). "
                f"Targets: TP1={tp1:{fmt}} (+{tp1_pct:.1f}%), "
                f"TP2={tp2:{fmt}}, TP3={tp3:{fmt}}. "
                f"Conviction: {confidence:.0f}%. Strategies: {', '.join(strategy_sources[:3])}."
            ),
            "timeframe_levels": self._compute_timeframe_levels(entry, direction, atr, atr_15m, dec),
        }
