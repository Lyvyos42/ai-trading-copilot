"""
IEF Calendar Daemon — month-end session grid for CME_REBAL_FLOW_01
==================================================================
Emits the four reference dates per calendar month that the strategy needs, built
ONLY from a published exchange holiday schedule.

WHY THIS MODULE EXISTS RATHER THAN A ONE-LINE GROUPBY:
Identifying "the 5th-to-last session of the month" by counting rows in the price
data is LOOK-AHEAD. On the decision date the remaining sessions have not
happened. Every date here is derived from weekday rules minus a published
holiday list, so the whole grid is knowable years in advance. The price feed is
consulted only to confirm a required date actually has a bar.

HORIZON IS ASSERTED, NOT ASSUMED. A holiday file that ends before the month
being planned silently produces a wrong session count, which would move the
formation date and change the signal. plan() raises instead.
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import os
from dataclasses import dataclass, asdict
from typing import Iterable

FORMATION_OFFSET = 5      # signal at the 5th-to-last session close
ENTRY_OFFSET = 4          # entry at the open of the 4th-to-last session
MIN_SESSIONS_IN_MONTH = 10
HORIZON_DAYS = 60         # holiday file must cover this far past any planned month

FORMATION, ENTRY, EXIT = "FORMATION", "ENTRY", "EXIT"


@dataclass(frozen=True)
class MonthPlan:
    month: str            # 'YYYY-MM'
    K: int                # published session count for the month
    prior_close: str      # last session of the previous month, the signal baseline
    formation: str        # 5th-to-last session: compute the signal at its close
    entry: str            # 4th-to-last session: enter at its OPEN
    exit: str             # last session: flatten at its settlement

    def as_dict(self) -> dict:
        return asdict(self)


class HolidayHorizonError(RuntimeError):
    """The holiday schedule does not extend far enough to plan the request."""


class CalendarDaemon:
    def __init__(self, holiday_csv: str, state_path: str | None = None):
        self.holiday_csv = holiday_csv
        self.state_path = state_path
        self._holidays: set[dt.date] = set()
        self._early_closes: set[dt.date] = set()
        self._ad_hoc: set[dt.date] = set()
        self._load_holidays()
        self._state: dict = self._load_state()

    @property
    def ad_hoc_closures(self) -> set[dt.date]:
        """Unscheduled closures. Not rule-derivable; a live daemon must re-plan
        if one lands on a planned step date."""
        return set(self._ad_hoc)

    def confirm_open(self, date: str) -> bool:
        """LIVE SAFETY. Call immediately before transmitting on any step date.
        An unscheduled closure discovered after planning must not become an order
        sent into a shut market."""
        return self.is_session(dt.date.fromisoformat(date))

    # -- holiday schedule ---------------------------------------------------
    def _load_holidays(self) -> None:
        """Accepts two formats.

        NEW (ief/data/exchange_holidays.csv): date,kind,source with kind in
        {holiday, early_close}. `source` distinguishes RULE_DERIVED from AD_HOC.
        AD-HOC CLOSURES MATTER: Hurricane Sandy (2012-10-29/30) shifts the
        October 2012 grid by two sessions. A rule engine cannot derive them and
        the original reference file did not contain them, so 1 of 371 historical
        months carried a formation date two sessions later than the true 5th-to-
        last session.

        LEGACY (app/data/nyse_holidays.csv): pre_holiday_date,holiday_date.
        """
        with open(self.holiday_csv, newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        if not rows:
            raise ValueError(f"{self.holiday_csv}: empty")

        if "kind" in rows[0]:
            for row in rows:
                d = (row.get("date") or "").strip()
                if not d:
                    continue
                kind = (row.get("kind") or "holiday").strip()
                src = (row.get("source") or "").strip()
                if kind == "early_close":
                    self._early_closes.add(dt.date.fromisoformat(d))
                else:
                    self._holidays.add(dt.date.fromisoformat(d))
                    if src.startswith("AD_HOC"):
                        self._ad_hoc.add(dt.date.fromisoformat(d))
        else:
            for row in rows:
                h = (row.get("holiday_date") or "").strip()
                if h:
                    self._holidays.add(dt.date.fromisoformat(h))
                p = (row.get("pre_holiday_date") or "").strip()
                if p:
                    # Early closes are VALID sessions for grid purposes, but the
                    # settlement time moves, which matters for the exit leg.
                    self._early_closes.add(dt.date.fromisoformat(p))
        if not self._holidays:
            raise ValueError(f"{self.holiday_csv}: no holiday rows parsed")

    @property
    def coverage_end(self) -> dt.date:
        return max(self._holidays)

    def is_session(self, d: dt.date) -> bool:
        return d.weekday() < 5 and d not in self._holidays

    def is_early_close(self, d: dt.date) -> bool:
        return d in self._early_closes

    def sessions_in_month(self, month: str) -> list[dt.date]:
        y, m = (int(x) for x in month.split("-"))
        d = dt.date(y, m, 1)
        out = []
        while d.month == m:
            if self.is_session(d):
                out.append(d)
            d += dt.timedelta(days=1)
        return out

    # -- planning -----------------------------------------------------------
    def month_plan(self, month: str) -> MonthPlan | None:
        """Reference dates for `month`. None if the month is not tradable."""
        y, m = (int(x) for x in month.split("-"))
        last_of_month = dt.date(y + (m == 12), (m % 12) + 1, 1) - dt.timedelta(days=1)
        if last_of_month + dt.timedelta(days=HORIZON_DAYS) > self.coverage_end:
            raise HolidayHorizonError(
                f"holiday schedule ends {self.coverage_end} but planning {month} "
                f"requires coverage through "
                f"{last_of_month + dt.timedelta(days=HORIZON_DAYS)}. "
                f"Extend {self.holiday_csv} before planning this month.")

        s = self.sessions_in_month(month)
        K = len(s)
        if K < MIN_SESSIONS_IN_MONTH or K < FORMATION_OFFSET + 1:
            return None

        pm = dt.date(y, m, 1) - dt.timedelta(days=1)
        prev = self.sessions_in_month(f"{pm.year:04d}-{pm.month:02d}")
        if not prev:
            return None

        return MonthPlan(
            month=month, K=K,
            prior_close=prev[-1].isoformat(),
            formation=s[K - FORMATION_OFFSET].isoformat(),
            entry=s[K - ENTRY_OFFSET].isoformat(),
            exit=s[-1].isoformat(),
        )

    def action_for(self, date: str) -> str | None:
        """Which step, if any, this session triggers."""
        d = dt.date.fromisoformat(date)
        plan = self.month_plan(f"{d.year:04d}-{d.month:02d}")
        if plan is None:
            return None
        if date == plan.formation:
            return FORMATION
        if date == plan.entry:
            return ENTRY
        if date == plan.exit:
            return EXIT
        return None

    def plans_between(self, start_month: str, end_month: str) -> list[MonthPlan]:
        out = []
        y, m = (int(x) for x in start_month.split("-"))
        ey, em = (int(x) for x in end_month.split("-"))
        while (y, m) <= (ey, em):
            p = self.month_plan(f"{y:04d}-{m:02d}")
            if p:
                out.append(p)
            y, m = (y + (m == 12), (m % 12) + 1)
        return out

    # -- idempotence --------------------------------------------------------
    def _load_state(self) -> dict:
        if self.state_path and os.path.exists(self.state_path):
            with open(self.state_path, encoding="utf-8") as fh:
                return json.load(fh)
        return {}

    def _save_state(self) -> None:
        if not self.state_path:
            return
        os.makedirs(os.path.dirname(self.state_path) or ".", exist_ok=True)
        with open(self.state_path, "w", encoding="utf-8") as fh:
            json.dump(self._state, fh, indent=2, sort_keys=True)

    def already_done(self, month: str, step: str) -> bool:
        return bool(self._state.get(f"{month}:{step}"))

    def mark_done(self, month: str, step: str, detail: dict | None = None) -> None:
        """Keyed on (month, step) so a restart cannot re-enter a live position."""
        self._state[f"{month}:{step}"] = {
            "at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "detail": detail or {},
        }
        self._save_state()

    def pending(self, date: str) -> tuple[str, MonthPlan] | None:
        """The step to run today, or None if there is nothing to do or it is done."""
        act = self.action_for(date)
        if act is None:
            return None
        d = dt.date.fromisoformat(date)
        plan = self.month_plan(f"{d.year:04d}-{d.month:02d}")
        if plan is None or self.already_done(plan.month, act):
            return None
        return act, plan

    # -- verification against the price feed --------------------------------
    def verify_against_feed(self, plans: Iterable[MonthPlan],
                            available_dates: set[str]) -> dict:
        """A month is tradable only if all four reference dates carry a bar.

        The CME daily files hold ~100 Globex holiday TRADE DATES the NYSE cash
        calendar lacks; that surplus is expected and harmless because reference
        dates are selected from the NYSE grid. A required date that is MISSING is
        a real gap and the month is skipped rather than silently substituted.
        """
        ok, skipped = [], []
        for p in plans:
            need = [p.prior_close, p.formation, p.entry, p.exit]
            missing = [d for d in need if d not in available_dates]
            (ok if not missing else skipped).append(
                p.month if not missing else {"month": p.month, "missing": missing})
        return {"tradable": ok, "skipped": skipped,
                "tradable_count": len(ok), "skipped_count": len(skipped)}
