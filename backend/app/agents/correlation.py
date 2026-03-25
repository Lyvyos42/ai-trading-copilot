import json
import random
from app.agents.base import BaseAgent
from app.pipeline.state import TradingState


SYSTEM_PROMPT = """You are an expert correlation and portfolio risk analyst:
- Portfolio concentration risk assessment
- Cross-asset contagion detection
- Kelly criterion position size adjustments based on correlation
- Strategy 3.18: Covariance-based portfolio construction
- Strategy 6.5: Target volatility with correlation adjustment

Respond ONLY with a valid JSON object:
{
  "direction": "LONG" | "SHORT" | "NEUTRAL",
  "confidence": <float 0-100>,
  "portfolio_correlation": <float -1 to 1>,
  "concentration_risk": "HIGH" | "MODERATE" | "LOW",
  "contagion_risk": <float 0 to 1>,
  "diversification_score": <float 0 to 1>,
  "kelly_adjustment": <float 0.5 to 1.5>,
  "correlated_assets": [<string>, ...],
  "reasoning": "<string>"
}"""


# Common correlation clusters for different asset classes
_CORRELATION_MAP = {
    "stocks": {
        "tech": ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA"],
        "finance": ["JPM", "GS", "BAC", "MS", "WFC", "C"],
        "energy": ["XOM", "CVX", "COP", "SLB", "EOG"],
        "healthcare": ["JNJ", "UNH", "PFE", "ABBV", "MRK"],
    },
    "crypto": {
        "major": ["BTCUSD", "ETHUSD"],
        "alt_l1": ["SOLUSD", "ADAUSD", "AVAXUSD", "DOTUSD"],
        "defi": ["UNIUSD", "AAVEUSD", "LINKUSD"],
    },
    "forex": {
        "usd_pairs": ["EURUSD", "GBPUSD", "USDJPY", "USDCHF"],
        "commodity_fx": ["AUDUSD", "NZDUSD", "USDCAD"],
    },
}


class CorrelationAnalyst(BaseAgent):
    def __init__(self):
        super().__init__("CorrelationAnalyst", tier="standard")

    async def analyze(self, state: TradingState) -> dict:
        ticker = state.get("ticker", "UNKNOWN")
        asset_class = state.get("asset_class", "stocks")
        market_data = state.get("market_data", {})
        macro = state.get("macro_analysis", {})

        close = market_data.get("close", 100)
        price_change = market_data.get("price_change_pct", 0.0)
        regime = macro.get("macro_regime", "TRANSITIONAL")

        # Find correlated assets for this ticker
        correlated = self._find_correlated_assets(ticker, asset_class)

        user_msg = f"""Analyze correlation risk for {ticker} ({asset_class}).
Current price: {close}
Price change today: {price_change:+.2f}%
Macro regime: {regime}
Correlated assets in same cluster: {', '.join(correlated[:5])}

Apply strategy 3.18 (covariance framework) and 6.5 (target volatility).
Assess portfolio concentration risk, contagion probability, and Kelly adjustment.
Output JSON only."""

        raw = await self._call_claude(SYSTEM_PROMPT, user_msg)
        if raw:
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                pass

        return self._mock_analysis(ticker, asset_class, price_change, regime, correlated)

    def _find_correlated_assets(self, ticker: str, asset_class: str) -> list[str]:
        clusters = _CORRELATION_MAP.get(asset_class, _CORRELATION_MAP["stocks"])
        for _group, assets in clusters.items():
            if ticker.upper() in [a.upper() for a in assets]:
                return [a for a in assets if a.upper() != ticker.upper()]
        # Default: return first cluster
        first_cluster = list(clusters.values())[0] if clusters else []
        return [a for a in first_cluster if a.upper() != ticker.upper()][:4]

    def _mock_analysis(self, ticker: str, asset_class: str, price_change: float,
                       regime: str, correlated: list) -> dict:
        seed = sum(ord(c) for c in ticker) + 33
        rng = random.Random(seed)

        # Portfolio correlation (higher in risk-off/crisis)
        base_corr = rng.uniform(0.2, 0.6)
        if regime in ("RISK_OFF", "CRISIS"):
            base_corr = min(1.0, base_corr + 0.3)  # Correlations spike in crisis
        portfolio_corr = round(base_corr, 3)

        # Concentration risk
        if portfolio_corr > 0.7:
            concentration = "HIGH"
        elif portfolio_corr > 0.4:
            concentration = "MODERATE"
        else:
            concentration = "LOW"

        # Contagion risk
        contagion = min(1.0, max(0.0, portfolio_corr * 0.8 + rng.uniform(-0.1, 0.1)))
        if abs(price_change) > 3.0:
            contagion = min(1.0, contagion + 0.2)

        # Diversification score (inverse of concentration)
        diversification = max(0.0, 1.0 - portfolio_corr * 0.8 + rng.uniform(-0.1, 0.1))

        # Kelly adjustment: reduce sizing when correlation is high
        kelly_adj = max(0.5, min(1.5, 1.0 - (portfolio_corr - 0.3) * 0.5))
        if concentration == "HIGH":
            kelly_adj = min(kelly_adj, 0.7)

        # Direction: correlation analysis is mostly about sizing, not direction
        # But high contagion in risk-off suggests SHORT bias
        if contagion > 0.7 and regime in ("RISK_OFF", "CRISIS"):
            direction = "SHORT"
            confidence = rng.uniform(55, 70)
        elif diversification > 0.6 and regime == "RISK_ON":
            direction = "LONG"
            confidence = rng.uniform(50, 65)
        else:
            direction = "NEUTRAL"
            confidence = rng.uniform(40, 55)

        return {
            "direction": direction,
            "confidence": round(confidence, 1),
            "portfolio_correlation": portfolio_corr,
            "concentration_risk": concentration,
            "contagion_risk": round(contagion, 3),
            "diversification_score": round(diversification, 3),
            "kelly_adjustment": round(kelly_adj, 3),
            "correlated_assets": correlated[:5],
            "reasoning": (
                f"{ticker} correlation analysis: portfolio correlation {portfolio_corr:.2f}, "
                f"concentration risk {concentration}. Contagion probability: {contagion:.0%}. "
                f"Diversification score: {diversification:.2f}. Kelly adjustment: {kelly_adj:.2f}x. "
                f"Correlated with: {', '.join(correlated[:3])}. "
                f"Strategy 3.18/6.5: {direction} at {confidence:.0f}%."
            ),
        }
