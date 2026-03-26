from typing import TypedDict, Any


class SessionState(TypedDict, total=False):
    # Session identity
    session_id: str
    user_id: str
    ticker: str
    asset_class: str
    strategy_profile: str

    # Session context
    session_start_time: str          # ISO timestamp
    session_duration_minutes: int    # elapsed
    kill_zone: str                   # "NY_OPEN" | "LONDON" | "ASIA" | "TOKYO" | "NONE"
    kill_zone_active: bool
    kill_zone_minutes_remaining: int

    # Market data (intraday focus)
    market_data: dict[str, Any]      # OHLCV + intraday indicators
    news_context: dict[str, Any]     # live headlines

    # Session agent outputs
    timer_analysis: dict[str, Any]
    session_technical: dict[str, Any]
    session_sentiment: dict[str, Any]
    session_order_flow: dict[str, Any]
    session_correlation: dict[str, Any]
    session_risk: dict[str, Any]
    session_trader_signal: dict[str, Any]
    coach_feedback: dict[str, Any]

    # Session risk gate
    session_risk_gate_result: dict[str, Any]

    # Session P&L tracking
    session_trades: list[dict[str, Any]]   # list of fills in this session
    session_pnl: float                     # running P&L in USD
    session_pnl_pct: float                 # running P&L in %
    session_high_water: float              # peak P&L in session
    session_drawdown_pct: float            # current drawdown from session peak
    session_trade_count: int               # number of trades this session

    # Pipeline metadata
    reasoning_chain: list[str]
    errors: list[str]
    analysis_count_this_session: int       # for session rate limiting
