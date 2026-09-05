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
