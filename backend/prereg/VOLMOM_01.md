# Pre-Registration — VOLMOM_01

**Title**: Volatility-Conditioned G10 Cross-Sectional Currency Momentum
**Written**: 2026-09-12, BEFORE any portfolio return was computed.
**Supersedes**: the `VOLCARRY_01` proposal, withdrawn — see §1.

**What HAD been computed before sealing** (design and power analysis only, no
portfolio return): data inventory, sigma_FX and the calm-regime frequency, the
correlation matrix and its eigenstructure, and Monte-Carlo null pass rates for the
gates. No momentum basket was ever formed. That boundary is why this document is
legitimate.

---

## 1. Why this is momentum and not carry

The predecessor `VOLCARRY_01` cited Menkhoff, Sarno, Schmeling & Schrimpf (2012,
*Journal of Finance*) — the **carry** paper, whose ranking signal is the forward
discount / interest differential.

`app/data/` holds 94 files, every one OHLCV. There are **no** rate, forward, swap,
deposit or OIS series. Therefore:

* Carry return is `spot + (i_foreign - i_USD)·dt`. The interest term — the dominant
  component of carry P&L — **cannot be computed**.
* Ranking by trailing 12-month **spot** return is a different factor. High-yield
  currencies tend to *depreciate* in spot (the forward premium puzzle), so spot
  momentum is not a noisy proxy for carry; it points the other way for exactly the
  currencies carry is long.

The specification is therefore **momentum**, and the governing reference is Menkhoff,
Sarno, Schmeling & Schrimpf (2012), *"Currency momentum strategies"*, **Journal of
Financial Economics 106(3), 660-684** — a different paper by the same authors. The
2012 *JF* carry paper is retained only as motivation for using aggregate FX volatility
as a state variable.

**No carry claim is made or tested here.**

## 2. Universe, sample, and measured design constants

```
UNIVERSE   EURUSD GBPUSD AUDUSD NZDUSD USDCAD USDCHF USDJPY   (7 G10 USD pairs)
SOURCE     app/data/*_h1.parquet
DISCOVERY  2010-09-24 .. 2023-12-29   82,337-82,347 H1 bars per pair
HOLDOUT    2024-01-01 .. 2026-09-07   SEALED, not read unless all gates pass
```

Measured before sealing:

```
daily panel                3,444 days
months in sample             160
calm months (invested)        89   (55.6%)  -> flat 44.4% of the time
mean sigma_FX  calm       0.0776   vs stressed 0.0964
participation-ratio N_eff   2.89 of 7   (top PC = 54.8% of variance)
```

## 3. Specification — frozen

```
S_k,d      foreign currency price in USD; INVERTED for CAD, CHF, JPY
DAILY BAR  last H1 close at or before 22:00 UTC (NY close)
r_k,d      ln(S_k,d) - ln(S_k,d-1)

sigma_FX,d = (1/7) * sum_k sqrt( (252/22) * sum_{i=1..22} r_k,d-i^2 )
bar_sigma,d = mean( sigma_FX,d-1 .. sigma_FX,d-60 )        [causal, shifted]
I_calm,d   = 1( sigma_FX,d < bar_sigma,d )

MOM_k,d    = ln(S_k,d) - ln(S_k,d-252)

REBALANCE  every 22 trading days, non-overlapping. Warmup 252 days.
BASKET     K=2 long (highest MOM), K=2 short (lowest MOM), weight 0.50 each
EXPOSURE   w_t = w_mom,t * I_calm,t      (flat to cash when stressed)
TOLL       charged on every leg that CHANGES at a rebalance, entry and exit
```

### Cluster constraint — CORRECTED from the reviewer's block

At most **one** currency per cluster in the long basket, and one per cluster in the
short basket. On collision the higher-ranked currency is kept and the next
non-colliding rank is promoted.

```
{EUR, CHF}      {GBP}      {AUD, NZD, CAD}      {JPY}
```

**This differs from the submitted specification and the change is measured, not
stylistic.** The reviewer proposed `{AUD,NZD} {EUR,CHF} {GBP} {CAD,JPY}`. Measured
correlations over the 3,444-day discovery panel:

| pair | rho | consequence of the submitted clustering |
| :--- | ---: | :--- |
| AUD/NZD | +0.822 | correctly separated |
| **AUD/CAD** | **+0.681** | 2nd-highest pair, **allowed to be held together** |
| EUR/CHF | **+0.641** | submitted as 0.78; the grouping survives, the number does not |
| **CAD/JPY** | **+0.117** | **lowest of all 21 pairs, forbidden from being held together** |

The submitted clustering forbids the best diversifying pair in the universe and permits
the second-worst collinearity. Average-linkage clustering on `1 - rho` at k=4 returns
the structure above: CAD joins the commodity bloc, JPY stands alone as the funding
currency.

### Tolls — CORRECTED

From `TOLL_BREAKEVEN_01` §4, which is the only measured source:

```
EURUSD 2.88   GBPUSD 3.10   USDJPY 3.51   AUDUSD 5.08
USDCAD 2.21   NZDUSD 7.33   USDCHF 4.48
```

The submitted block carried **GBPUSD 3.14**; §4 states **3.10**. All seven of these
instruments ARE in §4, so unlike `_squeeze_expansion.py` no toll here is invented.

## 4. Controls

**Control A — unconditioned momentum.** The identical cluster-constrained basket over
all 160 months with `I_calm` removed. Isolates the conditioner.

**Control B — random selection, 100 draws.** Random long/short assignment over the same
universe, same rebalance dates, same geometry, same tolls. Establishes the null
distribution of geometric drift. The control mean is reported and checked for centring.

## 5. Gates — fixed before running

### Gate 1 — economic significance

```
net expectancy > 0  AND  t >= 2.00 on the monthly net return series
```

**Stated in t, not Sharpe, deliberately.** The t-statistic is invariant to whether the
71 cash months are included; **Sharpe is not**, scaling by `sqrt(89/160) = 0.746`. The
submitted block said "Sharpe >= 0.73" without naming the sample, which is ambiguous by
34%:

```
Sharpe giving t = 2.00, invested months only : 0.734
Sharpe giving t = 2.00, all 160 incl. cash   : 0.548
```

Both Sharpe figures are **reported**; neither is the gate.

**Minimum detectable effect.** At N=89 invested months, `t = Sharpe_annual * 2.723`, so
t >= 2.00 requires `Sharpe_89 >= 0.734`. The reviewer's 48.9 bp/month floor assumes an
annualised basket volatility of 8.0%; **that figure is assumed, not measured**, and the
harness must report the realised basket volatility and restate the MDE from it.

### Gate 2 — the conditioner earns its place

Partition **Control A's** monthly returns by regime and test them directly:

```
mean(R_calm) - mean(R_stress) > 0   AND   Welch t >= 2.00      (n1=89, n2=71)
```

Null pass rate, verified independently: **0.0221** measured over 10,000 draws here,
0.0245 as submitted, 0.0237 theoretical for one-sided t>=2.00 at this df. These agree
within Monte-Carlo error.

This replaces the submitted Gate 2 (`Sharpe higher AND MaxDD lower`), which was
measured to pass **48.5% of the time on zero-edge noise** — being flat 44.4% of the
time lowers max drawdown mechanically in 83-86% of draws, and the Sharpe leg is a coin
flip. That gate could be passed by a random number generator and is withdrawn.

### Gate 3 — beats random selection

Welch `t >= 2.00` against the 100-draw Control B.

### Gate 4 — temporal stability

Net return > 0 in **>= 3 of 4** chronological 40-month sub-windows:

```
2010-09..2014-01   2014-01..2017-05   2017-05..2020-09   2020-09..2023-12
```

### Holdout protocol

`load_holdout()` is called **only** if Gates 1-4 all pass on discovery, enforced
structurally in the harness. `FOMCCYCLE_04` evaluated the holdout with two gates
failing; that violation is logged in `prereg/HOLDOUT_ACCESS.log`.

**Arming is a separate, higher bar** (registry `BAR`: t >= 3.0 across >= 70% of
symbols). Nothing here authorises arming.

## 6. Lookahead declaration

| variable | reads | causal |
| :--- | :--- | :--- |
| `sigma_FX,d` | `r_{d-22..d-1}` | yes |
| `bar_sigma,d` | `sigma_{d-60..d-1}`, shifted | yes |
| `I_calm,Tm` | both of the above | yes |
| `MOM_k,Tm` | `S_{Tm-252}` .. `S_{Tm}` | yes — all completed daily bars |
| position held | `Tm -> Tm+22` | outcome, not signal |

`assert_causal()` rebuilds the full signal path on truncated prefixes and requires
byte-identical weights. The DAX overnight proposal was refuted for reading `close[t]`
to select a window that had already closed, moving its t from -1.06 to +5.54.

**Non-overlapping by construction.** Rebalances are 22 trading days apart and positions
are held exactly one cycle, so no monthly return shares a day with another. This is the
defect that inflated the intraday studies, where a 16-bar hold sampled every bar took
raw t -4.08 to -0.67 once de-overlapped.

## 7. Honest prior

Wall 1 genuinely does not bind here: ~42 bp/year of toll against a plausible ~420
bp/year gross is ~10% — not the "<2.5%" originally claimed, but not fatal either. This
is the first pathway in the programme where toll is not the binding constraint.

**Wall 2 is now the binding constraint, and it binds hard.** N_eff is 2.89 of 7 pairs,
the conditioner discards 44.4% of the sample, and 89 invested months require an
annualised Sharpe of 0.734 to reach t = 2.00. Published G10 momentum Sharpes are
typically 0.3-0.6 gross on *broader* universes than seven pairs.

**My expectation is that Gate 1 FAILS**, at a Sharpe in the 0.2-0.5 range — real but
undetectable at this n. Gate 2 is the more interesting test: whether aggregate FX
volatility separates momentum returns at all is a statement about market structure that
does not depend on the strategy being tradeable. A Gate 2 pass with a Gate 1 fail would
be the most informative outcome available here, and is what I consider most likely.
