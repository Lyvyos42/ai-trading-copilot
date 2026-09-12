# RESULTS — SQUEEZE_EXPANSION_01

**Prereg**: `prereg/SQUEEZE_EXPANSION_01.md`, sha `cbb6a7e6ed1a1f22`, sealed before any
return was computed.
**Harness**: `_squeeze_expansion.py`
**Run**: 2026-09-12, discovery only (`ts < 2024-01-01`), 444,449 M15 bars, 12 instruments.
**Holdout**: NOT READ. All four gates failed; the harness branch is unreachable.

---

## 1. Verdict — all four gates FAIL

| gate | requirement | measured | |
| :--- | :--- | ---: | :--- |
| 1 economic | pooled net > 0, `t_adj >= 2.00` | net **-5.91 bp**, `t_adj` **-1.04** | FAIL |
| 2 squeeze earns its place | Welch vs Control A `>= 2.00` | **+0.71** | FAIL |
| 3 beats random timing | `z >= 2.00` vs Control B | **-0.49** | FAIL |
| 4 breadth | net > 0 on `>= 7 of 12` | **0 of 12** | FAIL |

Causality assertion PASSED on 32,418 eurusd_m15 bars across four truncation points.

## 2. The result is not a toll result

Re-run with `toll = 0` to separate Wall 1 from signal failure:

```
POOLED GROSS  treat  -0.90 bp  (t -0.24, n  1263)
              ctrlA  -4.44 bp  (t -1.54, n  1968)
              ctrlB  +1.11 bp  (t +1.07, n 20684)
```

**Gross expectancy is -0.90 bp at t -0.24 — indistinguishable from zero before a single
pip of cost is charged.** Wall 1 is not the binding constraint here. There is no gross
edge for the toll to consume.

Control B (random entry, identical geometry, 10 draws, 20,684 trades) returns **+1.11 bp
at t +1.07** — acceptably centred on zero, so the comparison is valid. The centring check
is performed on GROSS: a net control pays toll and structurally cannot centre at zero,
which is a defect in how the check was phrased in prereg §5 and is noted rather than
quietly skipped.

## 3. The filter stack does not beat coin flips

```
treat - ctrlB (gross) = -2.01 bp   Welch -0.51
```

**Random entries with the same bracket outperform the four-filter stack**, nominally,
though not significantly. Squeeze, H4 alignment, close dominance and volume surge together
add nothing detectable over uniformly random timing.

The win rate makes the mechanism plain:

```
win rate  0.270      geometric breakeven  1/(1+2.5) = 0.286
gross expectancy in R                     -0.0550 R
```

A 1:2.5 bracket on an efficient price lands at its own breakeven win rate by construction.
0.270 against 0.286 is that signature. The filters did not move the price process; they
selected a subset of bars on which the bracket behaved exactly as a bracket behaves.

## 4. Per-instrument, net of measured toll

| symbol | n | net bp | t | win | ctrlA n | ctrlA bp | Welch | ctrlB bp |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| audusd | 100 | -8.21 | -3.75 | 0.220 | 151 | -8.22 | +0.00 | -5.93 |
| eurgbp | 78 | -6.02 | -5.40 | 0.205 | 146 | -6.32 | +0.18 | -3.98 |
| eurjpy | 76 | -4.63 | -2.06 | 0.276 | 126 | -2.35 | -0.71 | -4.99 |
| eurusd | 85 | -2.67 | -1.88 | 0.294 | 153 | -3.26 | +0.26 | -3.30 |
| gbpusd | 98 | -3.44 | -2.20 | 0.276 | 151 | -2.58 | -0.32 | -3.46 |
| nzdusd | 90 | -4.45 | -1.50 | 0.322 | 133 | -9.60 | +1.27 | -8.74 |
| usdcad | 94 | -3.32 | -2.58 | 0.223 | 152 | -2.21 | -0.57 | -3.37 |
| usdchf | 73 | -3.25 | -1.78 | 0.329 | 154 | -3.99 | +0.27 | -3.45 |
| usdjpy | 95 | -2.11 | -0.91 | 0.316 | 152 | +0.80 | -0.89 | -4.70 |
| wti | 251 | -6.17 | -0.32 | 0.279 | 309 | -26.86 | +0.79 | +2.22 |
| xagusd | 118 | -13.10 | -2.96 | 0.297 | 163 | -20.88 | +1.11 | -10.06 |
| xauusd | 105 | -9.64 | -4.73 | 0.200 | 178 | -6.36 | -1.02 | -5.16 |

## 5. The pre-declared high-ATR subgroup also fails

Named in prereg §3 before results, because their ATR/toll ratio is structurally different:

```
wti     n=251  net  -6.17 bp  t -0.32   (gross -0.17 bp)
xagusd  n=118  net -13.10 bp  t -2.96   (gross -4.10 bp)
xauusd  n=105  net  -9.64 bp  t -4.73   (gross -4.64 bp)
```

WTI was the strongest prior in the document — Wall 1 costs it 1.0 win-rate point against
18.0 for EURGBP. Its gross is **-0.17 bp**. The escape route the arithmetic pointed to is
empty: widening the geometry removed the toll objection and revealed there was never a
gross edge underneath it.

## 6. What is NOT concluded

**The compression premise is unresolved, not refuted.** The squeeze arm beats the
no-squeeze arm by **+3.54 bp gross (Welch +0.74)** — the sign predicted by the
specification, at a magnitude the data cannot separate from noise. Roughly 7x the current
sample would be needed to resolve it. Filing this as "compression does not predict
expansion" would overclaim.

What IS concluded is narrower and firmer: **this specification, traded with this geometry
and this toll, is not profitable, and does not outperform random entry.**

**No parameter was swept and none will be.** Prereg §4 fixes the 20th percentile, the 1.75
ATR multiple, the 2.5 RR, the 1.5x volume threshold and the 96-bar stop. Re-running at the
15th percentile to find a positive cell is the error that produced the 472-variant ledger.

## 6b. CORRECTION — toll sourcing defect, added 2026-09-12

Section 4 of `TOLL_BREAKEVEN_01` lists **nine** instruments. `_squeeze_expansion.py`
labelled all twelve of its tolls as coming from that section. The tolls for **eurjpy
(4.50), xagusd (9.00) and wti (6.00) were invented and are not measured.**

Impact, measured rather than asserted:

```
all 12 (3 tolls invented) : n=1263  net -5.91 bp  t_adj -1.04
9 sourced tolls only      : n= 818  net -4.91 bp  t_adj -4.94
```

Gate 1 fails either way and the gross result (-0.90 bp, t -0.24) is toll-independent.
The refutation is **stronger** on the sourced subset; the difference is driven by WTI
variance dominating the pooled sd, not by the toll values. The three invented figures
must not be cited as measured tolls anywhere.

## 7. Limitations, stated

1. **Discovery spans 2022-06 to 2024-01 — about 16 months, one macro regime** (WTI excepted,
   from 2011). A strategy premised on volatility regime transitions is being judged on a
   narrow sample of regimes.
2. **Filter 4 is tick volume on 11 of 12 instruments.** `real_volume` is identically zero on
   all FX and metal CFDs. The "institutional participation" mechanism was not measured;
   quote-update activity was.
3. **Entry is market at `open[t+1]`, not the passive retest** the source specification
   proposed. Whether a limit fills is not a function of OHLCV. Given gross expectancy of
   -0.90 bp, a passive entry saving at most `toll/4.3` cannot reverse the sign
   (`TOLL_BREAKEVEN_01` §3).
