# Specification — CME Futures Data Ingestion (prerequisite for Option C)

**Written**: 2026-09-12. **Status**: specification only. No data has been fetched.
**Purpose**: replace carry-model projections with measured futures data.

Every futures conclusion in this programme so far — including the `WEINSTEIN_STAGE_01`
venue comparison and the `overnight_drift` financing audit — is **SPY cash with a
theoretical carry model subtracted**. There are no futures price series in either
repository. This document specifies what must exist before Option C can produce a
measurement rather than another projection.

---

## 0. The finding that justifies the work

Toll per round trip, computed from contract specifications:

| contract | notional (2023 ref) | 1 tick bp | commission bp | toll @1 tick | @2 ticks |
| :--- | ---: | ---: | ---: | ---: | ---: |
| MES | $22,500 | 0.556 | 0.462 | **1.018** | 1.573 |
| MYM | $17,000 | 0.294 | 0.612 | **0.906** | 1.200 |
| M2K | $9,250 | 0.541 | 1.124 | **1.665** | 2.205 |
| MCL | $7,500 | 1.333 | 1.387 | **2.720** | 4.053 |
| MGC | $19,500 | 0.513 | 0.533 | **1.046** | 1.559 |

Against measured CFD tolls (`TOLL_BREAKEVEN_01` §4): xauusd 5.00, audusd 5.08,
nzdusd 7.33, eurusd 2.88. **MGC at ~1.05 bp is 4.8x cheaper than the XAUUSD CFD.**

Two cautions that belong here rather than in a footnote:

1. **Micros carry a commission penalty in bp.** Notional is 1/10 of the full-size
   contract while commission is not 1/10. On M2K commission is 1.12 bp and on MCL
   1.39 bp — larger than the spread. **MCL at 2.72 bp is not meaningfully cheaper than
   the EURUSD CFD at 2.88.** The cost advantage is real for MES/MYM/MGC and marginal
   for MCL. Full-size contracts must be costed alongside micros, not assumed worse.
2. **The 4.3x slippage multiplier does not transfer.** It was measured on an MT5
   dealing desk where spread widens as the trade is placed. A central limit order book
   behaves differently. It must be **re-measured**, and must not be assumed to carry
   over *or* assumed to be 1.0. Until measured, every futures toll here is a lower
   bound.

## 1. THE STRUCTURAL PROBLEM WITH THE PROPOSED UNIVERSE

The scope names five micro contracts as the data source. **Four of the five have
almost no discovery history**, because the micro suite is recent:

```
MES, MYM, M2K   launched 2019-05-06   -> discovery (to 2024-01-01) ~4.6 years
MCL             launched 2021-07-12   -> discovery ~2.5 years
MGC             launched 2010-10-03   -> discovery ~13.2 years
```

A 2.5-year discovery window is the same weak instrument that made
`SQUEEZE_EXPANSION_01` (16 months) and `sp500_m30` (1.7 years) uninformative.

**Required design change — discover on full-size, execute on micros.**

```
DISCOVERY  ES, YM, RTY, CL, GC     full-size, deep history
EXECUTION  MES, MYM, M2K, MCL, MGC  1/10 notional, same underlying, same tick grid
```

The micro tracks the full-size contract on the same order book and settles to the same
index; the difference is notional and commission. Signal discovery therefore uses the
long series, and cost/sizing uses the micro specification. **All launch dates above are
to be VERIFIED from the data itself during Phase 1, not taken from this document.**

Constraint to check before any budget is committed: `GLBX.MDP3` history does not extend
indefinitely backwards. Phase 1 queries the actual available range.

## 2. Roll design

### 2.1 Trigger — volume crossover, confirmed at `t-1`

```
roll_date(T -> T+1) = first session t where
    volume[T+1, t-1] > volume[T, t-1]        observed at or before close of t-1
    AND that condition held on t-2 as well   (two-day confirmation, no whipsaw)
FALLBACK: if no crossover occurs, roll at  expiry - 8 calendar days
```

**Causality is structural, not asserted.** The decision to hold contract `T+1` over
session `t` uses only volume observed through the close of `t-1`. A roll rule reading
volume at `t` to decide the position held during `t` is the DAX error class (that
proposal moved from t −1.06 to +5.54 on exactly this defect).

Volume crossover is chosen over open-interest crossover because OI is published with a
one-session lag and is revised; using it invites a stale-data alignment bug. Fixed
calendar is retained only as a deterministic fallback so the rule always terminates.

**Do not use the vendor's continuous symbols (`ES.c.0`, `ES.v.0`, `ES.n.0`) as the
primary source.** They are convenient but they hide the roll decision inside a vendor
rule we cannot audit, and they are unadjusted stitches regardless. Fetch **raw
per-contract** bars and perform the roll here, where it is inspectable. The vendor
continuous series is fetched once as a **cross-check** (§4.3), not as the source.

### 2.2 Adjustment — store all three, do not choose

A single representation forces some downstream consumer into the wrong convention,
because this programme's consumers are genuinely split:

| consumer | needs | representation |
| :--- | :--- | :--- |
| `VOLMOM_01`, `WEINSTEIN_STAGE_01`, any trend/vol model | percentage returns | **ratio-adjusted** |
| squeeze / FVG / ORB style intraday brackets | ATR and tick geometry at real price levels | **raw + roll mask** |
| toll conversion (ticks -> bp) | true notional | **raw** |

Therefore store:

```
app/data/<root>_<tf>_raw.parquet      per-contract, NEVER adjusted, ground truth
app/data/<root>_<tf>.parquet          ratio-adjusted backward continuous + roll_flag
                                      (the default the loader sees)
```

Every continuous series carries a `roll_flag` column (1 on the first bar of a new
contract). Intraday modules consume the raw series and **mechanically bar any position
opened before and held across a `roll_flag` bar.**

**Ratio (multiplicative, backward) is the default**, because it preserves percentage
returns and cannot produce negative prices.

> **Specific hazard — negative crude.** CL settled at **−$37.63 on 2020-04-20**. Ratio
> adjustment is mathematically undefined across a non-positive price, and difference
> adjustment can drive an adjusted series negative. MCL postdates that print
> (launched 2021), so MCL is unaffected — but the Phase-1 decision to **discover on
> full-size CL** puts it squarely in range. The ingestion harness must assert
> `min(close) > 0` on every contract before ratio adjustment and **fail loudly**,
> naming the contract and date, rather than emitting `inf`/`NaN`.

## 3. Storage layout and loader contract

Files must satisfy `_discovery._read()`, which detects `time` / `date` / `timestamp`
and requires `ts.dt.year.max() >= 1990`.

```
schema (all bar files):
  ts              datetime64[ns, UTC]   strictly increasing, unique
  open high low close   float64
  volume          int64    exchange volume, > 0 on regular session bars
  contract        string   e.g. "ESH4"           (raw files, and continuous provenance)
  roll_flag       int8     continuous files only, 1 on first bar of a new contract
  adj_factor      float64  continuous files only, cumulative ratio applied
  open_interest   optional (int64, present only when statistics schema is ingested)
```

**Timestamps are UTC nanoseconds from Databento.** `pd.to_datetime` defaults to
nanoseconds, which is why `spy_daily` epoch-*seconds* silently mapped to 1970 and was
twice reported as a corrupt file. Assert `1990 <= year <= 2030` after parsing, in the
ingestion harness, before writing.

**All writes UTF-8 explicit, ASCII content.** `bindings.json` was once written with
`ensure_ascii=False` and a bare `open()` read it under cp1252, destroying every binding.
Contract symbols are ASCII; keep them so.

## 4. Integrity harness — assertions, not inspection

`ief/ingest/verify_futures.py`. No parquet is registered in `app/data/` until every
check passes. Each failure names the contract and timestamp.

**4.1 Timestamp and session integrity**
- `ts` strictly monotonic increasing, no duplicates, tz-aware UTC.
- The daily settlement halt (17:00–18:00 ET) and the weekend gap (Fri 17:00 → Sun 18:00
  ET) are the **only** permitted gaps above one bar interval on intraday files. Any
  other gap is reported with its duration; holiday closures are enumerated against an
  exchange calendar, not inferred from the data.
- DST: the halt is defined in **America/New_York**, not a fixed UTC offset. A fixed
  offset is wrong for roughly five months a year — the error that corrupted the FOMC
  cycle study and produced 53–57 holidays per year.

**4.2 Volume and open interest**
- `volume > 0` on every regular-session bar. Zero-volume bars are flagged, not dropped
  silently, and counted in the report.
- `open_interest` is omitted from basic `ohlcv-1d` files. Populating it requires the
  separate `statistics` schema ($8.55 total, with CL alone $6.57). Because the roll
  trigger uses volume crossover by design, spending credits on deferred-month open
  interest provides zero marginal signal. If open interest is required for macro
  positioning research, it is sourced at zero cost from weekly CFTC COT reports.

**4.3 Roll discontinuity audit**
- At each `roll_flag`, the raw price gap must equal the settlement differential of the
  two contracts on the roll date, within exchange settlement tolerance.
- `adj_factor` must reproduce the raw series exactly: `raw * cumulative_adj == adjusted`
  to floating tolerance, asserted end-to-end.
- **Independent cross-check**: the computed roll dates are compared against the vendor
  continuous series (`<ROOT>.v.0`). Divergence is reported per contract. It is a
  *diagnostic*, not an authority — our rule governs.

**4.4 Holdout partition**
- No special handling required and none permitted. `DISCOVERY_END = 2024-01-01` and
  `HOLDOUT_END = 2026-09-07` are already enforced in `_discovery.py`; `load_holdout()`
  refuses without `prereg/<id>.md` on disk and appends the file's SHA-256 to
  `prereg/HOLDOUT_ACCESS.log`.
- The harness asserts each file spans the discovery boundary and **reports discovery
  bar counts only**. It must never print, plot or summarise post-2024 bars. Two
  breaches are already logged; the second one spent the 08:30–09:30 window because a
  script iterated a full parquet without filtering.

## 5. Instrument metadata

The specifications supplied were checked and are **correct**:

| contract | exchange | point value | tick | tick $ | toll @1tk |
| :--- | :--- | ---: | ---: | ---: | ---: |
| MES | CME | $5.00 | 0.25 | $1.25 | 1.018 bp |
| MYM | CBOT | $0.50 | 1.00 | $0.50 | 0.906 bp |
| M2K | CME | $5.00 | 0.10 | $0.50 | 1.665 bp |
| MCL | NYMEX | $100.00 | 0.01 | $1.00 | 2.720 bp |
| MGC | COMEX | $10.00 | 0.10 | $1.00 | 1.046 bp |

Session Sun 18:00 – Fri 17:00 ET with a 17:00–18:00 daily halt: correct for all five.

**Commission must be sourced, not assumed.** The `$1.04` RT figure is plausible for
micros (≈$0.25 commission + ≈$0.27 exchange/regulatory per side) but no broker schedule
is on file. It enters `core/cost_model.py` under `toll_source = 'ESTIMATED'` until a
statement or schedule is attached. `_squeeze_expansion.py` shipped three invented tolls
labelled as measured; that defect is logged at `core/evidence.py:382-390` and will not
be repeated.

Symbol mapping: root + CME month code + single-digit year for raw storage
(`ESH4`, `MCLM4`), month codes `F G H J K M N Q U V X Z`. Store the mapping explicitly
per file rather than parsing it at read time.

## 6. Phased delivery

**Phase 1 — reconnaissance, no data purchased.** Query
`metadata.get_dataset_range('GLBX.MDP3')` for the true available history; enumerate
contract listings per root; run the existing `estimate_cost()` for each root and
schema. **Output: a cost and coverage table. Nothing is fetched.** This settles whether
full-size history is deep enough to be worth the spend, and it is the gate on Phase 2.

**Phase 2 — daily bars first.** `ohlcv-1d` for ES, YM, RTY, CL, GC, raw per contract.
Smallest payload, and sufficient to re-run `WEINSTEIN_STAGE_01` and `VOLMOM_01` on real
futures. Integrity harness must pass before registration.

**Phase 3 — intraday.** `ohlcv-1h` then `ohlcv-1m` only for roots that Phase 2 shows
are worth it. `ohlcv-1m` across five roots over a decade is the dominant cost in the
project; it is not purchased on spec.

**Phase 4 — slippage measurement.** The existing `tbbo`/`mbp-10` adapter path measures
the realised futures slippage multiplier against the touch. This is what replaces the
assumed 4.3x, and it is the single highest-value measurement in the plan.

## 7. What must not happen

1. **No strategy is tested during ingestion.** This phase produces data and a verified
   integrity report. Backtests come after, each behind its own pre-registration.
2. **No re-use of a spent hypothesis.** Migrating a refuted CFD strategy to futures is
   a *new* test of a *new* venue, requiring a new prereg with gates fixed in advance —
   not a re-run until the venue is favourable.
3. **No holdout contact.** Ingestion touches post-2024 bars only to write them to disk.
4. **The API key is never printed.** It lives in `InstitutionalEdgeFutures/.env`
   (gitignored at `.gitignore:1`, verified). Diagnostics report `SET (len N)` only.
   Note: `ief/config/secrets.py:44 status()` currently returns the last four characters
   of the key; that should be removed.

## 8. Open questions for decision before Phase 2

1. **Full-size vs micro for discovery.** §1 recommends full-size. Confirm.
2. **Budget ceiling** for the Databento spend, so Phase 1 can report against it.
3. **RTY history** begins at CME in 2017 (Russell futures traded on ICE before that).
   Accept ~7 years, or substitute a longer-history root?
