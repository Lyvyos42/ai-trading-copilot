import json
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
        "usd_pairs": ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "EURJPY"],
        "commodity_fx": ["AUDUSD", "NZDUSD", "USDCAD"],
    },
    "fx": {
        "usd_pairs": ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "EURJPY"],
        "commodity_fx": ["AUDUSD", "NZDUSD", "USDCAD"],
    },
    "commodities": {
        "metals": ["XAUUSD", "XAGUSD", "XPTUSD", "GC=F", "SI=F"],
        "energy": ["USOIL", "UKOIL", "NATGAS", "CL=F", "BZ=F"],
    },
    "indices": {
        "us": ["SPX", "NDX", "DJIA", "US500", "US100", "US30", "^GSPC", "^NDX"],
        "europe_asia": ["FTSE", "DAX", "CAC40", "JPN225", "NKY"],
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

        strategy_ctx = self._strategy_context(state)
        user_msg = f"""{strategy_ctx}Analyze correlation risk for {ticker} ({asset_class}).
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
        """Cluster membership is real; the correlation numbers were not.

        Removed:

            base_corr     = rng.uniform(0.2, 0.6)
            contagion     = portfolio_corr * 0.8 + rng.uniform(-0.1, 0.1)
            diversification = 1.0 - portfolio_corr * 0.8 + rng.uniform(-0.1, 0.1)
            confidence    = rng.uniform(55, 70)

        A correlation coefficient requires two price series. This agent is
        handed one - the ticker being analysed - and never fetches the other
        side, so it cannot compute a correlation and previously drew one from
        a uniform distribution instead. Contagion and diversification were
        then derived from that invented figure, which made them invented too.

        What survives is genuinely known: which assets sit in the same
        published cluster as this one (a static, curated map). That is useful
        context for a trader holding several positions, and it is reported as
        cluster membership rather than dressed up as a measured coefficient.
        """
        return self.abstain(
            f"{ticker} sits in a cluster with {', '.join(correlated[:4]) or 'no mapped peers'}. "
            f"No correlation coefficient is reported: computing one needs the price "
            f"history of both legs and this agent receives only {ticker}. Cluster "
            f"membership is published as context, not as a measured correlation.",
            correlated_assets=correlated[:6],
            portfolio_correlation=None,
            contagion_risk=None,
            diversification_score=None,
            cluster_regime=regime,
        )
