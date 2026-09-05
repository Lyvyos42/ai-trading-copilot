# Signal engine audit and repair — 2026-09-05

Triggered by a production screenshot: 50 signals, every one BEARISH, all
timestamped 15h ago, WINS 0 / LOSSES 4, every row showing R:R 3.5:1.

## The finding

**Every agent in the pipeline fabricated its output when its data source was
missing** — from a `random.Random` seeded on the ticker and the date. Not as a
rare fallback: as the live production path, because no LLM API key is set and
`_call_claude` returns None, which drops each agent into its mock.

Proof, not inference. The bull case rendered on screen read:

> EURJPY=X shows positive earnings momentum (EPS growth: 6.0%). Value score is
> stretched at P/E 28.2x. Applying strategy 3.2 (earnings momentum) and 3.3 ...

That is a character-for-character match to the f-string in
`agents/fundamental.py::_mock_analysis`, whose inputs were:

    eps_growth = market_data.get("eps_growth", rng.uniform(-10, 30))
    pe         = market_data.get("pe_ratio",   rng.uniform(10, 35))

EURJPY is a currency pair. It has no EPS and no P/E, so both defaults fired
every time. The "6.0%" and the "28.2x" were random numbers.

The seed was ticker + date, so output was *stable within a day*. That is why
this looked like analysis for so long: it did not flicker.

## Corrections to the first draft of this audit

Three claims in the initial version were wrong and are corrected here.

1. **macro was NOT wholesale fabricated.** Its live-news path does real
   keyword analysis over actually-scraped headlines. Only the no-news path
   invented a regime. Its real defect was different and worse — see below.
2. **technical was NOT fully real.** It has a mock path too: `if not closes:
   return self._mock_analysis(ticker)` returned a random direction at up to
   88% confidence on a random price between 50 and 500, including invented
   support and resistance. It is real *when bars exist*, and was fabricating
   when they did not.
3. **The 3.5:1 R:R is measured, not assumed.** `scripts/backtest_screener.py`
   exists and was run: tp 3.5 / sl 1.0 / 10-bar hold was the best of 54
   configurations over 3 years of real bars on a 20-symbol universe, at
   +0.265R expectancy. Calling it "an assumption printed as a finding" was
   wrong. What is true is that it is a *constant*, so the per-signal
   "POTENTIAL R:R" field carries no per-signal information.

## What was actually wrong, and what was done

| agent | defect | repair |
|---|---|---|
| technical | random direction + random price when the feed returned no bars; fake support/resistance flowed into the risk manager | strictest abstention — no bars, no reading |
| fundamental | invented EPS and P/E for every non-equity | abstains unless real figures exist; real equity path retained |
| sentiment | drew headlines from a hardcoded `MOCK_HEADLINES` pool, then analysed its own invention | abstains — no coverage is not neutral sentiment |
| macro | **structural SHORT bias** (below) + regime invention when the feed was empty | symmetric regime test; abstains with no news |
| regime_change | `stability`, `change_probability`, VIX term structure all from RNG; VIX defaulted to a plausible 18.0 | rebuilt on realised volatility (ATR/close), which is real; no VIX curve claimed |
| correlation | correlation coefficient from `rng.uniform(0.2, 0.6)`, with contagion and diversification derived from it | abstains — a coefficient needs two price series and this agent receives one |
| risk_manager | invented the portfolio it was protecting (drawdown, sector concentration, correlation), then approved/rejected real signals against it | reads the real portfolio; reports what it cannot check |
| quant | invented win rate, sample size, p-value, Sharpe, expectancy — then computed significance from them | abstains; `statistical_edge` is None (unknown), not False |
| trader | `position_size_pct` fell back to `rng.uniform(1, 3)` — a random 1-3% of equity shown as a sizing recommendation | None, meaning size it yourself |

Two further defects found during the repair, neither of them in an agent:

- **`market_data.py` generates synthetic bars.** When both TradingView and
  yfinance fail, `_mock_market_data` builds 260 bars from
  `rng.gauss(0.0001, 0.012)` — a random walk — and tags `data_source="mock"`.
  Every downstream calculation was then correct arithmetic on invented prices.
  The tag was already recorded and simply never checked. The trader now
  refuses to publish any signal when it is set.

- **`risk_manager` passed analyst confidence to Kelly as a win probability.**
  `win_prob = avg_confidence / 100`. "The analysts are 65% confident" and "65%
  of these trades win" are different quantities, and Kelly is violently
  sensitive to the difference. Kelly is no longer computed without a measured
  win rate.

## The uniform bearishness

Not fabrication — a real logic defect, in `macro.py::_derive_from_news`:

    if crisis_hl or geo_risk > 65 or fed_stance == "HAWKISH":
        regime, direction, confidence = "RISK_OFF", "SHORT", 65.0
    elif avg_sent > 0.1 and fed_stance != "HAWKISH":
        regime, direction, confidence = "RISK_ON", "LONG", 60.0

Three faults stacked:

1. **Asymmetry.** RISK_OFF fired on *any* of three conditions; RISK_ON required
   two to hold at once.
2. **Article count read as risk.** `geo_risk = min(95, max(10, geo_count * 8 + 20))`
   measures how many geopolitical articles the scraper saved. Six articles put
   it at 68, over the threshold, forcing RISK_OFF on volume rather than
   content. The screenshot showed exactly 68/100.
3. **One hawkish word anywhere.** `fed_stance` matches substrings like
   "tighten" or "inflation concern" across the whole concatenated feed — and
   that feed is **global, not per-symbol**. One headline set one boolean that
   then voted SHORT at 65% confidence on every symbol in the scan.

That is 50 consecutive SHORT signals across six unrelated symbols, from one
agent, driven by article volume. The regime test is now symmetric and
content-driven, confidence scales with corroboration instead of being a
constant 65, and the result is flagged `symbol_specific: False` so it is
weighted as shared context rather than an independent per-symbol opinion.

## New: the pipeline can now say "no"

Removing fabrication is only safe if silence propagates correctly. Previously
`direction = "LONG" if probability_score >= 50 else "SHORT"` could not return
"no opinion" — an empty tally defaulted to 50.0 and the `>=` sent it to LONG.
With agents now abstaining, that would have converted silence into a buy
recommendation.

- `BaseAgent.abstain()` is the single honest no-data response: NEUTRAL,
  confidence 0, `abstained: True`.
- Abstentions are excluded from the vote tally rather than counted as zero
  (which reads as "certain there is no edge") or defaulted to 50 (which
  invents a vote).
- `TraderAgent.MIN_DIRECTIONAL_VOTES = 2`. Below it, status is `NO_SIGNAL`
  with the abstaining agents named.
- Confidence is scaled by coverage, so two agreeing agents out of seven no
  longer read like seven. The old formula could return 92 on a single
  unopposed vote.

Verified end to end: FX with no fundamentals abstains; AAPL with a real P/E of
28.0 still produces LONG at 56.8 citing the reported figures; no bars produces
`support=None`; one directional vote produces NO_SIGNAL; `data_source="mock"`
produces NO_SIGNAL with no entry price.

## Still outstanding

- **Nothing resolves signals.** `signal_resolver.py` exists (264 lines) but no
  scheduler calls it — `main.py` never references it. 46 of 50 signals will
  never resolve, and WINS/LOSSES counts only hand-pressed buttons. The 0% win
  rate on the page is not a measured 0%.
- **Asset class is wrong.** EURJPY=X is tagged `stocks`.
- **Percentage signs are inverted.** Target $174.185 against a price of
  $181.482 is -4.0%, displayed as +4.0%.
- **RNG remains in routes** — `agents.py`, `correlations.py`, `market.py`,
  `portfolio.py`, `signals.py` — and in `market_data.py`'s generator. These
  feed panels rather than signals, but each needs the same treatment.
- **The 50 fabricated signals are still in the database** and still counted.

## Order of work from here

A restructure cannot raise the win rate of a system whose inputs are random,
so the sequence is: remove fabrication (done for the agent layer), wire real
sources for what can be real, schedule the resolver so outcomes are measured
rather than clicked, and only then tune — against measured outcomes, with the
same discipline used in IEB.

Expect the app to look *worse* first. Most agents will abstain and few signals
will pass. That is the correct behaviour.
