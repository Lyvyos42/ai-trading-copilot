"""
CONFIDENCE CALIBRATION - how often signals at each displayed percentage actually worked.

Each Copilot signal carries two numbers with different meanings. They are calibrated separately
and never mixed:

  vote_share   the share of the analysts' weighted votes on the signal's own side
               (probability_score / bullish_pct in app/agents/trader.py) - the large "72% BULLISH".
  confidence   the analysts' conviction scaled by how complete their data was (confidence_score).

Neither is a measured probability. Calibration shows, for each band of a number, how often the
signals in that band reached take-profit 1 before the stop (WIN) - resolved on real price bars by
app/services/signal_resolver.py. EXPIRED (neither level inside the window) and AMBIGUOUS (one bar
touched both) are counted but not scored. Signals from different generators (signal_mode) are
calibrated separately, because they are produced differently.
"""
from __future__ import annotations

import math
from collections import defaultdict
from typing import Iterable, Optional

Z95 = 1.959963984540054
BAND = 10                                   # percentage points per band
MIN_N_TO_COMPARE = 10                       # below this a band is shown as "not enough signals yet"

DEFINITIONS = {
    "vote_share": ("Share of the analysts' weighted votes on the signal's side (the large percentage on "
                   "each signal). A ranking between signals, not a measured probability."),
    "confidence": ("The analysts' conviction scaled by how complete their data was (confidence score). "
                   "A ranking between signals, not a measured probability."),
}
OUTCOME_DEFINITION = ("WIN = take-profit 1 reached before the stop within the signal's analytical window, "
                      "resolved on real price bars. LOSS = stop reached first. EXPIRED and AMBIGUOUS are "
                      "counted but not scored.")


def wilson(k: int, n: int) -> tuple[Optional[float], Optional[float]]:
    if n <= 0:
        return None, None
    p = k / n
    den = 1 + Z95 * Z95 / n
    centre = (p + Z95 * Z95 / (2 * n)) / den
    half = Z95 * math.sqrt(p * (1 - p) / n + Z95 * Z95 / (4 * n * n)) / den
    return max(0.0, centre - half), min(1.0, centre + half)


def vote_share(direction: Optional[str], probability_score: Optional[float]) -> Optional[float]:
    """The share of votes on the signal's own side; None for neutral or missing. Can be below 50 on
    older rows whose direction disagrees with the vote (see global_calibration)."""
    if probability_score is None or not direction:
        return None
    d = direction.upper()
    if d in ("LONG", "BUY", "BULLISH"):
        return float(probability_score)
    if d in ("SHORT", "SELL", "BEARISH"):
        return 100.0 - float(probability_score)
    return None


def band_of(score: float) -> int:
    return min(int(score // BAND) * BAND, 100 - BAND)


def calibrate(pairs: Iterable[tuple[float, bool]]) -> dict:
    """pairs: (score 0-100, won). Bands with n, observed rate, Wilson 95% interval and the gap."""
    pairs = list(pairs)
    buckets: dict[int, list[tuple[float, bool]]] = defaultdict(list)
    for s, won in pairs:
        buckets[band_of(s)].append((s, won))
    rows, ece, brier = [], 0.0, 0.0
    n_all = len(pairs)
    for b in sorted(buckets):
        ps = buckets[b]
        n, k = len(ps), sum(1 for _, w in ps if w)
        mean_score = sum(s for s, _ in ps) / n
        lo, hi = wilson(k, n)
        rows.append({"band": f"{b}-{b + BAND}", "n": n, "wins": k, "mean_score": round(mean_score, 1),
                     "observed_pct": round(100 * k / n, 1), "lo_pct": round(100 * lo, 1), "hi_pct": round(100 * hi, 1),
                     "enough": n >= MIN_N_TO_COMPARE})
        ece += n / n_all * abs(k / n - mean_score / 100)
    for s, won in pairs:
        brier += (s / 100 - (1.0 if won else 0.0)) ** 2
    return {"n": n_all, "bands": rows,
            "ece_points": round(100 * ece, 1) if n_all else None,
            "brier": round(brier / n_all, 4) if n_all else None}


def global_calibration(rows: Iterable) -> dict:
    """rows: (signal_mode, direction, probability_score, confidence_score, outcome)."""
    by_mode: dict[str, dict] = defaultdict(lambda: {"vote_share": [], "confidence": [], "expired": 0, "ambiguous": 0,
                                                    "direction_disagrees_with_votes": 0})
    for mode, direction, prob, conf, outcome in rows:
        m = by_mode[mode or "AI"]
        if outcome == "EXPIRED":
            m["expired"] += 1
            continue
        if outcome == "AMBIGUOUS":
            m["ambiguous"] += 1
            continue
        if outcome not in ("WIN", "LOSS"):
            continue
        won = outcome == "WIN"
        vs = vote_share(direction, prob)
        if vs is not None and vs < 50:
            # The card shows the majority side (e.g. 68% BEARISH) while the signal traded the other
            # side: the number on screen did not describe this trade. Counted, never calibrated.
            m["direction_disagrees_with_votes"] += 1
            continue
        if vs is not None:
            m["vote_share"].append((vs, won))
        if conf is not None:
            m["confidence"].append((float(conf), won))
    modes = {}
    for mode, m in sorted(by_mode.items()):
        modes[mode] = {"vote_share": calibrate(m["vote_share"]), "confidence": calibrate(m["confidence"]),
                       "expired": m["expired"], "ambiguous": m["ambiguous"],
                       "direction_disagrees_with_votes": m["direction_disagrees_with_votes"]}
    return {"definitions": DEFINITIONS, "outcome_definition": OUTCOME_DEFINITION, "band_width": BAND,
            "min_n_to_compare": MIN_N_TO_COMPARE, "modes": modes}
