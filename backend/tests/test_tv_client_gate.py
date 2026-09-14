"""
app/data/tv_client.py - the single TradingView gate.

Fake clients reproduce tvDatafeed's real hazards (shared mutable socket, a recv that
never returns, sockets left open) so each guarantee is tested against the failure it
exists to prevent. No network.

Run:  .venv/Scripts/python.exe -m pytest -q tests/test_tv_client_gate.py
"""
from __future__ import annotations

import os
import sys
import threading
import time

import pandas as pd

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

from app.data import tv_client  # noqa: E402


def _df(n=3):
    return pd.DataFrame({"open": [1.0] * n, "high": [1.0] * n, "low": [1.0] * n,
                         "close": [1.0] * n, "volume": [1.0] * n})


class _WS:
    def __init__(self):
        self.closed = threading.Event()

    def abort(self):
        self.closed.set()

    def close(self):
        self.closed.set()


class OverlapDetector:
    """Raises if two get_hist calls are ever inside it at once."""
    inside = 0
    overlaps = 0
    guard = threading.Lock()

    def __init__(self):
        self.ws = None

    def get_hist(self, symbol, exchange, interval, n_bars):
        with OverlapDetector.guard:
            OverlapDetector.inside += 1
            if OverlapDetector.inside > 1:
                OverlapDetector.overlaps += 1
        self.ws = _WS()
        time.sleep(0.02)
        with OverlapDetector.guard:
            OverlapDetector.inside -= 1
        return _df()


class Hangs:
    """recv never returns until the socket is aborted - tvDatafeed with no timeout."""
    instances = []

    def __init__(self):
        self.ws = _WS()
        Hangs.instances.append(self)

    def get_hist(self, symbol, exchange, interval, n_bars):
        self.ws.closed.wait(60)
        raise ConnectionError("socket aborted")


class Raises:
    def __init__(self):
        self.ws = _WS()

    def get_hist(self, **k):
        raise ConnectionError("403 Forbidden")


class Empty:
    def __init__(self):
        self.ws = _WS()

    def get_hist(self, **k):
        return _df(0)


def _with(factory, fn):
    old = tv_client._new_client
    tv_client._reset_for_tests()
    tv_client._new_client = factory
    try:
        return fn()
    finally:
        tv_client._new_client = old
        tv_client._reset_for_tests()


def test_concurrent_calls_never_share_the_client():
    OverlapDetector.inside = OverlapDetector.overlaps = 0

    def run():
        errs = []

        def worker(i):
            try:
                tv_client.get_hist(f"S{i}", "CME", "D", 10)
            except Exception as exc:
                errs.append(exc)
        ts = [threading.Thread(target=worker, args=(i,)) for i in range(12)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        return errs
    errs = _with(OverlapDetector, run)
    assert not errs and OverlapDetector.overlaps == 0


def test_socket_closed_after_every_call():
    holder = {}

    def factory():
        holder["c"] = OverlapDetector()
        return holder["c"]
    _with(factory, lambda: tv_client.get_hist("ES1!", "CME", "D", 10))
    assert holder["c"].ws.closed.is_set()


def test_hung_call_times_out_releases_lock_and_discards_client():
    Hangs.instances = []

    def run():
        t0 = time.monotonic()
        try:
            tv_client.get_hist("ES1!", "CME", "D", 10, timeout=0.3)
            raise AssertionError("expected TVUnavailable")
        except tv_client.TVUnavailable as exc:
            assert "timed out" in str(exc)
        assert time.monotonic() - t0 < 3.0
        st = tv_client.status()
        assert st["timeouts"] == 1 and st["client_connected"] is False
        assert Hangs.instances[0].ws.closed.is_set(), "blocked recv was not aborted"
        # lock is free: the next call proceeds (and gets a NEW client)
        tv_client._new_client = OverlapDetector
        assert len(tv_client.get_hist("NQ1!", "CME", "D", 10)) == 3
    _with(Hangs, run)


def test_breaker_opens_after_repeated_connection_failures_and_fails_fast():
    def run():
        for _ in range(tv_client.BREAKER_THRESHOLD):
            try:
                tv_client.get_hist("ES1!", "CME", "D", 10)
            except tv_client.TVUnavailable:
                pass
        assert tv_client.status()["circuit_open"] is True
        t0 = time.monotonic()
        try:
            tv_client.get_hist("ES1!", "CME", "D", 10)
            raise AssertionError("breaker did not fail fast")
        except tv_client.TVUnavailable as exc:
            assert "circuit open" in str(exc)
        assert time.monotonic() - t0 < 0.05
    _with(Raises, run)


def test_empty_result_for_a_symbol_does_not_trip_the_breaker():
    def run():
        for _ in range(tv_client.BREAKER_THRESHOLD + 2):
            try:
                tv_client.get_hist("NOPE", "CME", "D", 10)
            except tv_client.TVUnavailable as exc:
                assert "no bars" in str(exc)
        assert tv_client.status()["circuit_open"] is False
    _with(Empty, run)


def test_transient_failure_is_retried_once_on_a_fresh_client():
    calls = {"n": 0}

    def factory():
        calls["n"] += 1
        return Raises() if calls["n"] == 1 else OverlapDetector()
    df = _with(factory, lambda: tv_client.get_hist("ES1!", "CME", "D", 10))
    assert len(df) == 3 and calls["n"] == 2


def test_first_construction_never_reaches_the_stdin_prompt():
    """tvDatafeed prompts on stdin when its cache dir is missing; a server has none."""
    import tempfile
    import types

    tmp = tempfile.mkdtemp()
    base = os.path.join(tmp, ".tv_datafeed") + os.sep

    class PromptingTvDatafeed:
        path = base

        def __init__(self):
            if not os.path.exists(self.path):
                os.mkdir(self.path)
                raise EOFError("EOF when reading a line")   # input() with no stdin
            self.ws = None

        def get_hist(self, symbol, exchange, interval, n_bars):
            return _df()

    fake = types.ModuleType("tvDatafeed")
    fake.TvDatafeed = PromptingTvDatafeed
    saved = sys.modules.get("tvDatafeed")
    sys.modules["tvDatafeed"] = fake
    tv_client._reset_for_tests()
    try:
        df = tv_client.get_hist("ES1!", "CME", "D", 10)
        assert len(df) == 3
        assert tv_client.status()["last_error"] is None
        assert os.path.isdir(os.path.join(base, "chrome"))
    finally:
        if saved is not None:
            sys.modules["tvDatafeed"] = saved
        else:
            sys.modules.pop("tvDatafeed", None)
        tv_client._reset_for_tests()


def test_construction_failure_is_retried_once():
    calls = {"n": 0}

    def factory():
        calls["n"] += 1
        if calls["n"] == 1:
            raise EOFError("EOF when reading a line")
        return OverlapDetector()
    df = _with(factory, lambda: tv_client.get_hist("ES1!", "CME", "D", 10))
    assert len(df) == 3 and calls["n"] == 2


def test_unknown_symbol_fails_fast_without_tripping_breaker():
    """TradingView answers a bad symbol with symbol_error and never completes."""
    class _Sock:
        def __init__(self):
            self.frames = iter([
                '~m~87~m~{"m":"critical_error","p":["qs_x","invalid_parameters"]}',
                '~m~60~m~{"m":"symbol_error","p":["cs_x","symbol_1","invalid symbol"]}',
            ])
            self.closed = threading.Event()

        def recv(self):
            try:
                return next(self.frames)
            except StopIteration:
                self.closed.wait(60)          # TradingView goes quiet
                raise ConnectionError("aborted")

        def abort(self):
            self.closed.set()

        def close(self):
            self.closed.set()

    class FakeTv:
        def __init__(self):
            self.ws = None
            self.constructed = True

        def _TvDatafeed__create_connection(self):
            self.ws = _Sock()

        def get_hist(self, symbol, exchange, interval, n_bars):
            self._TvDatafeed__create_connection()
            while True:
                try:
                    frame = self.ws.recv()
                except Exception:
                    break
                if "series_completed" in frame:
                    break
            return None

    def run():
        t0 = time.monotonic()
        for _ in range(tv_client.BREAKER_THRESHOLD + 1):
            try:
                tv_client.get_hist("ES1!", "CME", "D", 10, timeout=5)
                raise AssertionError("expected TVUnavailable")
            except tv_client.TVUnavailable as exc:
                assert "symbol_error" in str(exc)
        assert time.monotonic() - t0 < 2.0, "symbol error waited for the deadline"
        st = tv_client.status()
        assert st["circuit_open"] is False and st["timeouts"] == 0
    _with(lambda: tv_client._watch_symbol_errors(FakeTv()), run)


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"PASS  {name}")
        except Exception as exc:
            failed += 1
            print(f"FAIL  {name}: {type(exc).__name__}: {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
