# Pre-Registration — SQUEEZE_EXPANSION_01

**Written**: 2026-09-12, BEFORE any return, expectancy or t-statistic was computed.
**Type**: directional volatility-expansion strategy test. M15 panel, 12 instruments.
**Origin**: user specification of 2026-09-12 — sigma as a signless dispersion operator
paired with a signed location reference, filtered by compression, HTF bias, close
dominance and volume.

**What HAD been computed before sealing** (power analysis only, no P&L):
signal counts per instrument, ATR(14) at signal, and the spread column. No return,
no win rate, no expectancy. That boundary is the reason this document is legitimate.

---

## 1. The claim under test

> A `2σ` displacement is direction-free. Paired with a signed anchor `μ` it becomes a
> displacement *with sign*. Of those, the subset that ignites **out of prior volatility
> compression**, **with** higher-timeframe alignment, close dominance and a volume
> surge, produces sustained directional expansion rather than mean reversion.

The distinctive claim is **Filter 1**: that trends ignite from compression. Gate 2 tests
exactly that and nothing else.

## 2. Why this is not excluded by TOLL_BREAKEVEN_01

`TOLL_BREAKEVEN_01` §3 bounds what *passive execution* can rescue: `edge/toll >= 0.767`.
That bound governs candidates whose edge is below their toll. It does **not** apply here,
because this strategy is not seeking a 1-3 bp edge — it targets 15-423 bp per trade.

**This is the first proposal in the programme that attacks Wall 1 structurally rather than
by execution.** Toll is approximately fixed per round trip; edge scales with the geometry.
Widening the geometry is the only manoeuvre that changes the ratio. That is why it is
being tested.

## 3. The arithmetic that decides it, computed before running

Required win rate decomposes exactly:

```
req_p  =  1/(1+r)   +   toll/(S*(1+r))   +   0.825/sqrt(n)
          geometry       Wall 1             Wall 2
           0.286
```

with `r = 2.5`, `S` the stop in bp, `n` the trade count. The third term derives from
`1.65*sd/sqrt(n)` with `sd ~= 0.5*S*(1+r)` for a two-point outcome.

**The Wall 2 term is invariant to geometry.** Widening targets cannot reduce it. This is
stated now because it is the most likely reason the test fails, and it must not be
discovered after the fact.

Measured ATR(14) at signal, with `S = 1.75*ATR`, `toll` from `TOLL_BREAKEVEN_01` §4:

| symbol | n | ATR bp | stop bp | Wall 1 | Wall 2 | req_p | vs BE |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| eurgbp | 103 | 3.5 | 6.1 | +0.180 | +0.081 | 0.547 | 1.91x |
| usdchf | 120 | 5.0 | 8.8 | +0.146 | +0.075 | 0.507 | 1.78x |
| nzdusd | 153 | 8.7 | 15.2 | +0.138 | +0.067 | 0.490 | 1.71x |
| eurjpy | 112 | 6.3 | 11.0 | +0.117 | +0.078 | 0.480 | 1.68x |
| eurusd | 139 | 3.9 | 6.8 | +0.121 | +0.070 | 0.476 | 1.67x |
| gbpusd | 160 | 4.4 | 7.7 | +0.115 | +0.065 | 0.466 | 1.63x |
| audusd | 180 | 7.8 | 13.7 | +0.106 | +0.061 | 0.454 | 1.59x |
| xauusd | 174 | 7.7 | 13.5 | +0.106 | +0.063 | 0.454 | 1.59x |
| usdjpy | 149 | 6.0 | 10.5 | +0.096 | +0.068 | 0.449 | 1.57x |
| usdcad | 143 | 3.9 | 6.8 | +0.093 | +0.069 | 0.447 | 1.57x |
| xagusd | 195 | 16.1 | 28.2 | +0.091 | +0.059 | 0.436 | 1.53x |
| **wti** | **404** | **96.6** | **169.0** | **+0.010** | **+0.041** | **0.337** | **1.18x** |

**Pre-declared high-ATR subgroup: `wti`, `xagusd`, `xauusd`.** Named here, before results,
because their ATR/toll ratio is structurally different — the WTI Wall 1 term is 1.0 point
against 18.0 for EURGBP. If the strategy works anywhere it should work there, and claiming
that *after* seeing results would be selection.

## 4. Frozen specification — ONE variant, nothing swept

```
timeframe        M15
mu_t, sigma_t    SMA(20) and population stdev(20) of close
BBW_t            4*sigma_t / mu_t
SQUEEZE          BBW[t-1] in the lowest 20th percentile of the 50 bars ENDING t-1
                 (measured at t-1, not t: sigma expands ON the breakout bar)
H4 BIAS          sign(close_H4 - SMA200_H4), LAST COMPLETED H4 bar only
CRP_t            (close - low) / (high - low)
VOLUME           tick_volume[t] >= 1.5 * mean(tick_volume[t-20..t-1])
LONG             close[t] > mu[t] + 2*sigma[t]  AND CRP[t] >= 0.75 AND bias > 0
SHORT            close[t] < mu[t] - 2*sigma[t]  AND CRP[t] <= 0.25 AND bias < 0
ENTRY            open[t+1], market
STOP             1.75 * ATR(14)[t] from entry
TARGET           2.5 * stop
TIME STOP        96 bars (24h)
OVERLAP          at most ONE open position per instrument; signals while open are DROPPED
TIE RULE         if a bar range spans both stop and target, resolve as STOP
TOLL             per-instrument, TOLL_BREAKEVEN_01 section 4, charged once per round trip
```

**No parameter in this block is swept.** The 20th percentile, the 1.75 ATR multiple, the
2.5 RR, the 1.5x volume threshold and the 96-bar stop are fixed here. If a gate fails, the
verdict is FAILED — not "retry at the 15th percentile". The programme ledger stands at 472
swept variants and that is the error this clause exists to prevent.

### Two deviations from the source specification, declared

1. **Entry is market at `open[t+1]`, not a passive limit on the retest.** Whether a limit
   order fills is not a function of OHLCV (`PASSIVE_EXECUTION_01` §2). Backtesting a
   passive retest would require assuming a fill rate, which is the assumption that
   experiment exists to measure. Market entry is the conservative, measurable choice.
2. **Filter 4 is TICK volume, relabelled.** `real_volume` is identically zero on all 11
   FX and metal series — these are CFDs with no consolidated tape. Only `wti` carries
   real volume. The filter is therefore a **quote-activity proxy**, and the stated
   mechanism ("institutional participation") is NOT what is being measured on 11 of 12
   instruments. This is a limitation of the data, not a finding.

## 5. Controls

**Control A — matched, isolates the squeeze.** Identical in every respect (2σ break, H4
bias, CRP, volume, geometry, toll) except `BBW[t-1]` is **not** in the bottom quintile.
Same instrument, same era, same everything but compression. This is what makes Gate 2 a
test of Filter 1 rather than of the strategy as a whole.

**Control B — random timing, >= 10 draws.** Entries drawn uniformly at random per
instrument, matched on count and side distribution, identical geometry and toll, pooled
over at least 10 draws. The empirical null sd is re-estimated **per population**, never
carried over. The control mean is reported and checked for centring on zero; a control
that is not centred invalidates the comparison and must be reported as such.

## 6. Universe and de-overlapping

12 M15 series, discovery only (`ts < 2024-01-01`), 444,449 bars.
**Discovery span is 2022-06 to 2024-01 — roughly 16 months, one macro regime** — except
`wti`, which reaches 2011. This is a material limitation and is stated before results.

Overlapping holds inflate `t` by ~sqrt(overlap). The one-position-per-instrument rule makes
trades non-overlapping **within** an instrument by construction. **Across** instruments
they remain correlated; the pooled statistic is therefore correlation-adjusted with
`N_eff ~= 5.5` for this panel (9 FX ~= 4.0 independent, 2 metals ~= 1.0, WTI ~= 1.0).

## 7. Gates — fixed before running

* **Gate 1 — economic.** Pooled net expectancy > 0 after measured toll, correlation-adjusted
  pooled `t >= 2.00` against zero.
* **Gate 2 — the squeeze earns its place.** Squeeze arm minus Control A, Welch `t >= 2.00`.
  *If this fails, Filter 1 is decoration and the central claim of the specification is
  refuted regardless of Gate 1.*
* **Gate 3 — not geometry alone.** Squeeze arm beats Control B by `>= 2.00` empirical-null
  sd, null re-estimated on this population.
* **Gate 4 — breadth.** Net expectancy positive on `>= 7 of 12` instruments (0.58).

**Holdout protocol.** `load_holdout()` is called **only** if Gates 1-4 all pass on
discovery. The harness enforces this structurally: the holdout branch is unreachable
unless every gate is True. This clause exists because `FOMCCYCLE_04` evaluated the holdout
with two gates failing, and that violation is logged in `prereg/HOLDOUT_ACCESS.log`.

**Arming is a separate, higher bar.** Passing these gates makes this a CANDIDATE, not a
live module. The registry arming bar is `t >= 3.0` across `>= 70%` of symbols over 4
windows. Nothing here authorises arming.

## 8. Lookahead declaration

| variable | reads | causal at decision time |
| :--- | :--- | :--- |
| `mu[t]`, `sigma[t]` | `close[t-19..t]` | yes |
| `BBW` percentile | `BBW[t-50..t-1]` | yes — ends at t-1 |
| H4 `SMA200` | last **completed** H4 bar before t | yes — shifted |
| `CRP[t]` | `high[t] low[t] close[t]` | yes |
| volume baseline | `tick_volume[t-20..t-1]` | yes — excludes t |
| entry | `open[t+1]` | outcome, not signal |

The H4 bias is the live risk: resampling M15 to H4 and reading the bar *containing* t
leaks the remainder of that bar. It is shifted by one completed H4 bar. The DAX overnight
proposal was refuted for precisely this class of error, moving its `t` from -1.06 to +5.54.
`assert_causal()` rebuilds every signal series on truncated prefixes at four cut points and
requires byte-identical output. An alignment error cannot pass silently.

## 9. Honest prior

The arithmetic in §3 says FX needs a 45-55% win rate on a 1:2.5 system against a 28.6%
breakeven — a 1.5-1.9x lift. I do not expect that.

**My expectation is Gate 1 FAILS pooled**, carried down by the nine FX pairs where Wall 1
costs 9-18 win-rate points. The interesting question is Gate 2: whether compression
predicts expansion *at all*, independent of whether the result is tradeable after toll. A
squeeze arm that beats Control A while still losing money after cost would be a genuine
finding about market structure and a clean example of Wall 1 binding on a real effect.

WTI is where I would expect signal if it exists anywhere: Wall 1 costs it 1.0 win-rate
point against 18.0 for EURGBP. But `n = 404` on one instrument is a single-instrument
result in a programme that has refuted 30 candidates, and it would need the holdout to
mean anything.

**Most likely outcome: Gate 1 fails, Gate 2 decides whether this is filed as a refutation
of the compression premise or as another Wall 1 casualty.**
