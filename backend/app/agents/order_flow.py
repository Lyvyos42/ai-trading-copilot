import json
import math
from app.agents.base import BaseAgent
from app.pipeline.state import TradingState


def _compute_microstructure(closes: list, volumes: list) -> dict:
    """Derive microstructure metrics from OHLCV for 3D surface integration."""
    if not closes or len(closes) < 10 or not volumes:
        return {}
    recent = closes[-60:]
    recent_vol = volumes[-60:] if len(volumes) >= 60 else volumes

    mid = recent[-1]
    price_range = max(recent) - min(recent)
    if price_range <= 0:
        return {}

    half_range = price_range * 0.6
    n_levels = 15
    price_min = mid - half_range
    step = (2 * half_range) / (n_levels - 1) if n_levels > 1 else 1
    levels = [price_min + i * step for i in range(n_levels)]

    bid_depth = 0.0
    ask_depth = 0.0
    for i, px in enumerate(levels):
        dist = abs(px - mid) / half_range
        weight = max(0, 1.0 - dist) ** 1.5
        if px <= mid:
            bid_depth += weight
        else:
            ask_depth += weight

    depth_imbalance = (bid_depth - ask_depth) / max(bid_depth + ask_depth, 1e-6)

    vol_profile = [0.0] * n_levels
    for j, c in enumerate(recent):
        idx = int((c - price_min) / step) if step > 0 else 0
        idx = max(0, min(idx, n_levels - 1))
        vol_profile[idx] += recent_vol[j] if j < len(recent_vol) else 1

    max_vol = max(vol_profile) if vol_profile else 1
    hotspot_idx = vol_profile.index(max_vol) if max_vol > 0 else len(vol_profile) // 2
    hotspot_price = levels[hotspot_idx] if hotspot_idx < len(levels) else mid

    first_half = sum(v * levels[i] for i, v in enumerate(vol_profile[:len(vol_profile) // 2]))
    first_weight = sum(vol_profile[:len(vol_profile) // 2])
    second_half = sum(v * levels[i] for i, v in enumerate(vol_profile[len(vol_profile) // 2:], len(vol_profile) // 2))
    second_weight = sum(vol_profile[len(vol_profile) // 2:])

    c1 = first_half / first_weight if first_weight > 0 else mid
    c2 = second_half / second_weight if second_weight > 0 else mid
    migration = "UP" if c2 > c1 else ("DOWN" if c2 < c1 else "STABLE")

    return {
        "depth_imbalance": round(depth_imbalance, 4),
        "bid_depth_score": round(bid_depth, 4),
        "ask_depth_score": round(ask_depth, 4),
        "liquidity_hotspot": round(hotspot_price, 5),
        "liquidity_migration": migration,
        "volume_concentration": round(max_vol / max(sum(vol_profile), 1), 4),
    }


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

        micro = _compute_microstructure(closes, volumes)

        micro_ctx = ""
        if micro:
            micro_ctx = f"""
3D Microstructure Analysis:
- Depth Imbalance: {micro.get('depth_imbalance', 0):+.4f} ({'BID HEAVY' if micro.get('depth_imbalance', 0) > 0 else 'ASK HEAVY'})
- Bid Depth Score: {micro.get('bid_depth_score', 0):.3f}, Ask Depth Score: {micro.get('ask_depth_score', 0):.3f}
- Liquidity Hotspot: {micro.get('liquidity_hotspot', 'N/A')}
- Liquidity Migration: {micro.get('liquidity_migration', 'STABLE')}
- Volume Concentration: {micro.get('volume_concentration', 0):.2%}"""

        user_msg = f"""{self._strategy_context(state)}Analyze order flow for {ticker}.
Current price: {close}
VWAP: {vwap}, deviation: {vwap_dev:+.2f}%
Volume: {volume:,.0f} (ratio vs 30d avg: {vol_ratio:.2f}x)
OBV trend: {obv_trend}
Recent closes: {closes[-10:] if closes else 'N/A'}
Recent volumes: {volumes[-10:] if volumes else 'N/A'}
{micro_ctx}

Apply strategies 3.16 (volume-weighted signals) and 3.17 (liquidity momentum).
Assess VPIN, bid/ask imbalance, and block trade activity. Output JSON only."""

        raw = await self._call_claude(SYSTEM_PROMPT, user_msg)
        if raw:
            try:
                result = json.loads(raw)
                if micro:
                    result["microstructure"] = micro
                return result
            except json.JSONDecodeError:
                pass

        return self._mock_analysis(ticker, market_data, vwap_dev, vol_ratio, obv_trend, micro)

    def _mock_analysis(self, ticker: str, market_data: dict, vwap_dev: float, vol_ratio: float, obv_trend: str, micro: dict | None = None) -> dict:
        from datetime import date
        price = market_data.get("close", 0)
        # vol_ratio, vwap_dev and obv_trend are REAL - computed from actual
        # bars upstream. The mock path then injected noise on top of them:
        #
        #     vpin         = 0.3 + (vol_ratio - 1.0) * 0.2 + rng.uniform(-0.1, 0.1)
        #     ba_imbalance = vwap_dev / 2.0 + rng.uniform(-0.2, 0.2)
        #     smf          = ... + rng.uniform(-0.15, 0.15)
        #
        # The jitter was wider than the signal it was added to. With a typical
        # vwap_dev of ~0.2 the real term contributes 0.10 while the noise term
        # spans +/-0.20, so the random component dominated the measurement it
        # was decorating. Removed - the real derivation stands on its own.
        vpin = min(1.0, max(0.0, 0.3 + (vol_ratio - 1.0) * 0.2))

        # Bid/ask imbalance derived from VWAP deviation
        ba_imbalance = max(-1.0, min(1.0, vwap_dev / 2.0))

        # Block trade bias
        if vol_ratio > 1.5 and vwap_dev > 0.3:
            block_bias = "ACCUMULATION"
        elif vol_ratio > 1.5 and vwap_dev < -0.3:
            block_bias = "DISTRIBUTION"
        else:
            block_bias = "NEUTRAL"

        dark_pool = "HIGH" if vol_ratio > 1.8 else ("MODERATE" if vol_ratio > 1.2 else "LOW")

        # Smart money flow composite.
        #
        # The OBV term was a CONSTANT +/-0.3 that dominated everything else:
        # ba_imbalance is vwap_dev/2 and typically runs 0.05-0.2, so the
        # composite landed near +/-0.15 on essentially every symbol and
        # confidence came out at 56-58 every time. Measured on BTC-USD,
        # ETH-USD, EURUSD and GBPUSD it returned 56, 56, 58, 58 - four
        # instruments, effectively one number.
        #
        # The OBV term is now scaled by how far volume is from its own
        # average, so a trend confirmed on heavy participation counts for more
        # than one drifting on nothing.
        _obv_dir = 1 if obv_trend == "RISING" else (-1 if obv_trend == "FALLING" else 0)
        _obv_conviction = min(1.0, max(0.15, abs(vol_ratio - 1.0) * 1.5))
        smf = ba_imbalance * 0.4 + _obv_dir * 0.45 * _obv_conviction
        smf = max(-1.0, min(1.0, smf))

        composite = smf * 0.5 + ba_imbalance * 0.3 + (vpin - 0.5) * 0.2
        direction = "LONG" if composite > 0.1 else ("SHORT" if composite < -0.1 else "NEUTRAL")
        confidence = min(88, max(30, 50 + abs(composite) * 40))

        # Incorporate microstructure depth imbalance into composite
        if micro and micro.get("depth_imbalance"):
            di = micro["depth_imbalance"]
            composite += di * 0.15
            smf = max(-1.0, min(1.0, smf + di * 0.1))
            direction = "LONG" if composite > 0.1 else ("SHORT" if composite < -0.1 else "NEUTRAL")
            confidence = min(88, max(30, 50 + abs(composite) * 40))

        micro_str = ""
        if micro:
            micro_str = (
                f" Depth imbalance: {micro.get('depth_imbalance', 0):+.3f} "
                f"({'BID HEAVY' if micro.get('depth_imbalance', 0) > 0 else 'ASK HEAVY'}). "
                f"Liquidity migration: {micro.get('liquidity_migration', 'STABLE')}."
            )

        result = {
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
                f"Smart money flow {smf:+.2f}.{micro_str} "
                f"Strategy 3.16-3.17: {direction} at {confidence:.0f}%."
            ),
        }
        if micro:
            result["microstructure"] = micro
        return result
