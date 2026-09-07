"""Discretionary macro overlay: append-only, hash-chained, point-in-time.

WHY THIS FILE IS SHAPED THE WAY IT IS

A discretionary bias that gates automated signals converts a measurable system
into an unmeasurable one, unless the bias itself is recorded as data. If the
operator sets HAWKISH_USD on Tuesday and the record is later edited, or simply
overwritten by the next state, then two things become impossible: attributing
forward P&L to the overlay rather than the strategy, and ever backtesting the
combined system, because the historical permission states no longer exist.

So the overlay is a LOG, not a variable. Three properties follow, and each is
enforced rather than documented:

    append-only     writes go to the end of macro_state_audit.jsonl; nothing
                    in the file is ever rewritten
    monotonic       a record whose timestamp is not strictly after the last
                    record's is REFUSED, which is what makes retroactive
                    insertion an error rather than a convention
    hash-chained    each record carries the SHA-256 of the previous one. A
                    plain JSONL can be edited silently and still parse; a
                    chain cannot. verify() walks it and names the first break.

The function that makes future research possible is state_at(). It reconstructs
what the operator's permission actually was at any past instant, from the log
alone. Without it, a backtest of the hierarchical architecture would have to
assume the current bias held for all history - which would be the same error as
the consensus_9 macro agent, and it would look like a regime filter while
actually being a constant.

HISTORY_CHANGED is deliberately sticky. Declaring it puts every automated
strategy into non-executing observer mode, and only an explicit REQUALIFIED
record clears it. There is no timeout: an unfalsifiable escape hatch that
expires on its own is worse than one that has to be closed by hand, because
nobody has to look at it again.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Iterator, Optional

DEFAULT_LOG = Path(__file__).resolve().parents[1] / "data" / "macro_state_audit.jsonl"


class MacroBias(str, Enum):
    HAWKISH_USD = "HAWKISH_USD"
    DOVISH_USD = "DOVISH_USD"
    RISK_ON = "RISK_ON"
    RISK_OFF = "RISK_OFF"
    GOLD_SOVEREIGN_BID = "GOLD_SOVEREIGN_BID"
    NEUTRAL = "NEUTRAL_STAND_ASIDE"


class RecordType(str, Enum):
    BIAS = "BIAS"
    HISTORY_CHANGED = "HISTORY_CHANGED"
    REQUALIFIED = "REQUALIFIED"


class ExecutionMode(str, Enum):
    EXECUTING = "executing"
    OBSERVER = "observer"          # computed and logged, never sent to a broker


# Instrument classification. Explicit tables rather than string heuristics: a
# rule like "endswith USD" silently misclassifies USDCHF, and a permission gate
# that inverts on one instrument is worse than no gate.
USD_QUOTE = ("EURUSD", "GBPUSD", "AUDUSD", "NZDUSD", "XAUUSD", "XAGUSD")
USD_BASE = ("USDJPY", "USDCHF", "USDCAD")
EQUITY_INDEX = ("SP500", "NASDAQ", "US30", "SPY", "QQQ", "IWM", "DIA",
                "ES", "NQ", "MES", "MNQ")
METALS = ("XAUUSD", "XAGUSD")
JPY_CROSS = ("EURJPY", "GBPJPY", "AUDJPY", "USDJPY")

LONG, SHORT, FLAT = 1, -1, 0


@dataclass(frozen=True)
class MacroState:
    """The overlay as of some instant. Reconstructed, never stored."""
    bias: MacroBias = MacroBias.NEUTRAL
    scope: str = "*"
    mode: ExecutionMode = ExecutionMode.EXECUTING
    history_changed: bool = False
    since: Optional[str] = None          # when THIS state began
    bias_since: Optional[str] = None     # when the BIAS itself was set
    bias_operator: Optional[str] = None
    trigger: Optional[str] = None
    operator: Optional[str] = None
    note: Optional[str] = None
    seq: int = 0

    def permits(self, symbol: str, side: int) -> bool:
        return side != FLAT and side == self.permitted_side(symbol)

    def permitted_side(self, symbol: str) -> int:
        """Which direction Tier 1 allows on this instrument. FLAT means none.

        Tier 2 may only execute setups congruent with this. It never overrides.
        """
        if self.history_changed or self.mode is ExecutionMode.OBSERVER:
            return FLAT
        s = symbol.upper().replace("=F", "").replace("=X", "")
        if self.scope not in ("*", s):
            return FLAT
        b = self.bias
        if b is MacroBias.NEUTRAL:
            return FLAT
        if b is MacroBias.GOLD_SOVEREIGN_BID:
            return LONG if s in METALS else FLAT
        if b in (MacroBias.HAWKISH_USD, MacroBias.DOVISH_USD):
            hawk = b is MacroBias.HAWKISH_USD
            # Gold is priced in USD and trades against real yields, so a
            # hawkish-USD regime is a headwind for it in the same direction as
            # for EURUSD. It is classified with the USD-quote pairs, not given
            # a bespoke rule.
            if s in USD_QUOTE:
                return SHORT if hawk else LONG
            if s in USD_BASE:
                return LONG if hawk else SHORT
            return FLAT
        if b in (MacroBias.RISK_ON, MacroBias.RISK_OFF):
            on = b is MacroBias.RISK_ON
            if s in EQUITY_INDEX:
                return LONG if on else SHORT
            # The yen bids in risk-off, so USDJPY falls: risk-off is SHORT
            # USDJPY. Only USDJPY is mapped here; the JPY crosses carry a
            # second currency's story and are left unpermitted on purpose.
            if s == "USDJPY":
                return LONG if on else SHORT
            return FLAT
        return FLAT


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _digest(rec: dict) -> str:
    body = {k: v for k, v in rec.items() if k != "hash"}
    return hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


class MacroLog:
    """Append-only, hash-chained audit log of the discretionary overlay."""

    def __init__(self, path: Path | str = DEFAULT_LOG):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    # -- reading -----------------------------------------------------------
    def records(self) -> Iterator[dict]:
        if not self.path.exists():
            return
        with self.path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    yield json.loads(line)

    def last(self) -> Optional[dict]:
        out = None
        for r in self.records():
            out = r
        return out

    def state_at(self, when: Optional[datetime | str] = None) -> MacroState:
        """The overlay as it stood at `when`. This is what makes a backtest of
        the combined system possible: permission is replayed, never assumed."""
        cutoff = None
        if when is not None:
            cutoff = when if isinstance(when, str) else \
                when.astimezone(timezone.utc).isoformat(timespec="microseconds")
        st = MacroState()
        for r in self.records():
            if cutoff is not None and r["ts_utc"] > cutoff:
                break
            rt = RecordType(r["record_type"])
            if rt is RecordType.BIAS:
                st = MacroState(
                    bias=MacroBias(r["bias"]), scope=r.get("scope", "*"),
                    mode=st.mode, history_changed=st.history_changed,
                    since=r["ts_utc"], bias_since=r["ts_utc"],
                    bias_operator=r.get("operator"), trigger=st.trigger,
                    operator=r.get("operator"), note=r.get("note"),
                    seq=r["seq"])
            elif rt is RecordType.HISTORY_CHANGED:
                st = MacroState(
                    bias=st.bias, scope=st.scope,
                    mode=ExecutionMode.OBSERVER, history_changed=True,
                    since=r["ts_utc"], bias_since=st.bias_since,
                    bias_operator=st.bias_operator, trigger=r.get("trigger"),
                    operator=r.get("operator"), note=r.get("note"),
                    seq=r["seq"])
            elif rt is RecordType.REQUALIFIED:
                st = MacroState(
                    bias=st.bias, scope=st.scope,
                    mode=ExecutionMode.EXECUTING, history_changed=False,
                    since=r["ts_utc"], bias_since=st.bias_since,
                    bias_operator=st.bias_operator, trigger=None,
                    operator=r.get("operator"), note=r.get("note"),
                    seq=r["seq"])
        return st

    def current(self) -> MacroState:
        return self.state_at(None)

    # -- writing -----------------------------------------------------------
    def _append(self, rec: dict) -> dict:
        prev = self.last()
        if prev is not None and rec["ts_utc"] <= prev["ts_utc"]:
            raise ValueError(
                f"non-monotonic timestamp: {rec['ts_utc']} is not after "
                f"{prev['ts_utc']}. The log is append-only and states are "
                f"never inserted behind existing ones.")
        rec["seq"] = (prev["seq"] + 1) if prev else 1
        rec["prev_hash"] = prev["hash"] if prev else None
        rec["hash"] = _digest(rec)
        line = json.dumps(rec, sort_keys=True, separators=(",", ":"))
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        return rec

    def set_bias(self, bias: MacroBias, operator: str, note: str = "",
                 scope: str = "*") -> dict:
        return self._append({
            "ts_utc": _now(), "record_type": RecordType.BIAS.value,
            "bias": MacroBias(bias).value, "scope": scope.upper(),
            "operator": operator, "note": note, "trigger": None})

    def declare_history_changed(self, trigger: str, operator: str,
                                note: str = "") -> dict:
        """Structural break. Every automated strategy drops to observer mode
        and stays there until requalify() is called by hand."""
        return self._append({
            "ts_utc": _now(),
            "record_type": RecordType.HISTORY_CHANGED.value,
            "bias": None, "scope": "*", "operator": operator,
            "note": note, "trigger": trigger})

    def requalify(self, operator: str, note: str = "") -> dict:
        return self._append({
            "ts_utc": _now(), "record_type": RecordType.REQUALIFIED.value,
            "bias": None, "scope": "*", "operator": operator,
            "note": note, "trigger": None})

    # -- integrity ---------------------------------------------------------
    def verify(self) -> list[str]:
        """Walk the chain. Returns the problems found, empty if intact."""
        problems: list[str] = []
        prev = None
        for n, r in enumerate(self.records(), 1):
            if r.get("seq") != n:
                problems.append(f"record {n}: seq is {r.get('seq')}, expected {n}")
            want_prev = prev["hash"] if prev else None
            if r.get("prev_hash") != want_prev:
                problems.append(
                    f"record {n} (seq {r.get('seq')}): prev_hash does not match "
                    f"the preceding record - the log has been edited or a "
                    f"record was removed")
            if r.get("hash") != _digest(r):
                problems.append(
                    f"record {n} (seq {r.get('seq')}): contents do not match "
                    f"their own hash - this record was modified in place")
            if prev is not None and r["ts_utc"] <= prev["ts_utc"]:
                problems.append(
                    f"record {n}: timestamp {r['ts_utc']} is not after "
                    f"{prev['ts_utc']}")
            prev = r
        return problems


def gate(state: MacroState, symbol: str, side: int) -> tuple[bool, str]:
    """Tier 1 permission check. Returns (allowed, reason).

    The reason is always populated, including on success, so a declined trade
    can explain itself in the same terms as an accepted one.
    """
    if state.history_changed:
        return False, (f"HISTORY_CHANGED declared at {state.since} "
                       f"(trigger: {state.trigger}); automated execution is in "
                       f"observer mode until requalified")
    if state.mode is ExecutionMode.OBSERVER:
        return False, f"execution mode is observer since {state.since}"
    allowed = state.permitted_side(symbol)
    if allowed == FLAT:
        return False, (f"macro bias {state.bias.value} grants no directional "
                       f"permission on {symbol}")
    if side != allowed:
        return False, (f"macro bias {state.bias.value} permits only "
                       f"{'LONG' if allowed > 0 else 'SHORT'} on {symbol}; "
                       f"Tier 2 proposed "
                       f"{'LONG' if side > 0 else 'SHORT'}")
    return True, (f"congruent with macro bias {state.bias.value} "
                  f"(set {state.bias_since} by {state.bias_operator}; "
                  f"state effective since {state.since})")
