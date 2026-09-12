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

# ---------------------------------------------------------------------------
# PHASE 4, MEASURED 2026-09-12. 4,572,432 tbbo prints on GLBX.MDP3, October 2023
# (inside the discovery window). M = |trade - mid| / (0.5 * spread), so M = 1.0
# is execution exactly at the touch and a round trip costs spread * M.
#
# THE 4.3x MULTIPLIER WAS RETAIL DEALING-DESK RENT, NOT MARKET STRUCTURE.
#   GC  96.78% of prints at the touch, median M 1.0000, mean 1.0928
#   CL  93.92% of prints at the touch, median M 1.0000, mean 1.0401
# A CLOB charges for DEPTH CONSUMPTION instead: small orders pay ~nothing over
# the touch, large orders pay more than the dealing desk ever did.
#
# MEASURED ON GC AND CL ONLY. ES, YM and RTY were NOT measured, and neither was
# any MICRO contract -- micros trade their own, thinner book. Applying these
# numbers to an unmeasured root is an ASSUMPTION and is tagged as such.
# One month, one regime: October 2023 was not a stress period.
# ---------------------------------------------------------------------------
CLOB_M_MEASURED: Dict[str, list] = {
    # root: [(max_contracts, mean M), ...]
    'GC': [(1, 1.0417), (5, 1.0829), (20, 1.5235), (100, 3.7230), (10**9, 6.1875)],
    'CL': [(1, 1.0039), (5, 1.0515), (20, 1.3202), (100, 3.2443), (10**9, 2.3939)],
}
# Conservative default for unmeasured roots: the worse of GC/CL at each size.
# CAUTION on the top tier: the 100+ bucket is n=16 (GC) and n=33 (CL). 6.1875
# is an order of magnitude, not an estimate. The 21-100 tier is well supported
# (6,808 / 9,024 prints) and its MEDIAN M is 3.0000, so that band's cost is
# typical rather than outlier-driven.
CLOB_M_DEFAULT: list = [(1, 1.0417), (5, 1.0829), (20, 1.5235),
                        (100, 3.7230), (10**9, 6.1875)]

# Micro contract specifications. Notional is price-dependent; these are 2023
# reference levels used only to express fixed commission in bp.
MICRO_SPEC: Dict[str, Dict[str, float]] = {
    'MES': {'point_value': 5.0,   'tick': 0.25, 'tick_usd': 1.25, 'ref_px': 4500.0,  'root': 'ES'},
    'MYM': {'point_value': 0.5,   'tick': 1.00, 'tick_usd': 0.50, 'ref_px': 34000.0, 'root': 'YM'},
    'M2K': {'point_value': 5.0,   'tick': 0.10, 'tick_usd': 0.50, 'ref_px': 1850.0,  'root': 'RTY'},
    'MCL': {'point_value': 100.0, 'tick': 0.01, 'tick_usd': 1.00, 'ref_px': 75.0,    'root': 'CL'},
    'MGC': {'point_value': 10.0,  'tick': 0.10, 'tick_usd': 1.00, 'ref_px': 1950.0,  'root': 'GC'},
}
CME_COMMISSION_RT_USD: float = 1.04      # ESTIMATED: no broker schedule on file


def clob_multiplier(contracts: float, root: str = None) -> tuple:
    """Size-conditioned M for a central limit order book.

    Returns (M, source). The dealing-desk 4.3x is NOT used here; a CLOB charges
    by depth consumed, so M depends on order size.
    """
    table = CLOB_M_MEASURED.get((root or '').upper())
    src = f'MEASURED (Phase 4 tbbo CLOB Oct 2023, {root})' if table else           'ASSUMED (Phase 4 default; this root was NOT measured)'
    table = table or CLOB_M_DEFAULT
    for cap, m in table:
        if contracts <= cap:
            return m, src
    return table[-1][1], src


def micro_futures_toll_bp(contract: str, contracts: float = 1.0,
                          spread_ticks: float = 1.0,
                          commission_rt_usd: float = CME_COMMISSION_RT_USD) -> Dict[str, Any]:
    """Round-trip toll in bp for a CME micro contract at a given order size.

    Round trip crosses the spread once: cost = spread * M, since M is defined
    against the HALF spread and a round trip pays two half-spreads.
    """
    c = contract.upper()
    if c not in MICRO_SPEC:
        raise KeyError(f"{contract}: not a registered micro contract {sorted(MICRO_SPEC)}")
    sp = MICRO_SPEC[c]
    notional = sp['ref_px'] * sp['point_value']
    tick_bp = sp['tick_usd'] / notional * 1e4
    m, src = clob_multiplier(contracts, sp['root'])
    spread_toll = tick_bp * spread_ticks * m
    comm_bp = commission_rt_usd / notional * 1e4
    return {
        'contract': c, 'root': sp['root'], 'order_contracts': contracts,
        'notional_usd': notional, 'tick_bp': tick_bp,
        'clob_multiplier': m, 'multiplier_source': src,
        'spread_toll_bp': spread_toll, 'commission_bp': comm_bp,
        'total_toll_bp': spread_toll + comm_bp,
        'commission_source': 'ESTIMATED - no broker schedule on file',
    }


def compute_execution_toll_bp(
    symbol: str,
    broker: str = 'ic_markets_mt5',
    order_type: str = 'market',
    holding_days: float = 0.0,
    annual_swap_rate_pct: float = 3.00,
    venue: str = 'mt5_cfd',
    contracts: float = 1.0,
) -> Dict[str, Any]:
    """venue='mt5_cfd' applies the 4.3x dealing-desk multiplier (measured on an
    MT5 retail book). venue='cme_clob' routes to the size-conditioned CLOB
    multiplier measured in Phase 4. The two are NOT interchangeable."""
    if venue == 'cme_clob':
        return micro_futures_toll_bp(symbol, contracts)
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
