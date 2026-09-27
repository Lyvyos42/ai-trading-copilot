"""Model-level calibration: definitions kept apart, outcomes scored correctly."""
import math

from app.services.calibration import band_of, calibrate, global_calibration, vote_share, wilson


def test_vote_share_is_the_signals_own_side():
    assert vote_share("LONG", 72.0) == 72.0
    assert vote_share("SHORT", 30.0) == 70.0          # 70% of the votes on the short side
    assert vote_share("NEUTRAL", 50.0) is None and vote_share("LONG", None) is None


def test_bands_and_wilson():
    assert band_of(72.0) == 70 and band_of(100.0) == 90 and band_of(0.0) == 0
    lo, hi = wilson(7, 10)
    assert math.isclose(lo, 0.3968, abs_tol=1e-3) and math.isclose(hi, 0.8922, abs_tol=1e-3)


def test_calibrate_perfect_and_off():
    good = calibrate([(75.0, i < 15) for i in range(20)])   # stated 75, observed 75
    assert good["bands"][0]["observed_pct"] == 75.0 and good["ece_points"] == 0.0
    bad = calibrate([(85.0, i < 2) for i in range(10)])     # stated 85, observed 20
    assert bad["ece_points"] == 65.0 and bad["bands"][0]["enough"] is True


def test_global_keeps_modes_and_definitions_apart_and_skips_unscored():
    rows = [("AI", "LONG", 72.0, 60.0, "WIN"), ("AI", "SHORT", 20.0, 55.0, "LOSS"),
            ("AUTO_SCAN", "LONG", 65.0, 50.0, "WIN"), ("AI", "LONG", 70.0, 50.0, "EXPIRED"),
            ("AI", "LONG", 70.0, 50.0, "AMBIGUOUS"), ("AI", "NEUTRAL", 50.0, 40.0, "WIN")]
    g = global_calibration(rows)
    ai = g["modes"]["AI"]
    assert set(g["modes"]) == {"AI", "AUTO_SCAN"}
    assert ai["expired"] == 1 and ai["ambiguous"] == 1
    assert ai["vote_share"]["n"] == 2                       # neutral has no side
    assert ai["confidence"]["n"] == 3                       # neutral still has a confidence
    assert "not a measured probability" in g["definitions"]["vote_share"]
