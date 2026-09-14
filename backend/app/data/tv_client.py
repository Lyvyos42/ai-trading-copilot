"""The one TradingView historical-data client in this process.

Every caller of tvDatafeed goes through `get_hist` here. There is no other path.

WHY A SINGLE GATE

tvDatafeed is not safe to share. Measured in its source (1.2.1, commit cfc26940):

  * `get_hist` REASSIGNS `self.ws` to a brand-new websocket on every call and reuses
    the instance's session ids, so two threads calling one instance write frames
    into each other's sockets - the collisions seen in production.
  * `create_connection` is called WITHOUT a timeout, so `ws.recv()` blocks forever
    on a silent connection. The recv loop only exits on "series_completed" or an
    exception.
  * The previous socket is never closed. Every call leaked one.

Two call sites used that shared instance - market_data._fetch_tvdatafeed and
tv_bars - and only one of them held a lock.

WHAT THIS DOES ABOUT EACH

  1. One process-wide lock guards the client REFERENCE and every call on it.
  2. The call runs in a worker thread under a hard deadline. On expiry the socket is
     aborted (which makes the blocked recv raise) and the client is DISCARDED, so the
     lock is released even if the worker never returns - the stuck worker holds its
     own reference to an instance nobody else will touch again.
  3. The socket is closed after every call, successful or not.
  4. A fast failure is retried once on a fresh client (a dropped socket is the common
     case). A timeout is not retried - it has already cost the deadline.
  5. A circuit breaker: after BREAKER_THRESHOLD consecutive connection-level failures
     (exceptions or timeouts - not an empty result for one symbol) the gate opens for
     BREAKER_COOLDOWN_S and callers fail immediately. A host TradingView blocks (a
     datacentre IP) then costs microseconds per request instead of a deadline each.
     `status()` exposes the state for /health.
"""
from __future__ import annotations

import threading
import time
from typing import Any, Optional

import structlog

log = structlog.get_logger()

CALL_TIMEOUT_S = 25.0
LOCK_WAIT_S = 30.0
BREAKER_THRESHOLD = 3
BREAKER_COOLDOWN_S = 300.0

_LOCK = threading.Lock()
_state: dict[str, Any] = {
    "client": None,
    "consecutive_failures": 0,
    "open_until": 0.0,
    "last_error": None,
    "last_ok_epoch": None,
    "calls": 0,
    "timeouts": 0,
    "breaker_trips": 0,
}


class TVUnavailable(RuntimeError):
    """TradingView could not serve this request."""


def _new_client():
    """Constructed lazily; patched in tests."""
    from tvDatafeed import TvDatafeed
    return TvDatafeed()


def _close_socket(client) -> None:
    ws = getattr(client, "ws", None)
    if ws is None:
        return
    for method in ("abort", "close"):
        fn = getattr(ws, method, None)
        if fn is not None:
            try:
                fn()
            except Exception:
                pass


def _record_failure(reason: str, connection_level: bool) -> None:
    _state["last_error"] = reason
    if not connection_level:
        return
    _state["consecutive_failures"] += 1
    if _state["consecutive_failures"] >= BREAKER_THRESHOLD:
        _state["open_until"] = time.monotonic() + BREAKER_COOLDOWN_S
        _state["breaker_trips"] += 1
        _state["consecutive_failures"] = 0
        log.warning("tradingview_circuit_open", cooldown_s=BREAKER_COOLDOWN_S,
                    last_error=reason,
                    consequence="TradingView requests fail fast until the cooldown ends")


def _attempt(client, symbol: str, exchange: str, interval, n_bars: int,
             timeout: float) -> tuple[Optional[Any], Optional[str], bool]:
    """(df, error, timed_out). Never raises."""
    box: dict[str, Any] = {}

    def work():
        try:
            box["df"] = client.get_hist(symbol=symbol, exchange=exchange,
                                        interval=interval, n_bars=n_bars)
        except Exception as exc:
            box["err"] = f"{type(exc).__name__}: {exc}"

    worker = threading.Thread(target=work, name=f"tv-hist-{exchange}:{symbol}", daemon=True)
    worker.start()
    worker.join(timeout)
    if worker.is_alive():
        _close_socket(client)             # makes the blocked recv raise
        worker.join(2.0)
        return None, f"timed out after {timeout:.0f}s", True
    _close_socket(client)                 # tvDatafeed never closes its own sockets
    return box.get("df"), box.get("err"), False


def get_hist(symbol: str, exchange: str, interval, n_bars: int,
             timeout: float = CALL_TIMEOUT_S):
    """A DataFrame of bars, or raise TVUnavailable. Thread-safe."""
    if time.monotonic() < _state["open_until"]:
        raise TVUnavailable(
            f"TradingView circuit open for another "
            f"{_state['open_until'] - time.monotonic():.0f}s after repeated failures "
            f"(last: {_state['last_error']})")
    if not _LOCK.acquire(timeout=LOCK_WAIT_S):
        raise TVUnavailable(f"TradingView client busy for more than {LOCK_WAIT_S:.0f}s")
    try:
        _state["calls"] += 1
        for attempt in (1, 2):
            client = _state["client"]
            if client is None:
                try:
                    client = _state["client"] = _new_client()
                except Exception as exc:
                    reason = f"client construction failed: {type(exc).__name__}: {exc}"
                    _record_failure(reason, connection_level=True)
                    raise TVUnavailable(reason) from exc

            df, err, timed_out = _attempt(client, symbol, exchange, interval, n_bars, timeout)
            if df is not None and len(df) > 0:
                _state["consecutive_failures"] = 0
                _state["last_ok_epoch"] = int(time.time())
                return df

            # Any failure discards the instance: its socket and session state are
            # suspect, and a stuck worker may still hold it.
            _state["client"] = None
            if timed_out:
                _state["timeouts"] += 1
                _record_failure(f"{exchange}:{symbol} {err}", connection_level=True)
                raise TVUnavailable(f"TradingView {exchange}:{symbol} {err}")
            if err is not None:
                if attempt == 1:
                    continue                       # one retry on a fresh client
                _record_failure(f"{exchange}:{symbol} {err}", connection_level=True)
                raise TVUnavailable(f"TradingView {exchange}:{symbol} failed: {err}")
            if attempt == 1:
                continue
            # Empty twice with no exception: a symbol-level answer, not a dead host.
            _record_failure(f"{exchange}:{symbol} returned no bars", connection_level=False)
            raise TVUnavailable(f"TradingView returned no bars for {exchange}:{symbol}")
    finally:
        _LOCK.release()


def status() -> dict:
    now = time.monotonic()
    return {
        "circuit_open": now < _state["open_until"],
        "circuit_open_remaining_s": max(0, int(_state["open_until"] - now)),
        "consecutive_failures": _state["consecutive_failures"],
        "last_error": _state["last_error"],
        "last_ok_epoch": _state["last_ok_epoch"],
        "calls": _state["calls"],
        "timeouts": _state["timeouts"],
        "breaker_trips": _state["breaker_trips"],
        "client_connected": _state["client"] is not None,
    }


def _reset_for_tests() -> None:
    with _LOCK:
        _state.update(client=None, consecutive_failures=0, open_until=0.0, last_error=None,
                      last_ok_epoch=None, calls=0, timeouts=0, breaker_trips=0)
