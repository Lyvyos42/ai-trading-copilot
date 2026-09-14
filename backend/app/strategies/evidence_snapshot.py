"""Pre-registered evidence for the quantitative strategies, as recorded.

Snapshot of Institutional Edge core/evidence.py REGISTRY and the cited prereg /
RESULTS documents, taken 2026-09-13. Copied rather than imported because the
deployed Copilot backend does not ship the Institutional Edge repository.

A FIELD THAT WAS NEVER MEASURED IS None, NOT A PLAUSIBLE NUMBER

No strategy below has a recorded historical win rate, so `win_rate` is None for
every one of them. Reporting a figure the record does not contain is exactly the
fabrication QuantAnalyst's mock path was rewritten to stop.
"""
from __future__ import annotations

SNAPSHOT_DATE = "2026-09-13"
SOURCE = "Institutional Edge core/evidence.py REGISTRY"

EVIDENCE: dict[str, dict] = {
    "cme_rebal_flow": {
        "registry_status": "CANDIDATE",
        "prereg": "prereg/CME_REBAL_FLOW_01.md",
        "edge_bp_per_event": 30.06,
        "edge_ci95_bp": [1.89, 58.23],
        "gross_t_portfolio": 2.67,
        "net_t": 2.34,
        "z_vs_sign_permutation_null": 2.634,
        "null_percentile": 99.3,
        "n_events": 392,
        "independent_months": 160,
        "net_sharpe": 0.642,
        "gates": "Gates 1, 2, 3 and binding Control C PASS; Gate 4 FAILS on 2020-23 (t -0.24)",
        "replication": "368 SPY months 1993-2023: Control B z +3.88; Gate 4 fails on 1993-2000",
        "win_rate": None,
        "caveat": "equity leg only - the bond leg of the mandated flow is not modelled",
    },
    "overnight_drift": {
        "registry_status": "CANDIDATE",
        "n_sessions": 8457,
        "oos_t": {"SPY": 2.36, "QQQ": 2.47},
        "oos_t_threshold": 2.73,
        "filtered_sharpe": {"SPY": 0.90, "QQQ": 1.09},
        "sharpe_retention": {"SPY": 1.00, "QQQ": 0.96},
        "max_drawdown": {"SPY": -0.174, "QQQ": -0.154},
        "gates": "OOS t FAIL (below 2.73); retention and drawdown PASS; IBS gate audit FAIL OOS",
        "win_rate": None,
        "caveat": "carried by retention and a 30-year prior, not by clearing the OOS bar",
    },
    "institutional_vwap": {
        "registry_status": "CANDIDATE",
        "gates": "NOT BACKTESTED - execution benchmark, no directional claim tested",
        "win_rate": None,
        "caveat": "its value is the reference level, not a measured edge",
    },
    "ten_am_macro": {
        "registry_status": "OBSERVE",
        "gates": "no backtest, no control, no cost model; mechanism checks only",
        "setup_rate_per_session": 0.54,
        "win_rate": None,
        "caveat": "forward data collection only; the edge is the open question",
    },
    "meanrev": {
        "registry_status": "CANDIDATE (IEB) / OBSERVER here",
        "net_r_per_trade": 0.112,
        "n_trades": 384,
        "clustered_t_filed": 1.82,
        "per_trade_oos_t": 1.20,
        "significance_bar": 3.0,
        "block_bootstrap_p_mean_le_0": 0.028,
        "gates": "OOS and 2021-2026 FAIL; control Welch +2.13 and symmetry PASS on EURUSD; "
                 "GBPUSD validation fails 4 of 5",
        "win_rate": None,
        "caveat": "filed clustered t equal-weights months and overstates the tradeable per-trade t",
    },
}


def for_strategy(name: str) -> dict:
    base = name.split(":")[0]
    rec = EVIDENCE.get(base)
    if rec is None:
        return {"registry_status": "UNRECORDED", "win_rate": None,
                "snapshot": SNAPSHOT_DATE, "source": SOURCE}
    return {**rec, "snapshot": SNAPSHOT_DATE, "source": SOURCE}
