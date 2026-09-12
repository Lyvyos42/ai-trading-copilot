# Adversarial Review Request — VOLCARRY_01 specification

You proposed `VOLCARRY_01` (Pathway 3: Long-Horizon Macro / Volatility-Conditioned
Carry), citing Menkhoff, Sarno, Schmeling & Schrimpf (2012, *Journal of Finance*).

The specification was audited before implementation. **Three of its premises were
verified and hold. Three findings contradict it.** You are asked to defend, amend, or
withdraw the specification against those findings.

This is a disagreement to be resolved on evidence, not a request for a survey of
options. **Take a position and defend it.**

---

## 1. Verified — these are not in dispute

Measured directly from `app/data/` on 2026-09-12. Do not re-litigate these.

* **Data exists as you described.** 7 G10 USD pairs in `app/data/*_h1.parquet`,
  82,337-82,347 discovery bars each, spanning 2010-09-24 to 2023-12-29. Your figure of
  "82,340 H1 bars per pair" is accurate.
* **The non-overlapping monthly design is correct** and is a genuine methodological
  advance over the intraday studies, whose t-statistics were inflated by 16-bar overlap
  (semi-variance raw t -4.08 collapsed to -0.67 de-overlapped).
* **Pathway 3 does escape Wall 1.** Your conclusion is right even though your arithmetic
  is wrong: the correct toll denominator is expected edge, not the 150-300 bp price
  swing. Four positions at 0.5 weight with roughly half the slots turning monthly gives
  ~42 bp/year against a plausible ~420 bp/year gross, so **~10%, not "<2.5%"**. Toll
  still does not bind at this horizon. The error does not change the verdict.

## 2. Finding A — there is no interest-rate data, so this cannot be a carry test

`app/data/` holds 94 files. Every one is OHLCV. There are **no** rate, forward, swap,
deposit or OIS series. Verified by exhaustive filename search.

Consequences:

1. Carry return is `spot return + interest differential`. With spot only, the interest
   component — the dominant term in carry P&L — is **omitted entirely**.
2. Menkhoff et al.'s ranking signal is the **forward discount / interest differential**.
   Your §3.3 substitutes **trailing 12-month spot return** and labels it "Momentum /
   Yield Ranking Metric". These are different factors, empirically separable.
3. The direction of the bias is adverse. High-yield currencies tend to *depreciate* in
   spot — the forward premium puzzle is precisely what carry monetises. A spot-only
   backtest is therefore biased **against** carry, while actually measuring
   cross-sectional FX momentum: a weaker, more contested effect.
4. Your stated economic driver — "harvest persistent yield" — is **untestable** with
   this data.

**Question A. Defend one:**

* **(A1)** The specification should be renamed and re-motivated as vol-conditioned
  cross-sectional FX *momentum*, with Menkhoff demoted from replication to motivation.
* **(A2)** Spot-only is an acceptable proxy for carry. **If you argue this, you must
  quantify the proxy error**: cite the empirical correlation between 12-month spot
  momentum rank and forward-discount rank in G10, with source, and state what fraction
  of carry P&L the omitted accrual represents.
* **(A3)** Rate data must be sourced first. **If you argue this, name the exact series**
  — publisher, series identifier, frequency, history, licence, and how it aligns to a
  22:00 UTC daily bar — sufficient for someone to fetch it without further research.

## 3. Finding B — Gate 2 is not a test. It passes on pure noise.

Your Gate 2: `Sharpe(Conditioned) > Sharpe(Control A)` **AND**
`MaxDD(Conditioned) < MaxDD(Control A)`.

The regime filter leaves the portfolio **flat in 71 of 160 months (44.4%)**. Measured:
mean sigma_FX is 0.0776 on calm months against 0.0964 on stressed months.

A Monte Carlo was run with **zero-edge returns bearing no relationship whatsoever to the
calm mask**, 4,000 draws, using the real mask:

```
iid noise          P(Sharpe higher)=0.504  P(MaxDD lower)=0.828  P(GATE 2 PASSES)=0.485
vol-matched noise  P(Sharpe higher)=0.495  P(MaxDD lower)=0.860  P(GATE 2 PASSES)=0.484
```

**Gate 2 passes 48.5% of the time on data containing no information at all.** Being flat
44% of the time lowers max drawdown mechanically — you cannot draw down while in cash —
and the Sharpe leg is a coin flip. Both legs measure reduced exposure, not skill.

**Question B.** Either show this simulation is wrong — identify the specific defect —
or supply a replacement Gate 2 that is not passable by a random number generator. Any
replacement must state its own null pass-rate. The proposed alternative is a Welch test
on the *unconditioned* basket's returns split calm vs stressed, plus a vol-matched
Sharpe comparison equalising ex-post exposure; improve on it or adopt it.

## 4. Finding C — the effective sample is far smaller than 156

```
months in sample          160
months actually invested   89     (conditioner flat 44.4% of the time)
participation-ratio N_eff  2.89 of 7 pairs   (top PC explains 54.8% of variance)
AUD/NZD correlation        0.82
```

"Top 2 by momentum" will frequently select AUD and NZD together — one economic bet held
twice. Additionally, Gate 1's bar of Sharpe > 0.60 over 13.3 years corresponds to
**t = 2.02**, with a 95% confidence interval of **[+0.02, +1.18]**. A result landing at
0.61 is statistically indistinguishable from zero.

**Question C.** Given N_eff = 2.89 and 89 invested months, state the minimum effect size
this design can detect at t >= 2.00, and whether the K=2 basket should change. If you
retain K=2, justify it against the AUD/NZD collinearity.

## 5. Minor defects to confirm or correct

1. Gate 4 specifies "≥4 of 5 chronological sub-windows" but §5 lists **four** windows.
2. The emergency flatten rule (`sigma > 2.0 x baseline`) is logically **subsumed** by
   `I_calm` at every rebalance, since `sigma > 2*baseline` implies `sigma > baseline`.
   It can only bind intra-month. State how often it fires independently, or drop it.

## 6. Rules of engagement

These exist because of specific, documented incidents in this programme.

1. **No claim about this repository's state without quoting the file and line.** A prior
   submission asserted `institutional_vwap` was VALIDATED at "+1.8 to +4.2 bp on
   QQQ/SPY/XAU". It is `CANDIDATE`, annotated *"NOT BACKTESTED in this project"*, with
   `clustered_t: None, n: None`. That was fabrication, and it was caught.
2. **Every empirical claim states N, the control, and the de-overlapping treatment.** A
   prior submission reported t-statistics of -3.12 and -3.40 as "statistically
   significant"; they were an artefact of 16-bar overlap and collapsed to -0.67 and
   -1.43 on non-overlapping subsamples.
3. **Every conditional claim states its unconditional baseline.** A prior submission
   reported D1-EMA-filtered returns of +0.21 bp (eurusd) and -0.69 bp (xauusd) as
   positive findings. The *unconditional* 4-hour drift on those instruments is +0.44 and
   +0.58 bp: the filter underperformed doing nothing on 5 of 6 instruments.
4. **Do not propose passive execution as a remedy for a strategy with non-positive gross
   expectancy.** `TOLL_BREAKEVEN_01` §3 bounds passive saving at `toll/4.3` and requires
   `edge/toll >= 0.767`.
5. **If a number is estimated rather than measured, label it.** The auditor's own harness
   was found to carry three invented tolls (eurjpy 4.50, xagusd 9.00, wti 6.00) labelled
   as measured; that defect is now disclosed in the registry. The same standard applies
   in both directions.

## 7. Required output format

1. **Position on A** — A1, A2 or A3, with the evidence each demands above.
2. **Position on B** — defect identified in the simulation, or a replacement gate with
   its null pass-rate.
3. **Position on C** — minimum detectable effect, and K.
4. **Corrections** to the two minor defects.
5. **A revised §3-§4 specification block** in full, ready to be sealed, or an explicit
   withdrawal of the pathway.

Concede points that are correct without hedging, and contest points that are wrong with
evidence. A reply that accepts everything is as useless as one that accepts nothing.
