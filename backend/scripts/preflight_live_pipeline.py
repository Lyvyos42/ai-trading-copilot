"""PRE-FLIGHT — will the cleaned pipeline actually produce signals?

Run:  python -m scripts.preflight_live_pipeline           (from backend/)
      python -m scripts.preflight_live_pipeline EURUSD=X AAPL

Removing fabrication carries a specific risk that is easy to miss while
celebrating the removal: an engine that never lies but also never speaks is
not a product. Agents now abstain when their data source is empty, the trader
refuses to publish below MIN_DIRECTIONAL_VOTES, and several agents were
deliberately taken out of the directional vote entirely - regime because a
volatility state is not a direction, correlation because it cannot compute a
coefficient from one price series.

Stack those together and the ensemble is materially smaller than "9 agents"
suggests. This script measures exactly how much smaller, against REAL bars,
so the answer is a number rather than a hope.

It deliberately does NOT go through langgraph. It calls the agents and the
trader directly, which is the decision logic that matters, and keeps the
script runnable without the full server dependency set.

Markets being closed does not affect it: the market-hours guard lives in the
scanner and the generate route, not in the agents, so the analysis still runs
on the last real bars.
"""
import asyncio
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

for _n in ("anthropic", "openai"):
    sys.modules.setdefault(_n, types.ModuleType(_n))
_router = types.ModuleType("app.providers.router")


class _NoLLM:
    async def complete(self, **_kw):
        return None            # no API key — the production reality


_router.model_router = _NoLLM()
sys.modules["app.providers.router"] = _router

# LOCAL DEVELOPMENT ONLY - never a production behaviour.
#
# This machine has TLS interception (a security product re-signing HTTPS), so
# certifi cannot verify Yahoo's chain and every price fetch fails locally while
# working fine from Render. PREFLIGHT_INSECURE_TLS=1 skips verification for
# THIS SCRIPT so the pipeline can be exercised against real bars.
#
# Do NOT port this into app code. Disabling certificate verification server-side
# to work around a developer machine's proxy is a real security regression: it
# makes the server accept any certificate for any host, on a service that
# carries user tokens.
if os.getenv("PREFLIGHT_INSECURE_TLS", "").lower() in ("1", "true", "yes"):
    import ssl
    ssl._create_default_https_context = ssl._create_unverified_context
    os.environ.setdefault("CURL_CA_BUNDLE", "")
    os.environ.setdefault("PYTHONHTTPSVERIFY", "0")
    print("[preflight] TLS verification disabled for this run (local only).")

from app.data.market_data import fetch_market_data, resolve_asset_class   # noqa: E402
from app.agents.fundamental import FundamentalAnalyst                     # noqa: E402
from app.agents.technical import TechnicalAnalyst                         # noqa: E402
from app.agents.sentiment import SentimentAnalyst                         # noqa: E402
from app.agents.macro import MacroAnalyst                                 # noqa: E402
from app.agents.order_flow import OrderFlowAnalyst                        # noqa: E402
from app.agents.regime_change import RegimeChangeAnalyst                  # noqa: E402
from app.agents.correlation import CorrelationAnalyst                     # noqa: E402
from app.agents.quant import QuantAnalyst                                 # noqa: E402
from app.agents.risk_manager import RiskManager                           # noqa: E402
from app.agents.trader import TraderAgent                                 # noqa: E402

DEFAULT_SYMBOLS = ["EURUSD=X", "XAUUSD=X", "AAPL", "BTC-USD"]

STAGE = [
    ("fundamental_analysis",   FundamentalAnalyst),
    ("technical_analysis",     TechnicalAnalyst),
    ("sentiment_analysis",     SentimentAnalyst),
    ("macro_analysis",         MacroAnalyst),
    ("order_flow_analysis",    OrderFlowAnalyst),
    ("regime_change_analysis", RegimeChangeAnalyst),
    ("correlation_analysis",   CorrelationAnalyst),
]


async def _direct_bars(ticker: str, asset_class: str) -> dict | None:
    """Fetch real bars straight from Yahoo, bypassing local TLS interception.

    Only used when PREFLIGHT_INSECURE_TLS is set and the app's own fetch has
    already failed. It exists so the decision path can be exercised against
    REAL prices on a machine whose certificate chain is being rewritten by a
    security product - otherwise every local run tests only the dead-feed
    branch, which proves nothing about whether the engine can still speak.
    """
    import httpx
    from app.data.market_data import resolve_ticker, _compute_atr, _price_decimals
    sym = resolve_ticker(ticker)
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}"
           f"?range=1y&interval=1d")
    try:
        async with httpx.AsyncClient(verify=False, timeout=25) as c:
            r = await c.get(url, headers={"User-Agent": "Mozilla/5.0"})
        res = (r.json().get("chart") or {}).get("result")
        if not res:
            return None
        q = res[0]["indicators"]["quote"][0]
        closes = [float(x) for x in q["close"] if x is not None]
        highs = [float(x) for x in q["high"] if x is not None]
        lows = [float(x) for x in q["low"] if x is not None]
        vols = [float(x or 0) for x in q.get("volume", [])]
        if len(closes) < 60:
            return None
        dec = _price_decimals(closes[-1])
        atr = _compute_atr(highs, lows, closes)
        prev = closes[-2] if len(closes) > 1 else closes[-1]
        return {
            "ticker": ticker, "asset_class": asset_class,
            "data_source": "yahoo-direct(preflight)",
            "closes": closes, "highs": highs, "lows": lows, "volumes": vols,
            "close": round(closes[-1], dec), "previous_close": round(prev, dec),
            "price_change_pct": round((closes[-1] - prev) / prev * 100, 2) if prev else 0.0,
            "atr": atr, "volume": vols[-1] if vols else 0,
            "avg_volume": (sum(vols[-20:]) / 20) if len(vols) >= 20 else (vols[-1] if vols else 0),
            "pe_ratio": None, "eps_growth": None, "revenue_growth": None,
        }
    except Exception:
        return None


async def run_one(ticker: str, profile: str) -> dict:
    asset_class = resolve_asset_class(ticker)
    md = await fetch_market_data(ticker, asset_class)
    if (not md or md.get("data_source") in (None, "unavailable")) and             os.getenv("PREFLIGHT_INSECURE_TLS", "").lower() in ("1", "true", "yes"):
        direct = await _direct_bars(ticker, asset_class)
        if direct:
            # Attach TradingView's indicator set, exactly as fetch_market_data
            # does in production - otherwise this harness silently tests the
            # Yahoo-only path and reports it as if it were the live one.
            from app.data.market_data import fetch_tv_indicators
            tv = await fetch_tv_indicators(ticker, asset_class)
            if tv:
                direct["tv"] = tv
                direct["tv_symbol"] = tv.get("tv_symbol")
                direct["data_source"] = "tradingview+yahoo-direct(preflight)"
                if tv.get("ATR"):
                    direct["atr"] = float(tv["ATR"])
                if tv.get("close"):
                    direct["close"] = float(tv["close"])
            md = direct
    state = {
        "ticker": ticker,
        "asset_class": asset_class,
        "market_data": md or {},
        "news_context": {"has_news": False},
        "fred_data": {},
        "strategy_profile": profile,
        "timeframe": "1D",
        "portfolio_stats": {},
    }

    for key, cls in STAGE:
        try:
            state[key] = await cls().analyze(state)
        except Exception as exc:
            state[key] = {"direction": "NEUTRAL", "confidence": 0.0, "abstained": True,
                          "reasoning": f"agent raised {type(exc).__name__}: {exc}"}

    state["quant_validation"] = await QuantAnalyst().analyze(state)
    state["risk_assessment"] = await RiskManager().analyze(state)
    final = await TraderAgent().analyze(state)
    return {"state": state, "final": final, "market_data": md or {}}


def render(ticker: str, res: dict) -> bool:
    md, state, final = res["market_data"], res["state"], res["final"]
    src = md.get("data_source", "none")
    close = md.get("close")
    bars = len(md.get("closes") or [])

    print(f"\n{'=' * 74}")
    print(f"{ticker}   feed={src}   bars={bars}   close={close}")
    print("-" * 74)

    voted, abstained = [], []
    for key, _ in STAGE:
        a = state.get(key) or {}
        name = key.replace("_analysis", "").replace("_change", "")
        if a.get("abstained"):
            abstained.append(name)
        elif a.get("direction") in ("LONG", "SHORT"):
            voted.append(f"{name}:{a['direction']}@{a.get('confidence', 0):.0f}")
        else:
            abstained.append(f"{name}(neutral)")

    print(f"  DIRECTIONAL VOTES ({len(voted)}): {', '.join(voted) or 'none'}")
    print(f"  NO VOTE          ({len(abstained)}): {', '.join(abstained)}")

    status = final.get("status")
    if status == "NO_SIGNAL":
        print("  RESULT: NO SIGNAL")
        for r in final.get("status_reasons", []):
            print(f"     - {r}")
        return False

    print(f"  RESULT: {final.get('direction')} "
          f"@ {final.get('probability_score')}% probability, "
          f"confidence {final.get('confidence_score')}")
    print(f"     entry={final.get('entry_price')}  target={final.get('research_target')}  "
          f"invalidation={final.get('invalidation_level')}  R:R={final.get('risk_reward_ratio')}")
    print(f"     window={final.get('analytical_window')}  size={final.get('position_size_pct')}")
    return True


async def main() -> int:
    symbols = sys.argv[1:] or DEFAULT_SYMBOLS
    profile = os.getenv("PREFLIGHT_PROFILE", "balanced")
    print(f"Pre-flight on {len(symbols)} symbols, profile={profile}, live feeds.")

    produced = 0
    for sym in symbols:
        try:
            res = await run_one(sym, profile)
        except Exception as exc:
            print(f"\n{sym}: FAILED — {type(exc).__name__}: {exc}")
            continue
        if render(sym, res):
            produced += 1

    print(f"\n{'=' * 74}")
    print(f"{produced} of {len(symbols)} symbols produced a signal.")
    if produced == 0:
        print("\nZERO SIGNALS. An engine that never speaks is not a product - this is\n"
              "as much of a failure as one that fabricates. Check which agents are\n"
              "abstaining above and whether their data source is genuinely dead.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
