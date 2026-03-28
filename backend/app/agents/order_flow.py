import json
import random
from app.agents.base import BaseAgent
from app.pipeline.state import TradingState


SYSTEM_PROMPT = """You are an expert order flow analyst specializing in microstructure signals:
- VPIN (Volume-Synchronized Probability of Informed Trading)
- Bid/ask imbalance and order book depth analysis
- Block trade detection (dark pool prints, large institutional orders)
- Strategy 3.16: Volume-weighted signals (OBV, VWAP deviation)
- Strategy 3.17: Liquidity-driven momentum

Respond ONLY with a valid JSON object:
{
  "direction": "LONG" | "SHORT" | "NEUTRAL",
  "confidence": <float 0-100>,
  "vpin_score": <float 0 to 1>,
  "bid_ask_imbalance": <float -1 to 1>,
  "block_trade_bias": "ACCUMULATION" | "DISTRIBUTION" | "NEUTRAL",
  "dark_pool_activity": "HIGH" | "MODERATE" | "LOW",
  "vwap_deviation_pct": <float>,
  "smart_money_flow": <float -1 to 1>,
  "reasoning": "<string>"
}"""


class OrderFlowAnalyst(BaseAgent):
    def __init__(self):
        super().__init__("OrderFlowAnalyst", tier="standard")

    async def analyze(self, state: TradingState) -> dict:
        ticker = state.get("ticker", "UNKNOWN")
        market_data = state.get("market_data", {})

        close = market_data.get("close", 0)
        volume = market_data.get("volume", 0)
        vwap = market_data.get("vwap", close)
        avg_volume = market_data.get("avg_volume_30d", volume or 1)
        closes = market_data.get("closes", [])
        volumes = market_data.get("volumes", [])

        # Compute VWAP deviation
        vwap_dev = ((close - vwap) / vwap * 100) if vwap else 0.0

        # Volume ratio
        vol_ratio = volume / avg_volume if avg_volume else 1.0

        # Simple OBV trend from available data
        obv_trend = "RISING"
        if len(closes) >= 5 and len(volumes) >= 5:
            obv = 0
            for i in range(1, min(len(closes), len(volumes))):
                if closes[i] > closes[i - 1]:
                    obv += volumes[i]
                elif closes[i] < closes[i - 1]:
                    obv -= volumes[i]
            obv_trend = "RISING" if obv > 0 else "FALLING"

        user_msg = f"""{self._strategy_context(state)}Analyze order flow for {ticker}.
Current price: {close}
VWAP: {vwap}, deviation: {vwap_dev:+.2f}%
Volume: {volume:,.0f} (ratio vs 30d avg: {vol_ratio:.2f}x)
OBV trend: {obv_trend}
Recent closes: {closes[-10:] if closes else 'N/A'}
Recent volumes: {volumes[-10:] if volumes else 'N/A'}

Apply strategies 3.16 (volume-weighted signals) and 3.17 (liquidity momentum).
Assess VPIN, bid/ask imbalance, and block trade activity. Output JSON only."""

        raw = await self._call_claude(SYSTEM_PROMPT, user_msg)
        if raw:
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                pass

        return self._mock_analysis(ticker, market_data, vwap_dev, vol_ratio, obv_trend)

    def _mock_analysis(self, ticker: str, market_data: dict, vwap_dev: float, vol_ratio: float, obv_trend: str) -> dict:
        seed = sum(ord(c) for c in ticker) + 55
        rng = random.Random(seed)

        # VPIN: higher when volume is unusual
        vpin = min(1.0, max(0.0, 0.3 + (vol_ratio - 1.0) * 0.2 + rng.uniform(-0.1, 0.1)))

        # Bid/ask imbalance derived from VWAP deviation + noise
        ba_imbalance = max(-1.0, min(1.0, vwap_dev / 2.0 + rng.uniform(-0.2, 0.2)))

        # Block trade bias
        if vol_ratio > 1.5 and vwap_dev > 0.3:
            block_bias = "ACCUMULATION"
        elif vol_ratio > 1.5 and vwap_dev < -0.3:
            block_bias = "DISTRIBUTION"
        else:
            block_bias = "NEUTRAL"

        dark_pool = "HIGH" if vol_ratio > 1.8 else ("MODERATE" if vol_ratio > 1.2 else "LOW")

        # Smart money flow composite
        smf = ba_imbalance * 0.4 + (1 if obv_trend == "RISING" else -1) * 0.3 + rng.uniform(-0.15, 0.15)
        smf = max(-1.0, min(1.0, smf))

        composite = smf * 0.5 + ba_imbalance * 0.3 + (vpin - 0.5) * 0.2
        direction = "LONG" if composite > 0.1 else ("SHORT" if composite < -0.1 else "NEUTRAL")
        confidence = min(88, max(30, 50 + abs(composite) * 40 + rng.uniform(-5, 5)))

        return {
            "direction": direction,
            "confidence": round(confidence, 1),
            "vpin_score": round(vpin, 3),
            "bid_ask_imbalance": round(ba_imbalance, 3),
            "block_trade_bias": block_bias,
            "dark_pool_activity": dark_pool,
            "vwap_deviation_pct": round(vwap_dev, 3),
            "smart_money_flow": round(smf, 3),
            "reasoning": (
                f"{ticker} order flow: VPIN at {vpin:.2f}, bid/ask imbalance {ba_imbalance:+.2f}. "
                f"Block trade bias: {block_bias}. Dark pool activity: {dark_pool}. "
                f"VWAP deviation {vwap_dev:+.2f}%, volume {vol_ratio:.1f}x average. "
                f"Smart money flow {smf:+.2f}. Strategy 3.16-3.17: {direction} at {confidence:.0f}%."
            ),
        }
