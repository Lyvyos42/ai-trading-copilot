"""AGENT INTEGRITY SUITE — no agent may invent data.

Run:  python -m scripts.test_agent_integrity      (from backend/)

This exists because "the agents no longer fabricate" is a claim that decays.
Every mock path removed on 2026-09-05 was, at the time it was written, a
reasonable-looking convenience; each became a production data source because
nothing checked. These tests are the check.

Two kinds of assertion:

  STRUCTURAL   No `random` in executable agent code. This is an AST walk, not
               a grep, so a mention inside a docstring or comment (there are
               several, quoting the removed code) does not trip it, and an
               `import random` that is actually used cannot hide from it.

  BEHAVIOURAL  Each agent, given nothing, must abstain rather than answer.
               And given something real, must still answer - a suite that only
               tested abstention would pass on an agent that had been broken
               into silence.

No API key and no network are required: the LLM router is stubbed to return
None, which is exactly what production does when ANTHROPIC_API_KEY is unset.
"""
import ast
import asyncio
import glob
import io
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

for _name in ("anthropic", "openai", "structlog"):
    sys.modules.setdefault(_name, types.ModuleType(_name))


class _Log:
    def __getattr__(self, _k):
        return lambda *a, **kw: None


sys.modules["structlog"].get_logger = lambda *a, **kw: _Log()

_router = types.ModuleType("app.providers.router")


class _NoLLM:
    async def complete(self, **_kw):
        return None            # no API key — the production reality


_router.model_router = _NoLLM()
sys.modules["app.providers.router"] = _router

from app.agents.fundamental import FundamentalAnalyst      # noqa: E402
from app.agents.technical import TechnicalAnalyst          # noqa: E402
from app.agents.quant import QuantAnalyst                  # noqa: E402
from app.agents.macro import MacroAnalyst                  # noqa: E402
from app.agents.sentiment import SentimentAnalyst          # noqa: E402
from app.agents.trader import TraderAgent                  # noqa: E402

FAILURES = []


def check(name, ok, detail=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {name}{'  — ' + detail if detail else ''}")
    if not ok:
        FAILURES.append(name)


def test_no_rng_in_agents():
    """AST walk: no executable reference to random/rng anywhere in the agents."""
    print("\nSTRUCTURAL — no randomness in agent code")
    root = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "app", "agents")
    offenders = []
    for path in sorted(glob.glob(os.path.join(root, "**", "*.py"), recursive=True)):
        tree = ast.parse(io.open(path, encoding="utf-8").read())
        for node in ast.walk(tree):
            if (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
                    and node.value.id in ("rng", "random")):
                offenders.append(f"{os.path.basename(path)}:{node.lineno}")
    check("no rng/random call in any agent", not offenders, ", ".join(offenders))


async def test_abstentions():
    """Given no data, every agent must decline rather than answer."""
    print("\nBEHAVIOURAL — abstention when the data source is empty")

    f = await FundamentalAnalyst().analyze(
        {"ticker": "EURJPY=X",
         "market_data": {"close": 181.48, "pe_ratio": None, "eps_growth": None}})
    check("fundamental abstains on an FX pair",
          f.get("abstained") is True and f["confidence"] == 0.0,
          f"{f['direction']} @ {f['confidence']}")

    t = await TechnicalAnalyst().analyze({"ticker": "XAUUSD", "market_data": {}})
    check("technical abstains with no bars",
          t.get("abstained") is True and t.get("support") is None,
          f"support={t.get('support')}")

    q = await QuantAnalyst().analyze(
        {"ticker": "US500", "technical_analysis": {"direction": "LONG", "confidence": 60}})
    check("quant reports no backtest rather than inventing one",
          q.get("backtest_win_rate") is None and q.get("statistical_edge") is None,
          f"wr={q.get('backtest_win_rate')} edge={q.get('statistical_edge')}")

    m = await MacroAnalyst().analyze(
        {"ticker": "US500", "news_context": {"has_news": False}, "fred_data": {}})
    check("macro abstains with no news and no FRED",
          m.get("abstained") is True and m.get("macro_regime") is None,
          f"{m['direction']} @ {m['confidence']}")

    s = await SentimentAnalyst().analyze(
        {"ticker": "US500", "news_context": {"has_news": False}, "market_data": {"close": 6700}})
    check("sentiment abstains with no articles",
          s.get("abstained") is True and s.get("news_volume") in (0, None),
          f"{s['direction']} @ {s['confidence']}")


async def test_real_paths_still_work():
    """A suite that only tested silence would pass on an agent broken into silence."""
    print("\nBEHAVIOURAL — real data still produces a real read")

    f = await FundamentalAnalyst().analyze(
        {"ticker": "AAPL",
         "market_data": {"close": 230.0, "pe_ratio": 28.0, "eps_growth": 9.0}})
    check("fundamental analyses a real equity",
          not f.get("abstained") and f["confidence"] > 0 and "28.0x" in f["reasoning"],
          f"{f['direction']} @ {f['confidence']}")


async def test_trader_gates():
    """Silence must not become a BUY, and synthetic bars must not become a signal."""
    print("\nBEHAVIOURAL — the trader can say no")
    abstain = {"direction": "NEUTRAL", "confidence": 0.0, "abstained": True}

    def state(md, **kw):
        s = {"ticker": "EURJPY=X", "market_data": md,
             "technical_analysis": {"direction": "SHORT", "confidence": 62, "atr": 0.9,
                                    "support": 180.0, "resistance": 183.0},
             "fundamental_analysis": abstain, "sentiment_analysis": abstain,
             "macro_analysis": abstain, "order_flow_analysis": abstain,
             "regime_analysis": abstain, "correlation_analysis": abstain,
             "risk_assessment": {}, "quant_validation": {}}
        s.update(kw)
        return s

    live = {"close": 181.48, "atr": 0.9, "data_source": "tradingview"}

    r = await TraderAgent().analyze(state(live))
    check("one directional vote produces NO_SIGNAL, not a coin flip",
          r.get("status") == "NO_SIGNAL" and r.get("research_target") is None,
          f"status={r.get('status')} direction={r.get('direction')}")

    r2 = await TraderAgent().analyze(
        state(live, order_flow_analysis={"direction": "SHORT", "confidence": 55}))
    check("two directional votes do produce a signal",
          r2.get("status") != "NO_SIGNAL" and r2.get("research_target") is not None,
          f"{r2.get('direction')} target={r2.get('research_target')}")

    r3 = await TraderAgent().analyze(
        state({"close": 181.48, "atr": 0.9, "data_source": "mock"},
              order_flow_analysis={"direction": "SHORT", "confidence": 55}))
    check("synthetic bars never become a signal",
          r3.get("status") == "NO_SIGNAL" and r3.get("entry_price") is None,
          f"status={r3.get('status')} entry={r3.get('entry_price')}")

    check("no signal ever quotes a position size it did not derive",
          r.get("position_size_pct") is None and r3.get("position_size_pct") is None)


async def test_macro_is_not_structurally_bearish():
    """The 50-consecutive-shorts defect: risk-off must not be easier than risk-on.

    The original test fired RISK_OFF on ANY of three conditions while RISK_ON
    needed two at once, so it returned SHORT for essentially every symbol. The
    guard is that a mirrored macro picture must produce a mirrored answer.
    """
    print("\nBEHAVIOURAL — macro regime is symmetric")

    bearish = {"yield_curve_spread": {"value": -0.4, "trend": "INVERTED"},
               "cpi_yoy": {"value": 4.0, "trend": "RISING"},
               "fed_funds": {"value": 5.5, "trend": "RISING"},
               "gdp_growth": {"value": 0.3, "trend": "FALLING"},
               "unemployment": {"value": 4.6, "trend": "RISING"}}
    bullish = {"yield_curve_spread": {"value": 1.4, "trend": "STEEPENING"},
               "cpi_yoy": {"value": 1.9, "trend": "FALLING"},
               "fed_funds": {"value": 2.0, "trend": "FALLING"},
               "gdp_growth": {"value": 3.4, "trend": "RISING"},
               "unemployment": {"value": 3.6, "trend": "FALLING"}}

    ctx = {"has_news": True, "macro_headlines": ["Fed holds rates steady"],
           "geo_headlines": [], "crisis_headlines": [], "avg_sentiment": 0.0,
           "article_count": 1}

    a = await MacroAnalyst().analyze(
        {"ticker": "US500", "news_context": ctx, "fred_data": bearish})
    b = await MacroAnalyst().analyze(
        {"ticker": "US500", "news_context": ctx, "fred_data": bullish})

    check("a bearish macro picture reads RISK_OFF",
          a.get("macro_regime") == "RISK_OFF", f"{a.get('macro_regime')} / {a['direction']}")
    check("a MIRRORED bullish picture reads RISK_ON",
          b.get("macro_regime") == "RISK_ON", f"{b.get('macro_regime')} / {b['direction']}")
    check("mirrored pictures carry comparable confidence",
          abs(a["confidence"] - b["confidence"]) <= 5.0,
          f"risk_off={a['confidence']} risk_on={b['confidence']}")
    check("macro declares itself market-wide, not symbol-specific",
          a.get("symbol_specific") is False)

    # The mirrored test above is necessary but not sufficient: both sides hit
    # the confidence cap of 70, which hides a one-sided ledger. This isolates
    # ONE indicator at a time against an otherwise neutral backdrop, which is
    # how the missing `falling_unemployment` counterpart was found - RISING
    # returned RISK_OFF/SHORT at 55 while FALLING returned TRANSITIONAL at 50.
    neutral = {"yield_curve_spread": {"value": 0.3, "trend": "FLAT"},
               "cpi_yoy": {"value": 2.5, "trend": "STABLE"},
               "fed_funds": {"value": 3.0, "trend": "STABLE"},
               "gdp_growth": {"value": 1.5, "trend": "STABLE"},
               "unemployment": {"value": 4.0, "trend": "STABLE"}}

    async def one(field, trend):
        fd = {k: dict(v) for k, v in neutral.items()}
        fd[field]["trend"] = trend
        r = await MacroAnalyst().analyze(
            {"ticker": "US500", "news_context": ctx, "fred_data": fd})
        return r.get("macro_regime")

    for field, bear, bull in (("unemployment", "RISING", "FALLING"),
                              ("cpi_yoy", "RISING", "FALLING"),
                              ("gdp_growth", "FALLING", "RISING")):
        off = await one(field, bear)
        on = await one(field, bull)
        check(f"{field}: each direction carries the same weight",
              (off == "RISK_OFF" and on == "RISK_ON") or (off == on),
              f"{bear}->{off}  {bull}->{on}")


async def main():
    test_no_rng_in_agents()
    await test_abstentions()
    await test_real_paths_still_work()
    await test_trader_gates()
    await test_macro_is_not_structurally_bearish()
    print("\n" + ("ALL CHECKS PASSED" if not FAILURES
                  else f"{len(FAILURES)} FAILED: {', '.join(FAILURES)}"))
    return 1 if FAILURES else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
