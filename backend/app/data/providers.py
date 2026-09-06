"""Market data sources, each declaring what it actually is.

WHY THIS EXISTS

The chart was fed by Yahoo's consumer chart endpoint and CoinGecko's /ohlc,
and neither of them says what it is returning. That silence caused real
defects, measured on 2026-09-06:

  * Spot FX on Yahoo carries NO volume. Not "sometimes" - 1440 of 1440
    USDJPY 5m bars came back zero, and 1440 of 1440 on EURUSD. There is no
    consolidated tape for spot FX, so this is structural and no amount of
    retrying fixes it.
  * CoinGecko's /ohlc endpoint returns no volume field at all; the caller
    hardcoded "volume": 0. So the primary crypto path had none either.
  * CoinGecko's /ohlc silently changes candle width with the day range -
    30 minutes under 2 days, 4 hours under 30, a day beyond that - so a
    request for 5m candles returned daily bars and nothing said so.
  * Yahoo's crypto composite sat $44 (0.055%) away from Binance's BTCUSDT
    at the same instant, and only 596 of 1330 5m bars carried volume.

Downstream, a chart that cannot tell "no volume" from "zero volume" will
draw a volume profile out of nothing. That is what it did.

So every response from here carries a Provenance record. It is not
decoration: the frontend gates the volume profile, the relative-volume
bubbles and the modelled depth ladder on it.

WHAT IS ACTUALLY AVAILABLE, AND WHY THIS SET

Binance and Coinbase are exchanges. Asking them about their own tape is
real-time and the volume is genuinely traded volume, so crypto is served
from a venue rather than from an aggregator. Neither needs a key.

Everything else needs either a key or a compromise, and no market data key is
currently set on this deployment - POLYGON_API_KEY exists in .env but is
empty. Yahoo therefore remains the fallback for equities, futures and indices
- where its volume IS real and the only problem is latency - and it is
labelled as the delayed consumer feed that it is rather than presented as a
market feed.

MEASURED, NOT ASSERTED

Rather than hardcode "15 minutes delayed", every response reports
`last_bar_age_seconds`: how old the newest bar was when it arrived. During
market hours that IS the delay, observed. It is a fact the caller can show
the user instead of a claim from this docstring.
"""
from __future__ import annotations

import logging
import os
import time
from dataclasses import asdict, dataclass, replace
from typing import Any, Optional

import httpx

log = logging.getLogger(__name__)

Candle = dict[str, Any]

# Volume semantics. These are NOT interchangeable and the chart renders them
# differently, so they are named rather than left to a boolean.
VOL_TRADED = "traded"      # contracts/coins/shares actually exchanged
VOL_TICK = "tick_count"    # number of price updates - a proxy, not size
VOL_NONE = "none"          # the feed publishes none


@dataclass(frozen=True)
class Provenance:
    source: str
    venue: str
    is_realtime: bool
    has_volume: bool
    volume_kind: str
    license: str
    note: str
    quote_currency: Optional[str] = None
    requested_symbol: Optional[str] = None
    resolved_symbol: Optional[str] = None
    # Observed, filled in by the router once candles are in hand.
    last_bar_age_seconds: Optional[int] = None
    bar_count: Optional[int] = None

    def to_dict(self) -> dict:
        return asdict(self)


_PERIOD_DAYS = {"1d": 1, "5d": 5, "1mo": 30, "3mo": 90, "6mo": 180, "1y": 365, "2y": 730}
_INTERVAL_SECONDS = {
    "1m": 60, "5m": 300, "15m": 900, "30m": 1800,
    "1h": 3600, "4h": 14400, "1d": 86400, "1wk": 604800,
}


def _bars_wanted(interval: str, period: str, cap: int) -> int:
    secs = _INTERVAL_SECONDS.get(interval, 300)
    days = _PERIOD_DAYS.get(period, 180)
    return max(2, min(cap, int(days * 86400 / secs)))


def _aggregate(candles: list[Candle], factor: int) -> list[Candle]:
    """Fold N candles into one, where a venue lacks the requested interval.

    Aggregating is honest. Asking for 4h and silently receiving 1h is not,
    and that is what the previous CoinGecko path did.
    """
    if factor <= 1:
        return candles
    out: list[Candle] = []
    for i in range(0, len(candles) - factor + 1, factor):
        chunk = candles[i:i + factor]
        out.append({
            "time": chunk[0]["time"],
            "open": chunk[0]["open"],
            "high": max(c["high"] for c in chunk),
            "low": min(c["low"] for c in chunk),
            "close": chunk[-1]["close"],
            "volume": sum(c["volume"] for c in chunk),
        })
    return out


# --------------------------------------------------------------------------
# Crypto: served from an exchange, not an aggregator
# --------------------------------------------------------------------------

_BINANCE_INTERVAL = {
    "1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
    "1h": "1h", "4h": "4h", "1d": "1d", "1wk": "1w",
}


def to_binance_symbol(ticker: str) -> Optional[str]:
    """BTC-USD -> BTCUSDT.

    Binance quotes in USDT, not USD. That is a small but real difference, and
    it goes in the provenance rather than being hidden: a chart that says USD
    while showing a USDT tape is making a quiet false statement all day.
    """
    t = (ticker or "").upper().strip()
    if t.endswith("-USDT"):
        return t.replace("-USDT", "USDT")
    if t.endswith("-USD"):
        return t[:-4] + "USDT"
    if t.endswith("USDT"):
        return t
    return None


async def fetch_binance(client: httpx.AsyncClient, ticker: str, interval: str,
                        period: str) -> tuple[list[Candle], Provenance]:
    sym = to_binance_symbol(ticker)
    if not sym:
        raise ValueError(f"not a Binance pair: {ticker}")
    iv = _BINANCE_INTERVAL.get(interval)
    if not iv:
        raise ValueError(f"interval {interval} unsupported on Binance")

    r = await client.get(
        "https://api.binance.com/api/v3/klines",
        params={"symbol": sym, "interval": iv,
                "limit": _bars_wanted(interval, period, 1000)},
    )
    r.raise_for_status()
    rows = r.json()

    candles = [{
        "time": int(k[0] // 1000),
        "open": float(k[1]), "high": float(k[2]),
        "low": float(k[3]), "close": float(k[4]),
        "volume": float(k[5]),
    } for k in rows]

    return candles, Provenance(
        source="binance",
        venue="Binance Spot",
        is_realtime=True,
        has_volume=True,
        volume_kind=VOL_TRADED,
        license="public_api",
        quote_currency="USDT",
        requested_symbol=ticker,
        resolved_symbol=sym,
        note="Exchange tape. Volume is coins actually traded on Binance. "
             "Quoted in USDT, not USD.",
    )


_COINBASE_GRANULARITY = {
    "1m": (60, 1), "5m": (300, 1), "15m": (900, 1), "30m": (900, 2),
    "1h": (3600, 1), "4h": (3600, 4), "1d": (86400, 1), "1wk": (86400, 7),
}


def to_coinbase_symbol(ticker: str) -> Optional[str]:
    t = (ticker or "").upper().strip()
    if t.endswith("-USD"):
        return t
    if t.endswith("-USDT"):
        return t.replace("-USDT", "-USD")
    return None


async def fetch_coinbase(client: httpx.AsyncClient, ticker: str, interval: str,
                         period: str) -> tuple[list[Candle], Provenance]:
    """Fallback venue for crypto.

    Binance answers 451 from some hosting regions - the US in particular -
    which is a deployment problem, not a bad symbol. A second exchange behind
    it means a US-hosted backend still gets venue data, quoted in real USD.
    """
    sym = to_coinbase_symbol(ticker)
    if not sym:
        raise ValueError(f"not a Coinbase product: {ticker}")
    gran, factor = _COINBASE_GRANULARITY.get(interval, (300, 1))

    r = await client.get(
        f"https://api.exchange.coinbase.com/products/{sym}/candles",
        params={"granularity": gran},
    )
    r.raise_for_status()
    rows = r.json()  # [time, low, high, open, close, volume], newest first

    candles = sorted(({
        "time": int(k[0]),
        "open": float(k[3]), "high": float(k[2]),
        "low": float(k[1]), "close": float(k[4]),
        "volume": float(k[5]),
    } for k in rows), key=lambda c: c["time"])
    candles = _aggregate(candles, factor)

    return candles, Provenance(
        source="coinbase",
        venue="Coinbase Exchange",
        is_realtime=True,
        has_volume=True,
        volume_kind=VOL_TRADED,
        license="public_api",
        quote_currency="USD",
        requested_symbol=ticker,
        resolved_symbol=sym,
        note="Exchange tape. Volume is coins actually traded on Coinbase.",
    )


# --------------------------------------------------------------------------
# Twelve Data: real-time FX and equities on a free key. Dormant without one.
# --------------------------------------------------------------------------

_TD_INTERVAL = {
    "1m": "1min", "5m": "5min", "15m": "15min", "30m": "30min",
    "1h": "1h", "4h": "4h", "1d": "1day", "1wk": "1week",
}


def twelvedata_key() -> Optional[str]:
    return (os.getenv("TWELVEDATA_API_KEY") or "").strip() or None


def to_twelvedata_symbol(ticker: str, asset_class: str) -> Optional[str]:
    t = (ticker or "").upper().strip()
    if asset_class == "fx":
        base = t.replace("=X", "")
        return f"{base[:3]}/{base[3:]}" if len(base) == 6 else None
    if asset_class == "stocks":
        return t
    return None


async def fetch_twelvedata(client: httpx.AsyncClient, ticker: str, interval: str,
                           period: str, asset_class: str) -> tuple[list[Candle], Provenance]:
    key = twelvedata_key()
    if not key:
        raise RuntimeError("TWELVEDATA_API_KEY not set")
    sym = to_twelvedata_symbol(ticker, asset_class)
    if not sym:
        raise ValueError(f"no Twelve Data symbol for {ticker}")
    iv = _TD_INTERVAL.get(interval)
    if not iv:
        raise ValueError(f"interval {interval} unsupported")

    r = await client.get(
        "https://api.twelvedata.com/time_series",
        params={"symbol": sym, "interval": iv, "apikey": key,
                "outputsize": _bars_wanted(interval, period, 5000)},
    )
    r.raise_for_status()
    d = r.json()
    if d.get("status") == "error":
        raise RuntimeError(f"twelvedata: {d.get('message')}")

    import datetime as _dt
    candles = []
    for v in reversed(d.get("values") or []):
        ts = v.get("datetime", "")
        try:
            fmt = "%Y-%m-%d %H:%M:%S" if " " in ts else "%Y-%m-%d"
            epoch = int(_dt.datetime.strptime(ts, fmt)
                        .replace(tzinfo=_dt.timezone.utc).timestamp())
        except Exception:
            continue
        candles.append({
            "time": epoch,
            "open": float(v["open"]), "high": float(v["high"]),
            "low": float(v["low"]), "close": float(v["close"]),
            "volume": float(v.get("volume") or 0),
        })

    has_vol = any(c["volume"] > 0 for c in candles)
    return candles, Provenance(
        source="twelvedata",
        venue="Twelve Data",
        is_realtime=True,
        has_volume=has_vol,
        # Twelve Data's FX "volume" counts price updates from its contributors,
        # not size traded. Calling that traded volume would be a worse lie than
        # reporting none, so it gets its own kind and the chart can label it.
        volume_kind=(VOL_TICK if (has_vol and asset_class == "fx")
                     else VOL_TRADED if has_vol else VOL_NONE),
        requested_symbol=ticker,
        resolved_symbol=sym,
        license="licensed_free_tier",
        note="Twelve Data free tier: 800 requests/day, 8 per minute.",
    )


# --------------------------------------------------------------------------
# Yahoo: the delayed consumer feed, kept and labelled as such
# --------------------------------------------------------------------------

_YF_INTERVAL = {"1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
                "1h": "60m", "4h": "60m", "1d": "1d", "1wk": "1wk"}
_YF_RANGE = {"1d": "1d", "5d": "5d", "1mo": "1mo", "3mo": "3mo",
             "6mo": "6mo", "1y": "1y", "2y": "2y"}


async def fetch_yahoo(client: httpx.AsyncClient, symbol: str, interval: str,
                      period: str, requested: str) -> tuple[list[Candle], Provenance]:
    iv = _YF_INTERVAL.get(interval, "1d")
    rng = _YF_RANGE.get(period, "6mo")

    r = await client.get(
        f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
        params={"interval": iv, "range": rng},
        headers={"User-Agent": "Mozilla/5.0"},
    )
    r.raise_for_status()
    res = r.json()["chart"]["result"][0]
    stamps = res.get("timestamp") or []
    q = res["indicators"]["quote"][0]
    # Yahoo returns "volume": null for whole symbols. `.get("volume", default)`
    # does not save you here - the key EXISTS with value None, so the default
    # never fires and None[i] raises.
    vols = q.get("volume") or [None] * len(stamps)

    candles = []
    for i, ts in enumerate(stamps):
        o, h, l, c = q["open"][i], q["high"][i], q["low"][i], q["close"][i]
        if o is None or c is None or h is None or l is None:
            continue
        candles.append({
            "time": int(ts),
            "open": round(float(o), 6), "high": round(float(h), 6),
            "low": round(float(l), 6), "close": round(float(c), 6),
            "volume": float(vols[i]) if vols[i] else 0.0,
        })
    candles = _aggregate(candles, 4 if interval == "4h" else 1)

    has_vol = any(c["volume"] > 0 for c in candles)
    meta = res.get("meta", {})
    return candles, Provenance(
        source="yahoo",
        venue=str(meta.get("exchangeName") or "Yahoo composite"),
        is_realtime=False,
        has_volume=has_vol,
        volume_kind=VOL_TRADED if has_vol else VOL_NONE,
        license="consumer_endpoint",
        quote_currency=meta.get("currency"),
        requested_symbol=requested,
        resolved_symbol=symbol,
        note=("Delayed consumer feed, not a market data licence. "
              + ("This symbol publishes no volume: spot FX has no "
                 "consolidated tape, so there is none to publish."
                 if not has_vol else
                 "Volume is real exchange volume; the bars arrive late.")),
    )


# --------------------------------------------------------------------------
# Router
# --------------------------------------------------------------------------

async def fetch(ticker: str, interval: str, period: str, asset_class: str,
                yahoo_symbol: str) -> tuple[list[Candle], Provenance]:
    """Best available source for this instrument, with provenance attached.

    Ordered by how close the source sits to where the trades happen: an
    exchange beats a licensed aggregator beats a scraped consumer endpoint.
    Whichever one answers, the caller is told which it was.
    """
    attempts: list[str] = []
    if asset_class == "crypto":
        attempts = ["binance", "coinbase"]
    elif asset_class in ("fx", "stocks") and twelvedata_key():
        attempts = ["twelvedata"]

    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        for name in attempts:
            try:
                if name == "binance":
                    candles, prov = await fetch_binance(client, ticker, interval, period)
                elif name == "coinbase":
                    candles, prov = await fetch_coinbase(client, ticker, interval, period)
                else:
                    candles, prov = await fetch_twelvedata(
                        client, ticker, interval, period, asset_class)
                if candles:
                    return candles, _observe(prov, candles)
                log.warning("provider %s returned no candles for %s", name, ticker)
            except httpx.HTTPStatusError as exc:
                # 451 from Binance means the HOST's region is blocked, not that
                # the symbol is wrong. Worth separating in the log so a
                # deployment problem is not misread as a data problem.
                code = exc.response.status_code
                log.warning("provider %s HTTP %s for %s%s", name, code, ticker,
                            "  (region-blocked: check where this backend runs)"
                            if code == 451 else "")
            except Exception as exc:
                log.warning("provider %s failed for %s: %s: %s",
                            name, ticker, type(exc).__name__, exc)

        candles, prov = await fetch_yahoo(client, yahoo_symbol, interval,
                                          period, ticker)
        return candles, _observe(prov, candles)


def _observe(prov: Provenance, candles: list[Candle]) -> Provenance:
    """Attach what was measured about this response, not what was assumed."""
    age = int(time.time() - candles[-1]["time"]) if candles else None
    return replace(prov, last_bar_age_seconds=age, bar_count=len(candles))
