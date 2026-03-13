from typing import TypedDict, Any


class TradingState(TypedDict, total=False):
    ticker: str
    timeframe: str
    asset_class: str
    market_data: dict[str, Any]          # OHLCV + indicators
    fundamental_analysis: dict[str, Any]  # from fundamental agent
    technical_analysis: dict[str, Any]    # from technical agent
    sentiment_analysis: dict[str, Any]    # from sentiment agent
    macro_analysis: dict[str, Any]        # from macro agent
    bull_case: str
    bear_case: str
    debate_score: dict[str, Any]
    risk_assessment: dict[str, Any]
    final_signal: dict[str, Any]
    reasoning_chain: list[str]
    errors: list[str]
