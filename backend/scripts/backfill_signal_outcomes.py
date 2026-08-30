"""
One-shot backfill: re-score the existing track record against real price history.

Every outcome recorded before the resolver fix was produced by comparing a
single spot price at page-render time, and auto-scanned signals were given 24h
to reach a target sized for their full analytical window. Both effects push
results toward LOSS regardless of whether the signal was any good, so the stored
outcomes cannot be trusted and are not evidence about the model either way.

This script:
  1. recomputes expiry_time from each signal's own analytical_window,
  2. clears outcomes that were written by the old snapshot logic,
  3. re-resolves every signal by walking its actual OHLC path.

Dry run (prints what would change, writes nothing):
    python -m scripts.backfill_signal_outcomes

Apply:
    python -m scripts.backfill_signal_outcomes --apply
"""
import argparse
import asyncio
import os
import sys
from collections import Counter
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select  # noqa: E402

from app.db.database import AsyncSessionLocal  # noqa: E402
# Every model must be imported so signals.user_id can resolve its FK to users.
import app.models.user  # noqa: E402,F401
import app.models.portfolio  # noqa: E402,F401
import app.models.news  # noqa: E402,F401
import app.models.alert  # noqa: E402,F401
import app.models.memory  # noqa: E402,F401
from app.models.signal import Signal  # noqa: E402
from app.services.signal_resolver import resolve_open_signals, window_to_hours  # noqa: E402

# Outcomes produced by the old snapshot logic. VOID is ours and stays put.
_STALE = ("WIN", "LOSS", "EXPIRED")


async def main(apply: bool, batch: int) -> None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Signal))
        signals = result.scalars().all()

        before = Counter(s.outcome or "UNRESOLVED" for s in signals)
        print(f"{len(signals)} signals in the table")
        print("  before:", dict(before))

        expiry_fixed = 0
        reopened = 0
        for s in signals:
            hours = window_to_hours(s.analytical_window)
            if s.created_at:
                corrected = s.created_at + timedelta(hours=hours)
                if s.expiry_time != corrected:
                    s.expiry_time = corrected
                    expiry_fixed += 1
            if s.outcome in _STALE:
                s.status = "ACTIVE"
                s.outcome = None
                s.exit_price = None
                s.pnl_pct = None
                s.resolved_at = None
                s.max_favorable_excursion = None
                s.max_adverse_excursion = None
                reopened += 1

        print(f"  expiry_time corrected on {expiry_fixed} signals")
        print(f"  {reopened} previously-scored signals reopened for re-resolution")

        if not apply:
            await session.rollback()
            print("\nDRY RUN — nothing written. Re-run with --apply to commit.")
            return

        await session.commit()

        print("\nre-resolving against OHLC history...")
        open_result = await session.execute(
            select(Signal).where(Signal.status == "ACTIVE").order_by(Signal.created_at)
        )
        open_signals = list(open_result.scalars().all())
        # Explicit non-overlapping slices: re-querying for ACTIVE each round would
        # keep re-fetching bars for signals that are legitimately still open.
        for i in range(0, len(open_signals), batch):
            chunk = open_signals[i:i + batch]
            stats = await resolve_open_signals(session, signals=chunk)
            print(f"  batch {i // batch + 1}: checked={stats['checked']} "
                  f"resolved={stats['resolved']} {stats['counts']}")

        result = await session.execute(select(Signal))
        after = Counter(s.outcome or "UNRESOLVED" for s in result.scalars().all())
        print("\n  after:", dict(after))
        wins, losses = after.get("WIN", 0), after.get("LOSS", 0)
        if wins + losses:
            print(f"  honest win rate: {wins}W / {losses}L = {wins / (wins + losses) * 100:.1f}%")
        else:
            print("  no signals resolved to WIN/LOSS — all still open, expired, or void")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="commit changes (default is a dry run)")
    ap.add_argument("--batch", type=int, default=100, help="signals per resolver batch")
    asyncio.run(main(ap.parse_args().apply, ap.parse_args().batch))
