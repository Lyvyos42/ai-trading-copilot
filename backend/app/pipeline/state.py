from typing import TypedDict, Any


class TradingState(TypedDict, total=False):
    ticker: str
    timeframe: str
    asset_class: str
    market_data: dict[str, Any]              # OHLCV + indicators
    news_context: dict[str, Any]             # live scraped headlines for agents
    # Stage 1: 7 parallel analysts
    fundamental_analysis: dict[str, Any]
    technical_analysis: dict[str, Any]
    sentiment_analysis: dict[str, Any]
    macro_analysis: dict[str, Any]
    order_flow_analysis: dict[str, Any]      # NEW — OrderFlowAnalyst
    regime_change_analysis: dict[str, Any]   # NEW — RegimeChangeAnalyst
    correlation_analysis: dict[str, Any]     # NEW — CorrelationAnalyst
    # Stage 2: Quant validation
    quant_validation: dict[str, Any]         # NEW — QuantAnalyst
    # Stage 3: Debate
    bull_case: str
    bear_case: str
    debate_score: dict[str, Any]
    # Stage 4-6: Trader → Risk → Risk Gate → Fund Manager
    risk_assessment: dict[str, Any]
    risk_gate_result: dict[str, Any]         # NEW — Risk Gate (pure Python)
    final_signal: dict[str, Any]
    reasoning_chain: list[str]
    errors: list[str]
    # Memory Layer
    memory_context: str                      # injected user + agent memory context
    user_id: str                             # for memory retrieval + storage
    # Metadata
    daily_analysis_count: int                # for Risk Gate rule 8
    strategy_profile: str                    # active profile slug (e.g. "balanced")
