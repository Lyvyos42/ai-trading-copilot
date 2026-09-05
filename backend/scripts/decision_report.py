"""REPORT — what the signal engine actually did.

Run:  python -m scripts.decision_report              (last 7 days)
      python -m scripts.decision_report --days 1
      python -m scripts.decision_report --days 30 --ticker BTC-USD

Reads `signal_decisions`, the audit log written on EVERY pipeline run, and
answers the questions a table of accepted signals cannot:

  How often does the engine decline, and for what stated reason?
  Which analysts abstain, and on which asset classes?
  Is confidence discriminating, or pinned to one value?
  Are different symbols producing IDENTICAL votes - the defect that had
    EURUSD and GBPUSD returning the same probability to one decimal?
  And once outcomes resolve: what is the measured win rate, per direction
    and per asset class.

Nothing here estimates. Every number is a count over recorded rows, and a
figure with no rows behind it prints as "-", never as zero.
"""
import argparse
import asyncio
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _pct(n: int, d: int) -> str:
    return f"{n / d * 100:5.1f}%" if d else "    -"


def _bar(n: int, total: int, width: int = 24) -> str:
    if not total:
        return ""
    filled = int(round(n / total * width))
    return "#" * filled + "." * (width - filled)


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--ticker", default=None)
    args = ap.parse_args()

    from sqlalchemy import select
    from app.db.database import AsyncSessionLocal, Base, engine
    from app.models.signal import Signal, SignalDecision

    # signal_decisions is created by create_all at server startup. Running this
    # report against a database that has never served a request would otherwise
    # fail with "no such table" - which reads like a bug rather than an empty
    # log. create_all is idempotent and never alters an existing table.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    since = datetime.utcnow() - timedelta(days=args.days)

    async with AsyncSessionLocal() as db:
        q = select(SignalDecision).where(SignalDecision.created_at >= since)
        if args.ticker:
            q = q.where(SignalDecision.ticker == args.ticker.upper())
        rows = (await db.execute(q.order_by(SignalDecision.created_at))).scalars().all()

        outcomes = (await db.execute(
            select(Signal.id, Signal.direction, Signal.asset_class, Signal.outcome)
            .where(Signal.resolved_at >= since)
            .where(Signal.outcome.in_(["WIN", "LOSS"]))
        )).all()

    print()
    print("=" * 78)
    print(f"SIGNAL ENGINE REPORT - last {args.days} day(s)"
          + (f", ticker {args.ticker.upper()}" if args.ticker else ""))
    print("=" * 78)

    if not rows:
        print()
        print("  No decisions recorded in this window.")
        print("  The audit log starts when signal_decisions was deployed; a window")
        print("  that predates it is empty rather than zero.")
        return 0

    total = len(rows)
    print()
    print(f"  {total} pipeline runs   "
          f"{len({r.ticker for r in rows})} symbols   "
          f"{sum(1 for r in rows if r.origin == 'auto_scan')} auto-scan / "
          f"{sum(1 for r in rows if r.origin == 'manual')} manual")

    # ── What came out ────────────────────────────────────────────────────────
    print()
    print("  OUTCOME OF EACH RUN")
    for status, n in Counter(r.status or "?" for r in rows).most_common():
        print(f"    {status:<20} {n:5d}  {_pct(n, total)}  {_bar(n, total)}")

    tradeable = [r for r in rows if r.status == "ACTIVE"]
    print(f"    -> {len(tradeable)} of {total} runs produced a tradeable signal "
          f"({_pct(len(tradeable), total).strip()})")

    # ── Why it declined ──────────────────────────────────────────────────────
    declines = [r for r in rows if r.status != "ACTIVE"]
    if declines:
        print()
        print("  STATED REASONS FOR DECLINING")
        reasons = Counter()
        for r in declines:
            for reason in (r.status_reasons or [])[:1]:
                reasons[str(reason)[:68]] += 1
        for reason, n in reasons.most_common(8):
            print(f"    {n:4d}  {reason}")

    # ── Direction balance ────────────────────────────────────────────────────
    dirs = Counter(r.direction or "NONE" for r in tradeable)
    if tradeable:
        print()
        print("  DIRECTION BALANCE (a healthy engine is not one-sided)")
        for d, n in dirs.most_common():
            print(f"    {d:<10} {n:5d}  {_pct(n, len(tradeable))}  {_bar(n, len(tradeable))}")
        if dirs and max(dirs.values()) / len(tradeable) > 0.85:
            print("    WARNING: over 85% one direction. That is the signature of a")
            print("             structural bias, not a market view.")

    # ── Analyst participation ────────────────────────────────────────────────
    print()
    print("  ANALYST PARTICIPATION")
    print(f"    {'agent':<16}{'voted':>8}{'abstained':>11}{'no-dir':>9}   {'market-wide':>11}")
    seen: dict[str, Counter] = defaultdict(Counter)
    for r in rows:
        for agent, v in (r.agent_votes or {}).items():
            if not isinstance(v, dict):
                continue
            if v.get("abstained"):
                seen[agent]["abstained"] += 1
            elif v.get("direction") in ("LONG", "SHORT"):
                seen[agent]["voted"] += 1
                if v.get("symbol_specific") is False:
                    seen[agent]["market_wide"] += 1
            else:
                seen[agent]["neutral"] += 1
    for agent in sorted(seen):
        c = seen[agent]
        print(f"    {agent:<16}{c['voted']:>8}{c['abstained']:>11}{c['neutral']:>9}"
              f"   {c['market_wide']:>11}")
    print("    market-wide = opinion formed without looking at that instrument.")
    print("    Those are pooled by the trader rather than counted as independent.")

    # ── Is confidence discriminating? ────────────────────────────────────────
    confs = defaultdict(list)
    for r in rows:
        for agent, v in (r.agent_votes or {}).items():
            if isinstance(v, dict) and isinstance(v.get("confidence"), (int, float)) and v["confidence"] > 0:
                confs[agent].append(round(float(v["confidence"]), 1))
    if confs:
        print()
        print("  CONFIDENCE SPREAD  (one repeated value means the number carries no")
        print("                      information - technical once returned 85 on every symbol)")
        print(f"    {'agent':<16}{'n':>6}{'distinct':>10}{'min':>8}{'max':>8}")
        for agent in sorted(confs):
            vals = confs[agent]
            flag = "   <- degenerate" if len(set(vals)) <= 2 and len(vals) >= 8 else ""
            print(f"    {agent:<16}{len(vals):>6}{len(set(vals)):>10}"
                  f"{min(vals):>8.1f}{max(vals):>8.1f}{flag}")

    # ── Identical signals across different symbols ───────────────────────────
    print()
    print("  IDENTICAL VOTE SETS ACROSS DIFFERENT SYMBOLS")
    sigs: dict[tuple, set] = defaultdict(set)
    for r in tradeable:
        key = tuple(sorted(
            (a, v.get("direction"), round(float(v.get("confidence") or 0), 1))
            for a, v in (r.agent_votes or {}).items()
            if isinstance(v, dict) and v.get("direction") in ("LONG", "SHORT")
        ))
        if key:
            sigs[key].add(r.ticker)
    collisions = {k: v for k, v in sigs.items() if len(v) > 1}
    if not collisions:
        print("    None. Every symbol produced its own vote set.")
    else:
        for k, tickers in list(collisions.items())[:6]:
            print(f"    {', '.join(sorted(tickers))}")
        print("    Different instruments returning the same votes means the ensemble")
        print("    is reading shared inputs, not independent evidence.")

    # ── Measured outcomes ────────────────────────────────────────────────────
    print()
    print("  MEASURED OUTCOMES")
    if not outcomes:
        print("    No signals have resolved in this window yet, so the win rate is")
        print("    UNMEASURED. It is not 0%.")
    else:
        wins = sum(1 for _, _, _, o in outcomes if o == "WIN")
        print(f"    {len(outcomes)} resolved   {wins}W / {len(outcomes) - wins}L   "
              f"win rate {_pct(wins, len(outcomes)).strip()}")
        by_dir = defaultdict(lambda: [0, 0])
        by_cls = defaultdict(lambda: [0, 0])
        for _sid, d, cls, o in outcomes:
            by_dir[d or "?"][o == "WIN"] += 1
            by_cls[cls or "?"][o == "WIN"] += 1
        print(f"    {'by direction':<18}{'n':>5}{'win rate':>11}")
        for d, (loss, win) in sorted(by_dir.items()):
            print(f"    {d:<18}{loss + win:>5}{_pct(win, loss + win):>11}")
        print(f"    {'by asset class':<18}{'n':>5}{'win rate':>11}")
        for c, (loss, win) in sorted(by_cls.items()):
            print(f"    {c:<18}{loss + win:>5}{_pct(win, loss + win):>11}")
        if len(outcomes) < 30:
            print("    NOTE: under 30 resolved signals. Treat this as an early")
            print("    indication, not a track record - the confidence interval on")
            print("    a win rate this size is roughly +/-18 points.")

    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
