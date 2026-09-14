"""
IEF position sizing — dual-tier architecture with a toll-band governor
=====================================================================
Converts the pre-registered target weights into integer contract counts, and
refuses to silently leave the execution-cost band the strategy was measured in.

THE GOVERNOR IS THE POINT OF THIS MODULE.
Phase 4 measured the CLOB slippage multiplier at M = 1.0829 for orders of 1-5
contracts. At 6-20 contracts M = 1.5235, a 41% toll increase. Every measured
number in CME_REBAL_FLOW_01 was produced inside the 1-5 band. An order of 7
contracts is therefore trading OUTSIDE the cost model that justified the trade,
and nothing in the weight formula prevents it: weights are fractions of equity,
so contract counts grow linearly with the account.

MEASURED CONSEQUENCE (mean target weights, discovery panel):
    panel mode, 4.0x leverage cap, $190,000 equity
      MES 5.12 contracts, MYM 6.71, M2K 5.85   -- ALL THREE outside the band
    panel mode, unlevered
      the band holds only up to ~$566,000 (MYM binding)

So the effective leverage multiple is NOT a free choice. It is
    k_eff = min(LEVERAGE_CAP, min_i  MAX_CONTRACTS * notional_i / (|w_i| * E))
which declines as equity grows. At $190,000 that is 2.98x, not 4.0x.

THAT HAS A GATE CONSEQUENCE AND IT MUST BE REPORTED, NOT BURIED.
Gate 3B (volatility-matched CAGR beats buy-and-hold) passes only at a cap of
4.0x or above; at 3.0x it FAILS by -1.065pp of CAGR. A deployment governed to
2.98x therefore does NOT carry Gate 3B's matched-CAGR claim. What it carries is
Gate 3A (Sharpe dominance) and Gate 3C (sign null), both scale-invariant.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

# Phase 4 measured CLOB bands. Exceeding MAX_CONTRACTS leaves the measured model.
MAX_CONTRACTS_PER_LEG = 5
M_IN_BAND = 1.0829
M_NEXT_BAND = 1.5235

PANEL_MIN_EQUITY = 190_000.0      # directive tier boundary
LEVERAGE_CAP = 4.0                # Gate 3B declared cap
MIN_CONTRACTS_FOR_PANEL = 1       # below this a leg cannot be expressed at all

SINGLE = "SINGLE_MES"
PANEL = "PANEL_3"


@dataclass(frozen=True)
class Contract:
    symbol: str
    series: str
    multiplier: float
    toll_bp: float
    tick: float


CONTRACTS = {
    "es_daily":  Contract("MES", "es_daily",  5.0, 1.018, 0.25),
    "ym_daily":  Contract("MYM", "ym_daily",  0.5, 0.906, 1.00),
    "rty_daily": Contract("M2K", "rty_daily", 5.0, 1.665, 0.10),
}
SINGLE_SERIES = "es_daily"


@dataclass
class Order:
    symbol: str
    series: str
    contracts: int
    side: int                 # +1 long, -1 short
    target_weight: float
    target_notional: float
    actual_notional: float
    price: float
    quantisation_error: float  # (actual - target) / target
    in_toll_band: bool


@dataclass
class SizingPlan:
    mode: str
    equity: float
    leverage_cap: float
    k_effective: float
    governor_binding: bool
    orders: list[Order] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def gross_notional(self) -> float:
        return sum(abs(o.actual_notional) for o in self.orders)

    @property
    def gross_leverage(self) -> float:
        return self.gross_notional / self.equity if self.equity else 0.0

    @property
    def all_in_band(self) -> bool:
        return all(o.in_toll_band for o in self.orders)


def select_mode(equity: float) -> str:
    """Directive tier boundary. Below it, fractional-contract rounding on a
    3-leg panel distorts the signal by more than the signal is worth."""
    return PANEL if equity >= PANEL_MIN_EQUITY else SINGLE


def effective_multiple(weights: dict[str, float], prices: dict[str, float],
                       equity: float, leverage_cap: float = LEVERAGE_CAP) -> tuple:
    """min(cap, the multiple that keeps every leg inside the measured toll band)."""
    limits = []
    for series, w in weights.items():
        if abs(w) < 1e-12:
            continue
        c = CONTRACTS[series]
        notional = prices[series] * c.multiplier
        limits.append(MAX_CONTRACTS_PER_LEG * notional / (abs(w) * equity))
    if not limits:
        return leverage_cap, False
    band_limit = min(limits)
    k = min(leverage_cap, band_limit)
    return k, band_limit < leverage_cap


def build_plan(weights: dict[str, float], prices: dict[str, float], equity: float,
               leverage_cap: float = LEVERAGE_CAP,
               apply_leverage: bool = True) -> SizingPlan:
    """weights are the PRE-REGISTERED targets as fractions of equity.

    In SINGLE mode the panel divisor 1/N is removed, because a one-instrument
    book is not splitting risk three ways. That is a sizing consequence of the
    tier, not a change to the signal.
    """
    mode = select_mode(equity)
    warnings: list[str] = []

    if mode == SINGLE:
        w0 = weights.get(SINGLE_SERIES, 0.0)
        n_active = sum(1 for v in weights.values() if abs(v) > 1e-12)
        weights = {SINGLE_SERIES: w0 * max(n_active, 1)}
        if SINGLE_SERIES not in prices:
            raise KeyError(f"SINGLE mode requires a price for {SINGLE_SERIES}")
        warnings.append(
            f"SINGLE_MES mode: equity ${equity:,.0f} < ${PANEL_MIN_EQUITY:,.0f}. "
            f"Cross-instrument averaging that produced the correlation-adjusted "
            f"statistic is NOT present in this configuration.")

    k, governor = (effective_multiple(weights, prices, equity, leverage_cap)
                   if apply_leverage else (1.0, False))
    if governor:
        warnings.append(
            f"TOLL-BAND GOVERNOR ACTIVE: leverage reduced from {leverage_cap:.2f}x to "
            f"{k:.2f}x so no leg exceeds {MAX_CONTRACTS_PER_LEG} contracts. "
            f"Gate 3B's matched-CAGR claim requires >= 4.0x and does NOT hold here; "
            f"Gate 3A and Gate 3C are scale-invariant and do.")

    orders: list[Order] = []
    for series, w in weights.items():
        if abs(w) < 1e-12:
            continue
        c = CONTRACTS[series]
        px = prices[series]
        notional_per = px * c.multiplier
        target_notional = w * k * equity
        raw = target_notional / notional_per
        n = int(round(abs(raw)))
        if n > MAX_CONTRACTS_PER_LEG:
            warnings.append(
                f"{c.symbol}: {n} contracts EXCEEDS the measured {MAX_CONTRACTS_PER_LEG}-lot "
                f"band even after the governor. Toll rises M {M_IN_BAND} -> {M_NEXT_BAND} "
                f"(+41%). Slice the order or re-measure the cost model.")
        if n == 0:
            warnings.append(
                f"{c.symbol}: target ${abs(target_notional):,.0f} rounds to ZERO contracts "
                f"(1 contract = ${notional_per:,.0f}). This leg is dropped.")
            continue
        side = 1 if raw > 0 else -1
        actual = side * n * notional_per
        orders.append(Order(
            symbol=c.symbol, series=series, contracts=n, side=side,
            target_weight=w * k, target_notional=target_notional,
            actual_notional=actual, price=px,
            quantisation_error=(abs(actual) - abs(target_notional)) / abs(target_notional)
            if target_notional else 0.0,
            in_toll_band=n <= MAX_CONTRACTS_PER_LEG))

    for o in orders:
        if abs(o.quantisation_error) > 0.25:
            warnings.append(
                f"{o.symbol}: quantisation error {o.quantisation_error:+.1%} on "
                f"{o.contracts} contract(s). The measured edge is ~30 bp/event; a sizing "
                f"error this large is an order of magnitude bigger than the signal.")

    return SizingPlan(mode=mode, equity=equity, leverage_cap=leverage_cap,
                      k_effective=k, governor_binding=governor,
                      orders=orders, warnings=warnings)


def trailing_vol_annualised(closes: list[float], lookback: int = 60) -> float:
    """The PRE-REGISTERED estimator: 60-session sd of daily log closes, annualised.

    ATR is NOT used. It is a different estimator, it includes gap and intraday
    range information this one excludes, and it was not what produced any measured
    number in the record. Substituting it silently would change the position series.
    """
    if len(closes) < lookback + 1:
        raise ValueError(f"need {lookback + 1} closes, got {len(closes)}")

    w = closes[-(lookback + 1):]
    r = [math.log(w[i + 1] / w[i]) for i in range(len(w) - 1)]
    mu = sum(r) / len(r)
    var = sum((x - mu) ** 2 for x in r) / (len(r) - 1)
    return math.sqrt(var) * math.sqrt(252.0)
