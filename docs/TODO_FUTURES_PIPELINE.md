# TODO — independent futures pipeline and page

Requested 2026-09-05. Not started; this records the shape of the work and the
decisions that need making, so it can be picked up cleanly.

## What was asked

An independent switch/page with a **new pipeline for futures only** — separate
from the current multi-asset pipeline, not a filter over it.

## Why it warrants its own pipeline rather than an asset-class branch

The current pipeline assumes a spot instrument with a continuous price series
and no expiry. Futures break four of those assumptions, and each one is a
place where the existing agents would be quietly wrong rather than loudly
broken — which is the failure mode this codebase has spent the most time
undoing:

1. **Contracts expire.** A signal with a 5-14 DAY analytical window on a
   contract expiring in three days is not a signal. Nothing in the pipeline
   knows an expiry date exists.

2. **Continuous series are synthetic.** `ES=F` is a stitched series across
   contract rolls. The roll gap is a real price discontinuity that the
   technical agent will read as a gap or a momentum event. ATR, z-score and
   EMA crossovers all inherit that artefact. Either the roll must be adjusted
   for, or the roll dates must be excluded — and the choice must be stated.

3. **Term structure is the signal.** Contango and backwardation carry more
   information about a futures market than most of what the current seven
   analysts measure. There is no agent for it, and it has no spot analogue.

4. **Volume and open interest are real here.** MT5-style tick volume is a
   proxy; futures report genuine exchange volume AND open interest. The order
   flow agent currently derives everything from `tick_volume` and VWAP
   deviation. On futures it could use the real thing — and open interest
   changes alongside price is a classic, measurable signal that does not exist
   for spot FX.

A shared pipeline with `if asset_class == "futures"` branches would smear
these differences across seven agents. A separate pipeline keeps the
assumptions of each honest.

## Solving the open-interest and curve problem — tested 2026-09-05

The blocker was: Yahoo's free `=F` series gives no open interest and no term
structure. Each candidate below was actually called, not assumed.

| source | result | verdict |
|---|---|---|
| Yahoo individual contract months (`ESZ25.CME`, `CLF26.NYM`, `GCZ25.CMX`) | **no data** for every format tried; only the continuous `=F` resolves | no curve from Yahoo, confirmed |
| CME Group settlements API | **HTTP 403** — "Use of scripts, software, spiders, robots... is strictly prohibited by CME Group's Data Terms of Use" | OFF THE TABLE. A legal prohibition, not a rate limit |
| CFTC Commitments of Traders | **HTTP 200, 1.7 MB**, 9,502 rows, 191 columns including `Open_Interest_All` and `Change_in_Open_Interest_All`. Verified live: GOLD OI 415,196 and WTI CRUDE OI 767,357 as of report date 2026-09-01 | **USE THIS** — official, free, explicitly published, no key |

### Recommendation

**Open interest and positioning: CFTC COT.** Free, official, and legally
unambiguous — it is published data, not scraped. Two files matter:
`fut_disagg_txt_<year>.zip` for commodities (producer / swap / managed money)
and `fut_fin_txt_<year>.zip` for financials (dealer / asset manager /
leveraged funds). Weekly: Tuesday positions released Friday 15:30 ET.

That cadence is the catch and it must shape the design. **A weekly figure
cannot drive an intraday signal.** It is a positioning-extreme and
crowding input — "managed money net long is at a two-year high" is a real,
measurable, tradeable observation — not a scalping trigger. An agent built on
it must state its own staleness, and abstain in the window before a release
rather than pretend Tuesday's data describes Friday.

**Term structure: still unsolved for free.** Ranked options:

1. **Interactive Brokers API** — free with a funded account, gives the full
   chain per contract with real OI and live quotes, and is entirely within
   terms. Needs a running gateway process, which is real operational weight on
   Render.
2. **Databento** — paid, usage-based, clean licensed CME data, no scraping.
   The straightforward answer if the futures page is meant to be commercial.
3. **Barchart** free tier — limited symbols per day; workable for a handful of
   contracts, not a universe.
4. **tvDatafeed continuous contracts** (`ES1!`, `ES2!`, `ES3!`) would give the
   curve directly — but it is an unofficial scraper of a service whose terms
   forbid it, so it carries the same objection as CME. See the data-source
   note below.

**If none is adopted:** the futures pipeline should ship WITHOUT a term
structure agent rather than inferring a curve from the front month. An
inferred curve is exactly the class of fabrication this codebase spent two
days removing.

## A finding that affects the whole app, not just futures

`tvDatafeed` is **not in `backend/requirements.txt`**, while `yfinance==0.2.48`
is. `_get_tv_client()` swallowed the resulting ImportError with a bare
`except Exception: pass`, so in production the client was always None,
`_fetch_tvdatafeed` always returned None, and **every request fell through to
yfinance**. TradingView was first in the fetch chain and never once ran.

So every bar every agent has ever analysed came from Yahoo — while the price
shown next to it came from TradingView's scanner API, which does work because
it is a plain HTTP POST needing no package. Two different sources for the
price and the analysis of it.

That is now logged loudly on first failure, and `scripts/decision_report.py`
prints which feed actually served each run. Before adding tvDatafeed as a
dependency, note that it is an unofficial websocket scraper, TradingView's
terms prohibit it, and it is as likely to be blocked from a datacentre IP as
yfinance is.

## Decisions needed before building

- **Data source.** Yahoo's `=F` continuous series is free but stitched and
  gives no open interest or term structure. Real futures data (per-contract
  OHLCV, OI, the full curve) needs a paid feed. **This choice determines
  whether points 1, 3 and 4 above are buildable at all** — without per-contract
  data the pipeline is a re-skin of the spot one, and should not ship claiming
  otherwise.
- **Instrument universe.** Index (ES, NQ, YM, RTY), energy (CL, NG), metals
  (GC, SI), rates (ZN, ZB), ags — each has different session hours and
  different drivers.
- **Session handling.** Futures trade nearly 24h with a daily settlement
  break. `market_hours.py` models equity and FX sessions; futures need their
  own calendar, including holiday schedules per exchange.
- **Contract selection.** Front month, or roll on volume crossover? Stated
  explicitly, because it changes every backtest.

## Non-negotiables carried over from this codebase

Everything learned the hard way over 2026-09-04/05 applies here from line one:

- **No agent may fabricate.** No `random`, no `hashlib`-seeded decisions, no
  plausible defaults for missing data. `BaseAgent.abstain()` is the only
  honest response to an absent source. `scripts/test_agent_integrity.py`
  enforces this at the source level and must be extended to cover the new
  package.
- **No `.get(key, default)` that is then indexed or compared.** Four separate
  production failures came from that one idiom. Use `nz()`.
- **Every run must be recorded** in `signal_decisions` via
  `app/services/decision_log.py`, so `scripts/decision_report.py` can evaluate
  the futures pipeline the same way as the spot one.
- **A term-structure agent must abstain when it has no curve**, not infer one
  from the front month.

## Suggested shape

```
backend/app/pipeline/futures/
    graph.py            separate DAG; not a branch of the spot pipeline
    agents/
        term_structure.py   contango / backwardation, curve slope
        open_interest.py    OI change vs price change
        roll_calendar.py    expiry proximity, roll windows, session state
        basis.py            futures vs spot divergence
    contracts.py        universe, front-month selection, roll rules
frontend/app/futures/page.tsx
```

The spot pipeline's technical, quant, risk and trader agents are reusable
unchanged **provided** the price series handed to them is roll-adjusted. That
adjustment is the integration point, and it is the thing most likely to be got
wrong silently.
