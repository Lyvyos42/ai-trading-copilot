"""
Market session awareness.

Nothing in this backend knew whether a market was open. On Sunday 2026-08-30 the
scanner ran the full 9-agent pipeline against Friday's closing prices for every
symbol on its list, wrote a row for each, and only caught the problem at the risk
gate — which blocked them on data staleness after the work was already done and
the rows already written.

A signal computed on a closed market is not a weak signal, it is not a signal:
its entry price is a stale print, its ATR is yesterday's, and its invalidation
level cannot be hit because nothing trades. Those are refused here, before the
pipeline runs.

Times are UTC. Session boundaries follow the common retail-broker convention and
are deliberately conservative — a few minutes either side of an open costs one
scan, while trading a stale print costs a bogus track record.
"""
from datetime import datetime, time, timezone

# Weekday numbers: Monday = 0 ... Sunday = 6
_FRI, _SAT, _SUN = 4, 5, 6

# FX / metals / CFDs: continuous from Sunday evening to Friday evening.
_FX_OPEN_SUN = time(21, 0)    # Sunday 21:00 UTC
_FX_CLOSE_FRI = time(21, 0)   # Friday 21:00 UTC

# US cash equities regular session, 09:30–16:00 America/New_York.
# Held in UTC at winter offset; the extra margin is absorbed by treating the
# pre/post window as closed rather than guessing the DST boundary.
_EQ_OPEN = time(14, 30)
_EQ_CLOSE = time(21, 0)

_ALWAYS_OPEN = {"crypto"}

# Instruments whose class the caller may not have set correctly.
_CRYPTO_HINTS = ("BTC", "ETH", "SOL", "XRP", "DOGE", "ADA", "-USD", "USDT")
_FX_HINTS = ("=X", "XAU", "XAG", "XPT", "XPD", "USD", "EUR", "GBP", "JPY", "CHF", "AUD", "NZD", "CAD")


# Symbols whose session is unambiguous from the ticker alone. These take
# priority over the caller's asset_class, because that label is a UI tab
# selection and is frequently wrong: the STOCKS tab sends
# asset_class="stocks" for a custom ticker, so XAUUSD arrived labelled as a US
# equity, was judged closed outside 14:30-21:00 UTC, and the resolver then
# VOIDED perfectly good gold signals. The symbol is the better evidence.
_METAL_PREFIXES = ("XAU", "XAG", "XPT", "XPD")

# ISO currency codes. A six-character symbol whose two halves are BOTH currency
# codes is an FX pair, whatever tab it was submitted from. Requiring both halves
# keeps real equity tickers out — US tickers are 1-5 characters and do not split
# into two currency codes.
_CCY = {"USD", "EUR", "GBP", "JPY", "CHF", "AUD", "NZD", "CAD", "SEK", "NOK",
        "DKK", "PLN", "ZAR", "MXN", "TRY", "HKD", "SGD", "CNH", "CZK", "HUF",
        "ILS", "THB", "RUB", "BRL", "INR", "KRW"}


def _is_fx_pair(t: str) -> bool:
    return len(t) == 6 and t[:3] in _CCY and t[3:] in _CCY


def _classify(ticker: str, asset_class: str | None) -> str:
    """Best-effort session class: 'crypto', 'fx' or 'equity'.

    The TICKER is consulted before the asset_class label wherever the symbol is
    unambiguous, because the label comes from whichever UI tab was open.
    """
    ac = (asset_class or "").lower()
    t = (ticker or "").upper()

    # 1. Unambiguous from the symbol, regardless of what the caller claimed.
    if any(h in t for h in _CRYPTO_HINTS):
        return "crypto"
    if any(t.startswith(m) for m in _METAL_PREFIXES):
        return "fx"          # spot metals follow the FX session
    if t.endswith("=X") or _is_fx_pair(t):
        return "fx"

    # 2. Otherwise trust the declared asset class.
    if ac in _ALWAYS_OPEN:
        return "crypto"
    if ac in ("fx", "forex", "commodities", "metals", "futures"):
        return "fx"
    if ac in ("stocks", "etfs", "indices", "equities", "fixed_income"):
        return "equity"
    # Unclassified: fall back on the symbol's own shape.
    if t.endswith("=X") or any(t.startswith(h) for h in ("XAU", "XAG", "XPT", "XPD")):
        return "fx"
    if len(t) == 6 and all(c.isalpha() for c in t) and any(h in t for h in _FX_HINTS):
        return "fx"
    return "equity"


def market_status(ticker: str, asset_class: str | None = None,
                  now: datetime | None = None) -> dict:
    """Return {'open': bool, 'session': str, 'reason': str, 'reopens': str|None}."""
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    kind = _classify(ticker, asset_class)
    wd, tod = now.weekday(), now.time()

    if kind == "crypto":
        return {"open": True, "session": "crypto", "reason": "Crypto trades continuously",
                "reopens": None}

    if kind == "fx":
        closed = (
            wd == _SAT
            or (wd == _FRI and tod >= _FX_CLOSE_FRI)
            or (wd == _SUN and tod < _FX_OPEN_SUN)
        )
        if closed:
            return {
                "open": False, "session": "fx",
                "reason": ("FX and metals are closed for the weekend "
                           "(Friday 21:00 UTC to Sunday 21:00 UTC)"),
                "reopens": "Sunday 21:00 UTC",
            }
        return {"open": True, "session": "fx", "reason": "FX session open", "reopens": None}

    # Equities
    if wd in (_SAT, _SUN):
        return {"open": False, "session": "equity",
                "reason": "US equity market is closed for the weekend",
                "reopens": "Monday 14:30 UTC"}
    if not (_EQ_OPEN <= tod < _EQ_CLOSE):
        return {"open": False, "session": "equity",
                "reason": ("US equity market is outside the regular session "
                           "(14:30-21:00 UTC)"),
                "reopens": "14:30 UTC"}
    return {"open": True, "session": "equity", "reason": "US equity session open",
            "reopens": None}


def is_open(ticker: str, asset_class: str | None = None,
            now: datetime | None = None) -> bool:
    return market_status(ticker, asset_class, now)["open"]
