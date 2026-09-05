import json
import math
from app.agents.base import BaseAgent, nz
from app.pipeline.state import TradingState


SYSTEM_PROMPT = """You are a quantitative validation analyst specializing in statistical rigor:
- 5-year historical backtest validation for proposed signals
- P-value and statistical significance testing
- Sample size adequacy (n-samples)
- Strategy Sharpe ratio estimation
- Win rate and expectancy calculation
- Regime-adjusted performance metrics

You review outputs from 7 analyst agents and validate whether the proposed signal
has statistically significant historical support.

Respond ONLY with a valid JSON object:
{
  "direction": "LONG" | "SHORT" | "NEUTRAL",
  "confidence": <float 0-100>,
  "backtest_win_rate": <float 0 to 1>,
  "backtest_n_samples": <int>,
  "p_value": <float>,
  "sharpe_estimate": <float>,
  "expectancy_per_trade": <float>,
  "statistical_edge": <bool>,
  "regime_adjusted_wr": <float 0 to 1>,
  "validation_notes": [<string>, ...],
  "reasoning": "<string>"
}"""



class QuantAnalyst(BaseAgent):
    def __init__(self):
        super().__init__("QuantAnalyst", tier="standard")

    async def analyze(self, state: TradingState) -> dict:
        ticker = state.get("ticker", "UNKNOWN")
        market_data = state.get("market_data", {})

        # Gather all analyst directions and confidences
        analysts = {}
        for key in ("fundamental_analysis", "technical_analysis", "sentiment_analysis",
                     "macro_analysis", "order_flow_analysis", "regime_change_analysis",
                     "correlation_analysis"):
            analysis = state.get(key, {})
            if analysis:
                name = key.replace("_analysis", "")
                analysts[name] = {
                    "direction": analysis.get("direction", "NEUTRAL"),
                    "confidence": analysis.get("confidence", 50),
                }

        # Consensus summary
        long_count = sum(1 for a in analysts.values() if a["direction"] == "LONG")
        short_count = sum(1 for a in analysts.values() if a["direction"] == "SHORT")
        avg_conf = sum(a["confidence"] for a in analysts.values()) / max(len(analysts), 1)
        consensus_dir = "LONG" if long_count > short_count else ("SHORT" if short_count > long_count else "NEUTRAL")

        close = market_data.get("close", 100)
        # close can be None on a dead feed; nz() also guards the eager default.
        close = nz(market_data, "close", 0.0)
        atr = nz(market_data, "atr", close * 0.012)

        analyst_summary = "\n".join(
            f"  - {name}: {a['direction']} ({a['confidence']:.0f}%)"
            for name, a in analysts.items()
        )

        strategy_ctx = self._strategy_context(state)
        user_msg = f"""{strategy_ctx}Validate the statistical edge for {ticker}.

ANALYST CONSENSUS: {long_count} LONG / {short_count} SHORT / {len(analysts) - long_count - short_count} NEUTRAL
Average confidence: {avg_conf:.1f}%
Consensus direction: {consensus_dir}

Individual analysts:
{analyst_summary}

Current price: {close}
ATR(14): {atr:.4f}

Assess:
1. Historical win rate for similar setups (5yr backtest estimate)
2. P-value: is this edge statistically significant at p < 0.05?
3. Sharpe ratio estimate
4. Whether the sample size is adequate
5. Regime-adjusted performance
Output JSON only."""

        raw = await self._call_claude(SYSTEM_PROMPT, user_msg, state=state)
        if raw:
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                pass

        return self._mock_analysis(ticker, consensus_dir, avg_conf, long_count, short_count, len(analysts))

    def _mock_analysis(self, ticker: str, consensus_dir: str, avg_conf: float,
                       long_count: int, short_count: int, total: int) -> dict:
        """No backtest was run, so no backtest is reported.

        This method used to manufacture an entire track record:

            base_wr   = 0.45 + agreement * 0.15 + rng.uniform(-0.05, 0.05)
            n_samples = rng.randint(80, 350)
            z         = abs(win_rate - 0.5) / sqrt(0.25 / n_samples)
            statistical_edge = p_value < 0.05 and win_rate > 0.52

        A win rate and a sample size were invented, a p-value was computed
        from those invented numbers, and the pair was presented to the user
        as a significance verdict - with validation notes reasoning about
        them ("p-value 0.03 < 0.05", "Sharpe 1.8 suggests strong risk-
        adjusted returns"). No historical data was consulted at any point.

        The honest output when this agent has no backtest to draw on is that
        it has no backtest. statistical_edge is None - UNKNOWN - rather than
        False, because False would claim we looked and found nothing, which
        is a different and equally untrue statement.

        Analyst agreement IS real - it is computed from the other agents'
        actual votes - so it is still reported, clearly labelled as
        agreement and not as validation.
        """
        agreement = max(long_count, short_count) / max(total, 1)
        return self.abstain(
            f"{ticker}: no backtest available for this setup, so no statistical "
            f"validation is claimed. Analyst agreement is {agreement:.0%} "
            f"({long_count} long / {short_count} short of {total}), which "
            f"measures consensus among the other agents - not historical edge.",
            backtest_win_rate=None,
            backtest_n_samples=0,
            p_value=None,
            sharpe_estimate=None,
            expectancy_per_trade=None,
            statistical_edge=None,
            regime_adjusted_wr=None,
            analyst_agreement=round(agreement, 3),
            validation_notes=[
                "No backtest run for this setup - edge is UNMEASURED, not zero.",
            ],
        )
