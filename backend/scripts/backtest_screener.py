"""
Real backtest of the auto-scanner's confluence screener.

Replaces nothing in the app — this is the measurement rig that tells us whether
the screener has an edge, and which target/stop geometry actually pays. Every
number it prints comes from real Yahoo daily bars.

No lookahead: at bar i the score is computed from bars [0..i] only, entry is at
close[i], and resolution walks bars i+1 onward. A bar that straddles both
barriers counts as a LOSS, matching app/services/signal_resolver.py.

Usage:
    python -m scripts.backtest_screener                    # default sweep
    python -m scripts.backtest_screener --years 5
    python -m scripts.backtest_screener --quick            # one config only
"""
import argparse
import json as _json
import os
import statistics
import sys
import urllib.parse as _urlpar
import urllib.request as _urlreq
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.auto_scanner import _score_setup  # noqa: E402

# Liquid, continuously-listed names across sectors — the kind of universe the
# scanner actually runs on.
UNIVERSE = [
    "AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "TSLA", "AMD",
    "NFLX", "INTC", "JPM", "XOM", "WMT", "DIS", "BA", "CAT",
    "SPY", "QQQ", "IWM", "GLD",
]

CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".bars_cache")


# ── Data ──────────────────────────────────────────────────────────────────────

def fetch_daily(ticker: str, years: int) -> list[dict]:
    """Daily OHLCV bars from the Yahoo chart API, cached on disk."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache = os.path.join(CACHE_DIR, f"{ticker}_{years}y.json")
    if os.path.exists(cache) and (datetime.now().timestamp() - os.path.getmtime(cache)) < 86400:
        with open(cache) as fh:
            return _json.load(fh)

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=365 * years + 60)  # +60 to warm up indicators
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{_urlpar.quote(ticker)}"
           f"?interval=1d&period1={int(start.timestamp())}&period2={int(end.timestamp())}")
    req = _urlreq.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with _urlreq.urlopen(req, timeout=20) as r:
        payload = _json.loads(r.read())

    res = (payload.get("chart") or {}).get("result") or []
    if not res:
        return []
    node = res[0]
    stamps = node.get("timestamp") or []
    q = ((node.get("indicators") or {}).get("quote") or [{}])[0]

    bars = []
    for i, ts in enumerate(stamps):
        o, h, l, c, v = (q.get("open") or [])[i], (q.get("high") or [])[i], \
                        (q.get("low") or [])[i], (q.get("close") or [])[i], (q.get("volume") or [])[i]
        if None in (h, l, c):
            continue
        bars.append({"ts": ts, "open": o or c, "high": h, "low": l, "close": c, "volume": v or 0})

    with open(cache, "w") as fh:
        _json.dump(bars, fh)
    return bars


def atr(highs, lows, closes, period=14) -> float:
    if len(closes) < period + 1:
        return 0.0
    trs = []
    for i in range(len(closes) - period, len(closes)):
        trs.append(max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1])))
    return sum(trs) / len(trs) if trs else 0.0


# ── Backtest ──────────────────────────────────────────────────────────────────

def backtest(bars_by_ticker: dict, threshold: int, tp_mult: float, sl_mult: float,
             hold_bars: int, use_screener: bool = True, entry_every: int = 5,
             baseline_dir: str = "match", dir_filter: str | None = None,
             dir_mix: dict | None = None) -> dict:
    """Walk every symbol bar by bar and score each triggered setup.

    use_screener=False enters on a fixed cadence instead, giving the noise
    baseline the screener has to beat. baseline_dir controls that baseline's
    direction: "long" is pure market beta and flatters itself in a bull sample,
    so "match" reproduces the screener's own long/short mix (dir_mix) to keep
    the comparison about signal quality rather than market drift.
    dir_filter restricts the screener to one side.
    """
    trades = []
    rng = __import__("random").Random(20260830)

    for ticker, bars in bars_by_ticker.items():
        if len(bars) < 80:
            continue
        closes = [b["close"] for b in bars]
        highs = [b["high"] for b in bars]
        lows = [b["low"] for b in bars]
        vols = [b["volume"] for b in bars]

        open_until = -1  # bar index this symbol is free again (one position at a time)

        for i in range(60, len(bars) - 1):
            if i < open_until:
                continue

            if use_screener:
                avg_vol = statistics.mean(vols[i - 20:i]) if i >= 20 and any(vols[i - 20:i]) else 0
                data = {
                    "closes": closes[: i + 1],
                    "highs": highs[: i + 1],
                    "lows": lows[: i + 1],
                    "volume": vols[i],
                    "volume_ratio": (vols[i] / avg_vol) if avg_vol else 1.0,
                }
                score, direction, _ = _score_setup(data)
                if score < threshold or direction not in ("LONG", "SHORT"):
                    continue
                if dir_filter and direction != dir_filter:
                    continue
            else:
                if i % entry_every:
                    continue
                score = 0
                if baseline_dir == "match" and dir_mix:
                    p_long = dir_mix.get("LONG", 0.5)
                    direction = "LONG" if rng.random() < p_long else "SHORT"
                elif baseline_dir == "alternate":
                    direction = "LONG" if rng.random() < 0.5 else "SHORT"
                else:
                    direction = baseline_dir.upper()

            a = atr(highs[: i + 1], lows[: i + 1], closes[: i + 1])
            if a <= 0:
                continue

            entry = closes[i]
            long_side = direction == "LONG"
            if long_side:
                tp, sl = entry + a * tp_mult, entry - a * sl_mult
            else:
                tp, sl = entry - a * tp_mult, entry + a * sl_mult
            risk = abs(entry - sl)
            if risk <= 0:
                continue

            # Resolve forward — bar i+1 onward only.
            outcome, exit_px, bars_held = "EXPIRED", closes[min(i + hold_bars, len(bars) - 1)], hold_bars
            for j in range(i + 1, min(i + 1 + hold_bars, len(bars))):
                hi, lo = highs[j], lows[j]
                hit_sl = lo <= sl if long_side else hi >= sl
                hit_tp = hi >= tp if long_side else lo <= tp
                if hit_sl:  # stop-first on a straddle, same rule as the live resolver
                    outcome, exit_px, bars_held = "LOSS", sl, j - i
                    break
                if hit_tp:
                    outcome, exit_px, bars_held = "WIN", tp, j - i
                    break

            r_mult = ((exit_px - entry) if long_side else (entry - exit_px)) / risk
            trades.append({"ticker": ticker, "outcome": outcome, "r": r_mult,
                           "score": score, "bars_held": bars_held, "direction": direction})
            open_until = i + bars_held + 1

    out = summarize(trades)
    longs = [t for t in trades if t["direction"] == "LONG"]
    out["pct_long"] = (len(longs) / len(trades) * 100) if trades else 0.0
    out["by_direction"] = {d: summarize([t for t in trades if t["direction"] == d])
                           for d in ("LONG", "SHORT")}
    out["trades_list"] = trades
    return out


def slice_bars(bars_by_ticker: dict, lo: float, hi: float) -> dict:
    """Take a contiguous date slice of every symbol, as fractions of its history."""
    out = {}
    for t, bars in bars_by_ticker.items():
        n = len(bars)
        chunk = bars[int(n * lo):int(n * hi)]
        if len(chunk) > 80:
            out[t] = chunk
    return out


def summarize(trades: list[dict]) -> dict:
    n = len(trades)
    if not n:
        return {"trades": 0, "win_rate": 0.0, "barrier_win_rate": 0.0, "expired_pct": 0.0,
                "expectancy_r": 0.0, "profit_factor": 0.0, "total_r": 0.0,
                "avg_win_r": 0.0, "avg_loss_r": 0.0, "wins": 0, "losses": 0}
    wins = [t["r"] for t in trades if t["r"] > 0]
    losses = [t["r"] for t in trades if t["r"] <= 0]
    gross_win, gross_loss = sum(wins), abs(sum(losses))
    # The app only scores a signal that actually touched a barrier; expiries are
    # excluded from its win rate. Report that separately so the two are comparable.
    tp_hits = sum(1 for t in trades if t["outcome"] == "WIN")
    sl_hits = sum(1 for t in trades if t["outcome"] == "LOSS")
    resolved = tp_hits + sl_hits
    return {
        "trades": n,
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": len(wins) / n * 100,
        "barrier_win_rate": (tp_hits / resolved * 100) if resolved else 0.0,
        "expired_pct": (n - resolved) / n * 100,
        "expectancy_r": sum(t["r"] for t in trades) / n,
        "total_r": sum(t["r"] for t in trades),
        "profit_factor": (gross_win / gross_loss) if gross_loss else float("inf"),
        "avg_win_r": statistics.mean(wins) if wins else 0.0,
        "avg_loss_r": statistics.mean(losses) if losses else 0.0,
    }


def row(label: str, s: dict) -> str:
    return (f"{label:<34} {s['trades']:>5}  {s['barrier_win_rate']:>6.1f}%  "
            f"{s['expired_pct']:>5.0f}%  {s['expectancy_r']:>+7.3f}R  "
            f"{s['profit_factor']:>6.2f}  {s['total_r']:>+9.1f}R")


HEADER = (f"{'configuration':<34} {'trades':>5}  {'TPwin%':>7}  {'exp':>5}  "
          f"{'expect':>8}  {'PF':>6}  {'total':>10}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", type=int, default=3)
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args()

    print(f"loading {len(UNIVERSE)} symbols, {args.years}y daily bars...")
    bars_by_ticker = {}
    for t in UNIVERSE:
        try:
            b = fetch_daily(t, args.years)
            if len(b) > 80:
                bars_by_ticker[t] = b
        except Exception as exc:
            print(f"  {t}: {exc}")
    total_bars = sum(len(b) for b in bars_by_ticker.values())
    print(f"loaded {len(bars_by_ticker)} symbols / {total_bars} bars\n")

    print(HEADER)
    print("-" * len(HEADER))

    # What the app ships today: balanced profile geometry, 24h hold.
    shipped = backtest(bars_by_ticker, 75, 3.5, 1.5, 1)
    print(row("SHIPPED (3.5/1.5 ATR, 1d hold)", shipped))

    # Same geometry, window matched to the stated 3-7 day thesis.
    fixed_window = backtest(bars_by_ticker, 75, 3.5, 1.5, 7)
    print(row("+ window fixed (7d hold)", fixed_window))

    if args.quick:
        return

    print()
    results = []
    for tp in (1.0, 1.5, 2.0, 2.5, 3.0, 3.5):
        for sl in (1.0, 1.5, 2.0):
            for hold in (5, 10, 20):
                s = backtest(bars_by_ticker, 75, tp, sl, hold)
                if s["trades"] >= 100:
                    results.append((f"tp={tp} sl={sl} hold={hold}d", s, (tp, sl, hold)))

    results.sort(key=lambda x: x[1]["expectancy_r"], reverse=True)
    print("TOP 10 BY EXPECTANCY (threshold 75)")
    print(HEADER)
    print("-" * len(HEADER))
    for label, s, _ in results[:10]:
        print(row(label, s))

    if results:
        best_label, _best, (tp_b, sl_b, hold_b) = results[0]
        print("\nCONFLUENCE THRESHOLD SWEEP (best geometry: " + best_label + ")")
        print(HEADER)
        print("-" * len(HEADER))
        thr_results = []
        for thr in (55, 60, 65, 70, 75, 80, 85):
            s = backtest(bars_by_ticker, thr, tp_b, sl_b, hold_b)
            thr_results.append((thr, s))
            print(row(f"threshold={thr}", s))

        best_thr, best_thr_s = max(thr_results, key=lambda x: x[1]["expectancy_r"])

        # Direction breakdown — a long-only bull sample can hide a broken short side.
        print(f"\nDIRECTION BREAKDOWN (screener @ threshold={best_thr}, {best_label})")
        print(HEADER)
        print("-" * len(HEADER))
        print(row(f"  LONG  ({best_thr_s['pct_long']:.0f}% of trades)", best_thr_s["by_direction"]["LONG"]))
        print(row(f"  SHORT ({100 - best_thr_s['pct_long']:.0f}% of trades)", best_thr_s["by_direction"]["SHORT"]))

        # Fair baseline: same long/short mix as the screener, entries at a fixed
        # cadence. Anything the screener earns above this is signal, not drift.
        mix = {"LONG": best_thr_s["pct_long"] / 100}
        print("\nBASELINE — identical geometry and direction mix, no screener")
        print(HEADER)
        print("-" * len(HEADER))
        base = backtest(bars_by_ticker, 0, tp_b, sl_b, hold_b,
                        use_screener=False, baseline_dir="match", dir_mix=mix)
        base_long = backtest(bars_by_ticker, 0, tp_b, sl_b, hold_b,
                             use_screener=False, baseline_dir="long")
        print(row("no screener, matched mix", base))
        print(row("no screener, long-only (beta)", base_long))
        print(row(f"screener @ threshold={best_thr}", best_thr_s))
        edge = best_thr_s["expectancy_r"] - base["expectancy_r"]
        print(f"\nscreener edge over matched-mix noise: {edge:+.3f}R per trade")

        # Long-only screener — the obvious remedy if the short side is the leak.
        lo = backtest(bars_by_ticker, best_thr, tp_b, sl_b, hold_b, dir_filter="LONG")
        print("\nLONG-ONLY SCREENER vs LONG-ONLY NOISE")
        print(HEADER)
        print("-" * len(HEADER))
        print(row("screener, LONG only", lo))
        print(row("no screener, long-only", base_long))
        print(f"\nlong-only screener edge: "
              f"{lo['expectancy_r'] - base_long['expectancy_r']:+.3f}R per trade")

        # ── Robustness. A config tuned and measured on one sample proves nothing. ──
        print("\n" + "=" * len(HEADER))
        print("ROBUSTNESS — long-only, threshold "
              f"{best_thr}, tp={tp_b} sl={sl_b} hold={hold_b}d")
        print("=" * len(HEADER))

        print("\nOUT-OF-SAMPLE SPLIT (screener vs long-only noise in each half)")
        print(HEADER)
        print("-" * len(HEADER))
        for name, (a, b) in [("first half", (0.0, 0.5)), ("second half", (0.5, 1.0))]:
            sl_bars = slice_bars(bars_by_ticker, a, b)
            s = backtest(sl_bars, best_thr, tp_b, sl_b, hold_b, dir_filter="LONG")
            nb = backtest(sl_bars, 0, tp_b, sl_b, hold_b, use_screener=False, baseline_dir="long")
            print(row(f"{name}: screener", s))
            print(row(f"{name}: noise", nb))
            print(f"{'':<34} edge {s['expectancy_r'] - nb['expectancy_r']:+.3f}R\n")

        print("PER-SYMBOL (is the edge broad, or two lucky names?)")
        print(f"{'symbol':<10} {'trades':>6}  {'TPwin%':>7}  {'expect':>8}  {'total':>9}")
        print("-" * 48)
        per: dict[str, list] = {}
        for t in lo["trades_list"]:
            per.setdefault(t["ticker"], []).append(t)
        rows = sorted(((k, summarize(v)) for k, v in per.items()),
                      key=lambda x: x[1]["expectancy_r"], reverse=True)
        for sym, s in rows:
            print(f"{sym:<10} {s['trades']:>6}  {s['barrier_win_rate']:>6.1f}%  "
                  f"{s['expectancy_r']:>+7.3f}R  {s['total_r']:>+8.1f}R")
        pos = sum(1 for _, s in rows if s["expectancy_r"] > 0)
        print(f"\n{pos}/{len(rows)} symbols positive")


if __name__ == "__main__":
    main()
