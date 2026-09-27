"""
Signal Lab research engine (pure functions): research cards, breakdowns, score discrimination.

Definitions - every metric is named for what it measures; nothing is called "accuracy":
    tp1_before_stop        among signals that ended at TP1 or at the stop, the share that reached TP1 first
    direction_correct      the exit was beyond the entry in the signal's direction (any exit)
    R                      signed move from entry to exit / distance from entry to stop (signal layer,
                           before execution costs)
    MFE / MAE              best / worst excursion in R while open, when it was measured

Sample adequacy is judged by the width of the 95% interval, not by a fixed count:
    a rate is "adequate" when its Wilson half-width <= RATE_HALF_WIDTH (10 points);
    mean R is "adequate" when its t half-width <= R_HALF_WIDTH (0.25 R).
For planning, n_for_rate_precision() gives the sample that reaches the target half-width at p = 0.5.

Research findings (directive s24): NEGATIVE, WEAK, INSUFFICIENT_SAMPLE, UNRESOLVED,
POSITIVE_BEFORE_COSTS (a candidate, still subject to out-of-sample and execution checks), plus
SYMBOL_DEPENDENT / VERSION_DEPENDENT / SESSION_DEPENDENT when groups with adequate samples disagree.
Regime and market-state breakdowns need context captured at signal time; until then the card says so.
"""
from __future__ import annotations

import math
import statistics as st
from collections import defaultdict
from typing import Iterable

Z = 1.959963984540054
RATE_HALF_WIDTH = 0.10
R_HALF_WIDTH = 0.25
SCORE_BANDS = [(50, 60), (60, 70), (70, 80), (80, 90), (90, 101)]


def wilson(k: int, n: int) -> tuple[float | None, float | None]:
    if n <= 0:
        return None, None
    p = k / n
    den = 1 + Z * Z / n
    c = (p + Z * Z / (2 * n)) / den
    h = Z * math.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n)) / den
    return max(0.0, c - h), min(1.0, c + h)


# exact Student-t 97.5% quantiles for small df (the expansion below is too narrow at df 1-2)
_T975 = {1: 12.7062, 2: 4.3027, 3: 3.1824, 4: 2.7764, 5: 2.5706, 6: 2.4469, 7: 2.3646, 8: 2.3060,
         9: 2.2622, 10: 2.2281}


def t_crit(df: int) -> float:
    """Student-t 97.5% quantile: exact table for df <= 10, Cornish-Fisher expansion above (error < 0.1%)."""
    if df <= 0:
        return float("nan")
    if df in _T975:
        return _T975[df]
    z = Z
    return (z + (z ** 3 + z) / (4 * df) + (5 * z ** 5 + 16 * z ** 3 + 3 * z) / (96 * df ** 2)
            + (3 * z ** 7 + 19 * z ** 5 + 17 * z ** 3 - 15 * z) / (384 * df ** 3))


def n_for_rate_precision(half_width: float = RATE_HALF_WIDTH, p: float = 0.5) -> int:
    return math.ceil(p * (1 - p) * (Z / half_width) ** 2)


def rate(k: int, n: int) -> dict:
    lo, hi = wilson(k, n)
    return {"k": k, "n": n, "rate": (k / n) if n else None, "lo": lo, "hi": hi,
            "half_width": ((hi - lo) / 2) if n else None,
            "adequate": bool(n) and (hi - lo) / 2 <= RATE_HALF_WIDTH}


def mean_ci(xs: list[float]) -> dict:
    n = len(xs)
    if n == 0:
        return {"n": 0, "mean": None, "lo": None, "hi": None, "median": None, "adequate": False}
    m = sum(xs) / n
    if n < 2:
        return {"n": n, "mean": m, "lo": None, "hi": None, "median": m, "adequate": False}
    se = st.stdev(xs) / math.sqrt(n)
    h = t_crit(n - 1) * se
    return {"n": n, "mean": m, "lo": m - h, "hi": m + h, "median": st.median(xs), "half_width": h,
            "adequate": h <= R_HALF_WIDTH}


def resolved(recs: Iterable[dict]) -> list[dict]:
    return [r for r in recs if r.get("resolved") and r.get("exit_reason") not in (None, "unknown")]


def card(recs: list[dict]) -> dict:
    """Research card for one population (one module version, or any slice of one)."""
    rs = resolved(recs)
    tb = [r for r in rs if r.get("exit_reason") in ("target", "stop")]
    dc = [r for r in rs if r.get("direction_correct") is not None]
    R = [float(r["r_multiple"]) for r in rs if r.get("r_multiple") is not None]
    wins = [x for x in R if x > 0]
    losses = [x for x in R if x <= 0]
    mfe = [float(r["mfe_r"]) for r in rs if r.get("mfe_r") is not None]
    mae = [float(r["mae_r"]) for r in rs if r.get("mae_r") is not None]
    hold = [float(r["holding_minutes"]) for r in rs if r.get("holding_minutes") is not None]
    scores = [float(r["consensus_score"]) for r in recs if r.get("consensus_score") is not None]
    aw = sum(wins) / len(wins) if wins else None
    al = -sum(losses) / len(losses) if losses else None
    return {
        "signals": len(recs),
        "resolved": len(rs),
        "unknown_exits": sum(1 for r in recs if r.get("resolved") and r.get("exit_reason") == "unknown"),
        "tp1_before_stop": rate(sum(1 for r in tb if r["exit_reason"] == "target"), len(tb)),
        "direction_correct_at_exit": rate(sum(1 for r in dc if r["direction_correct"]), len(dc)),
        "r": {**mean_ci(R), "win_rate": (len(wins) / len(R)) if R else None, "avg_win": aw, "avg_loss": al,
              "breakeven_win_rate": (al / (aw + al)) if (aw and al is not None and aw + al > 0) else None},
        "mfe_r": {"n": len(mfe), "mean": (sum(mfe) / len(mfe)) if mfe else None},
        "mae_r": {"n": len(mae), "mean": (sum(mae) / len(mae)) if mae else None},
        "median_holding_minutes": st.median(hold) if hold else None,
        "score_distribution": score_distribution(scores),
        "costs": "not included - signal layer only",
    }


def score_distribution(scores: list[float]) -> dict:
    if not scores:
        return {"n": 0, "note": "this module produces no consensus score"}
    out = {"n": len(scores)}
    for lo, hi in SCORE_BANDS:
        out[f"{lo}-{min(hi, 100)}"] = sum(1 for s in scores if lo <= s < hi)
    out["below_50"] = sum(1 for s in scores if s < 50)
    return out


def breakdown(recs: list[dict], key) -> dict:
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in recs:
        g = key(r) if callable(key) else r.get(key)
        groups[str(g if g not in (None, "") else "unknown")].append(r)
    out = {}
    for g, rs in sorted(groups.items()):
        c = card(rs)
        out[g] = {"signals": c["signals"], "resolved": c["resolved"],
                  "tp1_before_stop": c["tp1_before_stop"]["rate"], "tp1_n": c["tp1_before_stop"]["n"],
                  "mean_r": c["r"]["mean"], "r_lo": c["r"]["lo"], "r_hi": c["r"]["hi"], "r_n": c["r"]["n"]}
    return out


def _disagree(groups: dict, min_n: int = 20) -> bool:
    big = [g for g in groups.values() if g["r_n"] >= min_n and g["r_lo"] is not None]
    for i in range(len(big)):
        for j in range(i + 1, len(big)):
            a, b = big[i], big[j]
            if a["r_hi"] < b["r_lo"] or b["r_hi"] < a["r_lo"]:
                return True
    return False


def finding(c: dict, dims: dict[str, dict] | None = None) -> dict:
    r = c["r"]
    flags: list[str] = []
    if r["n"] >= 10 and r.get("hi") is not None and r["hi"] < 0:
        label, why = "NEGATIVE", f"mean R {r['mean']:+.2f}, 95% interval {r['lo']:+.2f}..{r['hi']:+.2f} below zero (n={r['n']})"
    elif not r.get("adequate"):
        need = "no resolved outcomes yet" if r["n"] == 0 else (
            f"mean R interval half-width {r.get('half_width', float('nan')):.2f} R > {R_HALF_WIDTH} R" if r.get("half_width") else f"n={r['n']}")
        label, why = "INSUFFICIENT_SAMPLE", need
    elif r["lo"] > 0:
        label, why = "POSITIVE_BEFORE_COSTS", f"mean R {r['mean']:+.2f}, interval {r['lo']:+.2f}..{r['hi']:+.2f} above zero; execution and out-of-sample checks still required"
    elif r["mean"] < 0:
        label, why = "WEAK", f"mean R {r['mean']:+.2f}, interval includes zero"
    else:
        label, why = "UNRESOLVED", f"mean R {r['mean']:+.2f}, interval includes zero"
    for dim, groups in (dims or {}).items():
        if _disagree(groups):
            flags.append(f"{dim.upper()}_DEPENDENT")
    return {"label": label, "why": why, "flags": flags,
            "limitations": ["regime and market-state context are not captured at signal time yet"]}


def auc(pairs: list[tuple[float, bool]]) -> dict:
    """Does a higher score go with more wins? Mann-Whitney AUC with a Hanley-McNeil 95% interval.
    0.5 = no discrimination."""
    pos = [s for s, w in pairs if w]
    neg = [s for s, w in pairs if not w]
    n1, n0 = len(pos), len(neg)
    if n1 == 0 or n0 == 0:
        return {"auc": None, "n_win": n1, "n_loss": n0, "verdict": "cannot compute: needs both wins and losses"}
    gt = sum(1.0 if p > q else 0.5 if p == q else 0.0 for p in pos for q in neg)
    a = gt / (n1 * n0)
    q1, q2 = a / (2 - a), 2 * a * a / (1 + a)
    se = math.sqrt(max(a * (1 - a) + (n1 - 1) * (q1 - a * a) + (n0 - 1) * (q2 - a * a), 0.0) / (n1 * n0))
    lo, hi = a - Z * se, a + Z * se
    if lo > 0.5:
        verdict = "higher scores went with more wins (interval above 0.5)"
    elif hi < 0.5:
        verdict = "higher scores went with FEWER wins (interval below 0.5)"
    else:
        verdict = "no demonstrated discrimination yet (interval includes 0.5)"
    return {"auc": a, "lo": lo, "hi": hi, "n_win": n1, "n_loss": n0, "verdict": verdict}


def score_research(pairs: list[tuple[float, bool]]) -> dict:
    """pairs: (consensus score, reached TP1 before the stop)."""
    bands = []
    for lo, hi in SCORE_BANDS:
        ps = [w for s, w in pairs if lo <= s < hi]
        bands.append({"band": f"{lo}-{min(hi, 100) - (0 if hi > 100 else 1)}" if hi <= 100 else f"{lo}-100",
                      **rate(sum(1 for w in ps if w), len(ps))})
    below = [w for s, w in pairs if s < 50]
    return {"n": len(pairs), "bands": bands, "below_50": len(below), "discrimination": auc(pairs),
            "n_needed_per_band_for_10pt_interval": n_for_rate_precision()}


# ── promotion pipeline ───────────────────────────────────────────────────────
PIPELINE = ["RESEARCH", "SHADOW", "BETA", "LIVE", "AUTOMATION_ELIGIBLE"]
PIPELINE_RULES = {
    "RESEARCH": "Idea or backtest only. No forward record yet.",
    "SHADOW": "Runs forward; every signal and outcome is recorded and sent to Copilot. Not published.",
    "BETA": "Published (Telegram / Copilot) with its sample shown, or 'insufficient sample'. Needs: no NEGATIVE "
            "finding, and the owner's decision to publish.",
    "LIVE": "Needs, on forward records of ONE code version: TP1-before-stop rate measured to +/-10 points, mean R "
            "measured to +/-0.25 R, and the mean-R interval above zero before costs.",
    "AUTOMATION_ELIGIBLE": "Needs: the LIVE conditions still met after a measured execution profile (costs, "
                           "slippage), and a Prop Guard risk profile. Switched on only by the owner.",
    "DEMOTION": "A NEGATIVE finding (mean-R interval below zero, n >= 10) moves a module back to SHADOW. A code or "
                "parameter change starts a new version with its own record.",
}


def promotion(status: str | None, c: dict, forward: bool, not_forward_note: str | None = None) -> dict:
    """Which rules for the next pipeline step are met, computed from the card. Never promotes by itself."""
    r, tp = c["r"], c["tp1_before_stop"]
    neg = finding(c)["label"] == "NEGATIVE"
    reqs: list[dict] = []
    if status in (None, "DISABLED", "RETIRED", "PAUSED"):
        return {"next": None, "requirements": [], "note": "not running - no promotion path until it is switched on"}
    if not forward:
        return {"next": None, "requirements": [],
                "note": not_forward_note or "promotion counts forward records of one code version only"}
    if status in ("RESEARCH", "SHADOW"):
        nxt = "SHADOW" if status == "RESEARCH" else "BETA"
        reqs.append({"rule": "no NEGATIVE finding", "met": not neg})
        reqs.append({"rule": "owner decides to publish", "met": None, "detail": "a decision, not a measurement"})
        return {"next": nxt, "requirements": reqs}
    need_tp = max(0, n_for_rate_precision(p=tp["rate"] if tp["rate"] is not None else 0.5) - tp["n"])
    live = [
        {"rule": "TP1-before-stop rate measured to +/-10 points", "met": bool(tp["adequate"]),
         "detail": f"n={tp['n']}" + (f", about {need_tp} more target/stop outcomes" if not tp["adequate"] else "")},
        {"rule": "mean R measured to +/-0.25 R", "met": bool(r.get("adequate")),
         "detail": f"n={r['n']}" + (f", half-width {r['half_width']:.2f} R" if r.get("half_width") is not None else "")},
        {"rule": "mean-R interval above zero before costs", "met": r.get("lo") is not None and r["lo"] > 0},
        {"rule": "no NEGATIVE finding", "met": not neg},
    ]
    if status == "BETA":
        return {"next": "LIVE", "requirements": live}
    if status == "LIVE":
        return {"next": "AUTOMATION_ELIGIBLE", "requirements": live + [
            {"rule": "LIVE conditions hold after a measured execution profile", "met": None,
             "detail": "execution-layer results are recorded; the profile check is not computed here yet"},
            {"rule": "Prop Guard risk profile attached", "met": None, "detail": "set by the owner"}]}
    return {"next": None, "requirements": []}
