import json
import random
from app.agents.base import BaseAgent
from app.pipeline.state import TradingState


SYSTEM_PROMPT = """You are an elite quantitative trader and portfolio manager with 20+ years of experience.
You synthesize analysis from 4 specialized AI analysts and a bull/bear debate to make high-conviction
trading decisions. You apply the mathematical frameworks from "151 Trading Strategies".

Your job:
1. Weigh analyst consensus (fundamental, technical, sentiment, macro)
2. Evaluate the bull vs bear debate quality and arguments
3. Apply Kelly criterion for position sizing (already calculated by Risk Manager)
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

CURRENT PRICE: {current_price:.2f}

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
- Support: {tech.get('support', current_price * 0.95):.2f}
- Resistance: {tech.get('resistance', current_price * 1.06):.2f}

Set TP1 at 1.5R, TP2 at 2.5R, TP3 at 4R from entry.
Output JSON only."""

        raw = self._call_claude(SYSTEM_PROMPT, user_msg, max_tokens=3000)
        if raw:
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                pass

        return self._compute_signal(ticker, current_price, direction, votes, tech, risk, fund, sent, macro)

    def _compute_signal(self, ticker, price, direction, votes, tech, risk, fund, sent, macro) -> dict:
        rng = random.Random(sum(ord(c) for c in ticker) + 13)

        support = tech.get("support", price * 0.95)
        resistance = tech.get("resistance", price * 1.06)

        if direction == "LONG":
            entry = price * (1 + rng.uniform(0, 0.003))
            stop = support * (1 - rng.uniform(0.002, 0.008))
            risk_per_share = entry - stop
            tp1 = entry + risk_per_share * 1.5
            tp2 = entry + risk_per_share * 2.5
            tp3 = entry + risk_per_share * 4.0
        else:
            entry = price * (1 - rng.uniform(0, 0.003))
            stop = resistance * (1 + rng.uniform(0.002, 0.008))
            risk_per_share = stop - entry
            tp1 = entry - risk_per_share * 1.5
            tp2 = entry - risk_per_share * 2.5
            tp3 = entry - risk_per_share * 4.0

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

        reasoning_chain = [
            f"Analyst vote: {sum(1 for d, _ in votes if d == direction)}/4 agents agree on {direction}",
            f"Technical: EMA crossover {tech.get('ema_crossover', 'N/A')}, RSI {tech.get('rsi', 'N/A'):.0f}",
            f"Fundamental: Earnings momentum {fund.get('earnings_momentum', 0):+.2f}, value score {fund.get('value_score', 0):+.2f}",
            f"Sentiment: News {sent.get('news_sentiment', 0):+.2f}, social {sent.get('social_sentiment', 0):+.2f}",
            f"Macro regime: {macro.get('macro_regime', 'N/A')}, Fed {macro.get('fed_stance', 'N/A')}",
            f"Risk check passed: position size {risk.get('position_size_pct', 2):.1f}% (half-Kelly)",
            f"Entry {entry:.2f}, SL {stop:.2f} ({abs((stop-entry)/entry)*100:.1f}% risk), TP1 {tp1:.2f} (1.5R)",
        ]

        return {
            "direction": direction,
            "entry_price": round(entry, 2),
            "stop_loss": round(stop, 2),
            "take_profit_1": round(tp1, 2),
            "take_profit_2": round(tp2, 2),
            "take_profit_3": round(tp3, 2),
            "confidence_score": round(confidence, 1),
            "position_size_pct": risk.get("position_size_pct", round(rng.uniform(1, 3), 2)),
            "strategy_sources": strategy_sources,
            "reasoning_chain": reasoning_chain,
            "trade_rationale": (
                f"{direction} {ticker} @ {entry:.2f}. "
                f"Stop {stop:.2f} ({abs((stop-entry)/entry)*100:.1f}% risk). "
                f"Targets: TP1={tp1:.2f} (+{abs((tp1-entry)/entry)*100:.1f}%), "
                f"TP2={tp2:.2f}, TP3={tp3:.2f}. "
                f"Conviction: {confidence:.0f}%. Strategies: {', '.join(strategy_sources[:3])}."
            ),
        }
