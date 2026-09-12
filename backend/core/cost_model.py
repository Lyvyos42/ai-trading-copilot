"""
Institutional Execution Cost Model (core/cost_model.py)
Mandatory Pre-Flight Execution Toll and Feasibility Verification Engine

Evaluates the 4-component execution toll:
    Toll = (Spread * 4.3) + Commission + (Swap * dt)

Enforces:
    1. Edge/Toll >= 0.767 for any passive execution rehabilitation.
    2. Gross Expectancy > Toll for active market execution.
    3. Verified broker commission schedules (no phantom or estimated tolls).
"""

from typing import Dict, Any

BROKER_COMMISSIONS_RT: Dict[str, float] = {
    'ic_markets_mt5': 7.00,
    'ic_markets_ctrader': 6.00,
    'pepperstone_mt5': 7.00,
    'pepperstone_ctrader': 6.00,
    'tickmill_pro': 4.00,
    'tickmill_vip': 2.00,
    'fusion_markets_zero': 3.00,
    'darwinex_classic': 5.00,
    'ibkr_ideal_pro': 4.00,
    'ftmo_normal': 6.00,
    'funding_pips_raw': 3.00,
}

EMPIRICAL_RAW_SPREAD_BP: Dict[str, float] = {
    'eurusd': 0.10,
    'gbpusd': 0.35,
    'usdjpy': 0.20,
    'audusd': 0.40,
    'usdcad': 0.30,
    'nzdusd': 0.60,
    'usdchf': 0.35,
    'eurgbp': 0.45,
    'eurjpy': 0.50,
    'xauusd': 0.90,
    'xagusd': 2.00,
    'wti': 2.50,
    'us500': 0.80,
    'ustech100m': 0.60,
}

SLIPPAGE_MULTIPLIER: float = 4.30
PASSIVE_REHABILITATION_THRESHOLD: float = 0.767

# ---------------------------------------------------------------------------
# AUDIT 2026-09-12. The spread table above is ESTIMATED, not measured, and the
# tolls it produced were 0.39x to 0.91x the values sealed in
# prereg/TOLL_BREAKEVEN_01.md section 4 (eurusd 1.13 vs 2.88; nzdusd 3.28 vs
# 7.33). Deploying it as the mandatory gate would have LOWERED every toll in
# the programme and made already-refuted strategies look better.
#
# The sealed measured tolls therefore take precedence. The spread model is used
# only for instruments section 4 does not cover, and is labelled estimated.
# ---------------------------------------------------------------------------
SEALED_TOLL_BP: Dict[str, float] = {
    'eurgbp': 3.86, 'xauusd': 5.00, 'gbpusd': 3.10, 'eurusd': 2.88,
    'usdjpy': 3.51, 'audusd': 5.08, 'nzdusd': 7.33, 'usdcad': 2.21,
    'usdchf': 4.48,
}

# $/lot commission converts to bp against LOT NOTIONAL, which is not 100,000
# for metals, energy or indices. A flat /10 divisor overstated gold 2x and
# understated WTI by 30%.
LOT_NOTIONAL_USD: Dict[str, float] = {
    'xauusd': 200_000.0, 'xagusd': 150_000.0, 'wti': 70_000.0,
    'us500': 50_000.0, 'ustech100m': 20_000.0,
}
DEFAULT_LOT_NOTIONAL_USD: float = 100_000.0

def compute_execution_toll_bp(
    symbol: str,
    broker: str = 'ic_markets_mt5',
    order_type: str = 'market',
    holding_days: float = 0.0,
    annual_swap_rate_pct: float = 3.00,
) -> Dict[str, Any]:
    sym = symbol.lower()
    raw_spread_bp = EMPIRICAL_RAW_SPREAD_BP.get(sym, 0.50)
    comm_dollars = BROKER_COMMISSIONS_RT.get(broker, 7.00)
    notional = LOT_NOTIONAL_USD.get(sym, DEFAULT_LOT_NOTIONAL_USD)
    comm_bp = comm_dollars / notional * 1e4

    if order_type == 'market':
        spread_toll_bp = raw_spread_bp * SLIPPAGE_MULTIPLIER
    else:
        spread_toll_bp = raw_spread_bp

    # Financing accrues on CALENDAR days, not the 252 trading days the first
    # version divided by, which overstated it by 45%. Wednesday 3x rollover and
    # weekends are the caller's responsibility via `holding_days`.
    swap_toll_bp = (annual_swap_rate_pct / 365.0) * holding_days * 100.0 if holding_days > 0 else 0.0

    sealed = SEALED_TOLL_BP.get(sym)
    if sealed is not None:
        spread_and_comm_bp = sealed          # measured; supersedes the estimate
        toll_source = 'MEASURED (TOLL_BREAKEVEN_01 section 4)'
    else:
        spread_and_comm_bp = spread_toll_bp + comm_bp
        toll_source = 'ESTIMATED (unsourced spread table) - do not cite as measured'
    total_toll_bp = spread_and_comm_bp + swap_toll_bp
    max_passive_saving_bp = raw_spread_bp   # Delta <= spread, TOLL_BREAKEVEN_01 section 3
    
    return {
        'symbol': sym,
        'broker': broker,
        'order_type': order_type,
        'raw_spread_bp': raw_spread_bp,
        'commission_bp': comm_bp,
        'spread_toll_bp': spread_toll_bp,
        'swap_toll_bp': swap_toll_bp,
        'total_toll_bp': total_toll_bp,
        'toll_source': toll_source,
        'max_passive_saving_bp': max_passive_saving_bp,
        'min_required_gross_edge_bp': total_toll_bp,
        'min_edge_for_passive_rescue_bp': total_toll_bp * PASSIVE_REHABILITATION_THRESHOLD,
    }

def validate_strategy_feasibility(
    expected_gross_bp: float,
    symbol: str,
    broker: str = 'ic_markets_mt5',
    order_type: str = 'market',
    holding_days: float = 0.0,
) -> Dict[str, Any]:
    toll = compute_execution_toll_bp(symbol, broker, order_type, holding_days)
    total_toll = toll['total_toll_bp']
    edge_toll_ratio = expected_gross_bp / total_toll if total_toll > 0 else 0.0
    
    is_market_viable = expected_gross_bp > total_toll
    is_passive_rehabilitable = edge_toll_ratio >= PASSIVE_REHABILITATION_THRESHOLD
    
    # 'REJECTED_WALL_1' was unreachable dead code: the if/elif/else below covers
    # every case and always overwrote it. Non-positive gross is now named
    # explicitly, since it is a different failure from merely missing the hurdle.
    if expected_gross_bp <= 0.0:
        verdict = 'REJECTED_NO_GROSS_EDGE'
    elif is_market_viable:
        verdict = 'VIABLE_ACTIVE'
    elif is_passive_rehabilitable:
        # 0.767 is NECESSARY, not sufficient: TOLL_BREAKEVEN_01 section 5 adds an
        # adverse-selection term. Naming this 'FEASIBLE' overstated the bound.
        verdict = 'NOT_EXCLUDED_BY_PASSIVE_BOUND'
    else:
        verdict = 'REJECTED_WALL_1'
        
    return {
        'verdict': verdict,
        'expected_gross_bp': expected_gross_bp,
        'total_toll_bp': total_toll,
        'edge_to_toll_ratio': edge_toll_ratio,
        'hurdle_ratio': PASSIVE_REHABILITATION_THRESHOLD,
        'net_expectancy_bp': expected_gross_bp - total_toll,
        'toll_breakdown': toll,
    }
