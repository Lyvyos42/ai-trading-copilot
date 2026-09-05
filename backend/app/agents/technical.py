import json
import numpy as np
from app.agents.base import BaseAgent
from app.pipeline.state import TradingState


def _price_decimals(price: float) -> int:
    if price < 0.001:  return 6
    if price < 0.1:    return 5
    if price < 10:     return 4
    if price < 100:    return 3
    return 2


SYSTEM_PROMPT = """You are an expert quantitative technical analyst applying price-action strategies
from "151 Trading Strategies":
- Strategy 3.1: Price Momentum (12-1 month cross-sectional return)
- Strategy 3.9: Mean Reversion (cluster-demeaned Z-score entry)
- Strategy 3.11-3.13: SMA/EMA crossover systems
- Strategy 3.14: Support/Resistance breakout
- Strategy 3.15: Channel breakout

Respond ONLY with a valid JSON object with these exact keys:
{
  "direction": "LONG" | "SHORT" | "NEUTRAL",
  "confidence": <float 0-100>,
  "trend_signal": "BULLISH" | "BEARISH" | "SIDEWAYS",
  "momentum_score": <float -1 to 1>,
  "mean_reversion_signal": <float -1 to 1>,
  "support": <float>,
  "resistance": <float>,
  "rsi": <float>,
  "ema_crossover": "BULLISH" | "BEARISH" | "NEUTRAL",
  "reasoning": "<string>"
}"""


def _zscore(prices: list[float], window: int = 20) -> float:
    if len(prices) < window:
        return 0.0
    arr = np.array(prices[-window:])
    mean = arr.mean()
    std = arr.std()
    if std == 0:
        return 0.0
    return float((prices[-1] - mean) / std)


def _ema(prices: list[float], period: int) -> float:
    if len(prices) < period:
        return prices[-1] if prices else 0.0
    k = 2 / (period + 1)
    ema = prices[0]
    for p in prices[1:]:
        ema = p * k + ema * (1 - k)
    return ema


def _rsi(prices: list[float], period: int = 14) -> float:
    if len(prices) < period + 1:
        return 50.0
    deltas = np.diff(prices[-period - 1:])
    gains = deltas[deltas > 0].mean() if any(d > 0 for d in deltas) else 0
    losses = -deltas[deltas < 0].mean() if any(d < 0 for d in deltas) else 1e-9
    rs = gains / losses
    return float(100 - 100 / (1 + rs))


class TechnicalAnalyst(BaseAgent):
    def __init__(self):
        super().__init__("TechnicalAnalyst", tier="standard")

    async def analyze(self, state: TradingState) -> dict:
        ticker = state.get("ticker", "UNKNOWN")
        market_data = state.get("market_data", {})
        closes = market_data.get("closes", [])
        highs = market_data.get("highs", [])
        lows = market_data.get("lows", [])

        if not closes:
            return self._mock_analysis(ticker)

        # Compute indicators locally
        ema12 = _ema(closes, 12)
        ema26 = _ema(closes, 26)
        rsi = _rsi(closes)
        zscore = _zscore(closes, 20)

        # Momentum: 12-1 month return (strategy 3.1)
        if len(closes) >= 252:
            momentum = (closes[-22] - closes[-252]) / closes[-252]
        elif len(closes) > 1:
            momentum = (closes[-1] - closes[0]) / closes[0]
        else:
            momentum = 0.0

        current_price = closes[-1] if closes else 100.0
        dec = _price_decimals(current_price)
        support = round(min(lows[-20:]) if len(lows) >= 20 else current_price * 0.95, dec)
        resistance = round(max(highs[-20:]) if len(highs) >= 20 else current_price * 1.05, dec)
        atr = market_data.get("atr", current_price * 0.012)

        ema_cross = "BULLISH" if ema12 > ema26 else ("BEARISH" if ema12 < ema26 else "NEUTRAL")

        user_msg = (
            f"{self._strategy_context(state)}"
            f"Analyze {ticker} technically.\n"
            f"EMA12={ema12:.{dec}f}, EMA26={ema26:.{dec}f}, RSI={rsi:.1f}\n"
            f"Z-Score (20d)={zscore:.2f} (mean reversion signal, strategy 3.9)\n"
            f"Momentum (12-1m)={momentum:.3f} (strategy 3.1)\n"
            f"ATR(14)={atr:.{dec}f}\n"
            f"Support={support:.{dec}f}, Resistance={resistance:.{dec}f}\n"
            f"EMA Crossover: {ema_cross} (strategy 3.11-3.13)\n"
            f"Current price: {current_price:.{dec}f}\n"
            f"Output JSON only."
        )

        raw = await self._call_claude(SYSTEM_PROMPT, user_msg)
        if raw:
            try:
                result = json.loads(raw)
                result.setdefault("support", support)
                result.setdefault("resistance", resistance)
                result.setdefault("rsi", round(rsi, 1))
                result.setdefault("atr", atr)
                return result
            except json.JSONDecodeError:
                pass

        return self._compute_analysis(ticker, closes, ema12, ema26, rsi, zscore, momentum, support, resistance, ema_cross, atr)

    def _compute_analysis(self, ticker, closes, ema12, ema26, rsi, zscore, momentum, support, resistance, ema_cross, atr=None) -> dict:
        if atr is None:
            atr = (closes[-1] if closes else 100.0) * 0.012
        # Composite signal from multiple indicators
        signals = []
        if ema12 > ema26:
            signals.append(1)
        elif ema12 < ema26:
            signals.append(-1)

        if rsi < 35:
            signals.append(1)  # Oversold -> potential long
        elif rsi > 70:
            signals.append(-1)  # Overbought -> potential short

        if momentum > 0.05:
            signals.append(1)
        elif momentum < -0.05:
            signals.append(-1)

        if zscore < -2:
            signals.append(1)  # Mean reversion long
        elif zscore > 2:
            signals.append(-1)  # Mean reversion short

        composite = sum(signals) / max(len(signals), 1)
        direction = "LONG" if composite > 0.2 else ("SHORT" if composite < -0.2 else "NEUTRAL")
        confidence = min(92, max(30, 50 + composite * 35))

        trend = "BULLISH" if ema12 > ema26 and momentum > 0 else ("BEARISH" if ema12 < ema26 and momentum < 0 else "SIDEWAYS")

        return {
            "direction": direction,
            "confidence": round(confidence, 1),
            "trend_signal": trend,
            "momentum_score": round(min(1, max(-1, momentum * 5)), 3),
            "mean_reversion_signal": round(-zscore / 3, 3),
            "support": support,
            "resistance": resistance,
            "rsi": round(rsi, 1),
            "atr": atr,
            "ema_crossover": ema_cross,
            "reasoning": (
                f"{ticker}: EMA12/26 crossover is {ema_cross} (strategy 3.11-3.13). "
                f"RSI at {rsi:.0f} ({'oversold' if rsi < 35 else 'overbought' if rsi > 70 else 'neutral'}). "
                f"12-1m momentum {momentum:+.1%} (strategy 3.1). "
                f"Mean-reversion Z-score {zscore:.1f} (strategy 3.9). "
                f"Composite signal: {direction} with {confidence:.0f}% confidence."
            ),
        }

    def _mock_analysis(self, ticker: str) -> dict:
        """No bars, no analysis.

        Reached from `if not closes: return self._mock_analysis(ticker)` -
        the price feed returned nothing. The old response to that was:

            direction  = rng.choice(["LONG", "SHORT", "NEUTRAL"])
            base_price = rng.uniform(50, 500)
            confidence = rng.uniform(45, 88)
            support    = base_price * 0.94
            resistance = base_price * 1.06

        A random direction at up to 88% confidence, on a random price, from
        the one agent in the pipeline that is supposed to be grounded in
        actual bars. The invented support and resistance then travelled into
        the risk manager, which computed a reward/risk ratio from them - so a
        symbol trading at 4,400 could be assigned support at 235.

        This is the strictest abstention in the pipeline. If the price feed
        is down there is nothing to analyse, and with the technical agent
        abstaining the trader will almost always fall below
        MIN_DIRECTIONAL_VOTES and publish no signal at all - which is the
        correct outcome when the market data never arrived.
        """
        return self.abstain(
            f"No price bars returned for {ticker}. Technical analysis needs OHLCV "
            f"data and none was available, so no trend, level or momentum reading "
            f"is produced.",
            trend_signal=None,
            momentum_score=None,
            mean_reversion_signal=None,
            support=None,
            resistance=None,
            rsi=None,
            atr=None,
            ema_crossover=None,
        )
