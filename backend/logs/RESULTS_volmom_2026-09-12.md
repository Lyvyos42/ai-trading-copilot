# RESULTS — VOLMOM_01

**Prereg**: `prereg/VOLMOM_01.md`, sha `7e7468eafae22ec6`, sealed before any portfolio
return was computed.
**Harness**: `_volmom.py`
**Run**: 2026-09-12, discovery only (`ts < 2024-01-01`), 3,443 daily bars from H1,
7 G10 pairs, 145 non-overlapping 22-day rebalances.
**Holdout**: NOT READ. All four gates failed; the branch is unreachable.

---

## 1. Verdict — all four gates FAIL

| gate | requirement | measured | |
| :--- | :--- | ---: | :--- |
| 1 economic | net > 0, `t >= 2.00` | net **-12.28 bp/mo**, `t` **-1.08** | FAIL |
| 2 conditioner earns place | calm > stress, Welch `>= 2.00` | **-0.59**, wrong sign | FAIL |
| 3 beats random selection | Welch `>= 2.00` | **-0.36** | FAIL |
| 4 temporal stability | net > 0 in >= 3 of 4 | **2 of 4** | FAIL |

Causality assertion PASSED — weights rebuilt on truncated prefixes at three cut
points are identical.

## 2. An alignment bug was found and fixed, and it reversed Gate 2

`returns()` indexes each monthly observation by its **end** date. The first version of
the Gate 2 partition split Control A's returns using `calm` reindexed onto that end
date — classifying every month by a regime observed *after* the position was entered.

```
before fix (lookahead) : calm -5.36 bp  stress -12.84 bp  Welch +0.23   calm BETTER
after  fix (corrected) : calm -17.56 bp stress  +1.99 bp  Welch -0.59   calm WORSE
```

**The apparent support for the volatility conditioner was entirely an artefact of that
misalignment.** This is the same error class that took the DAX overnight proposal from
t -1.06 to +5.54. It was caught because the conditioned portfolio's invested-month
return (-19.08 bp) could not be reconciled with the partition's calm-month return
(-5.36 bp) when both should describe the same months.

The strategy's own weights were never affected — `weights()` reads `calm` at the
decision date throughout, and `assert_causal()` passed both before and after.

## 3. The conditioner destroys value, and not through turnover

```
conditioned   NET  -12.28 bp/mo   t -1.08   Sharpe -0.312
uncond (A)    NET   -8.74 bp/mo   t -0.54   Sharpe -0.156
conditioned  GROSS  -7.26 bp/mo   t -0.64
uncond (A)   GROSS  -4.25 bp/mo   t -0.26
```

Conditioning makes the portfolio **worse on both gross and net**. The obvious
explanation — that going flat and re-entering burns toll — is wrong:

```
toll, conditioned   +5.02 bp/mo      leg changes 353
toll, unconditioned +4.49 bp/mo      leg changes 301
extra cost of regime switching  +0.54 bp/mo
```

Only 0.54 bp/month of the 3.54 bp/month gap is turnover. **The conditioner is
selecting the wrong months**, consistent with the corrected Gate 2 sign.

## 4. Control B is valid, and the strategy loses to it

```
Control B NET    n=14,400  mean -8.12 bp   NOT centred (pays toll)
Control B GROSS  n=14,400  mean -0.65 bp   t -0.54  -> CENTRED, valid
strategy GROSS -7.26 bp  vs  ctrlB GROSS -0.65 bp   Welch -0.58
```

As in `SQUEEZE_EXPANSION_01`, the centring check must be performed on **gross**: a net
control pays toll and structurally cannot centre at zero. On gross the control is
properly centred, and the strategy underperforms random selection — nominally, not
significantly.

## 5. Power, restated from realised rather than assumed volatility

Prereg §5 required this restatement:

```
assumed basket volatility   8.00% annualised   -> MDE 48.9 bp/month
realised (unconditioned)    6.71% annualised   -> MDE 41.4 bp/month at t=2.00, n=79
```

The assumption was conservative; the true detection floor is lower. It does not help —
the measured effect is **-12.28 bp/month**, the wrong side of zero.

## 6. Sub-windows

```
2010-09 .. 2014-01   n=27    +836.8 bp
2014-01 .. 2017-05   n=39   -1244.8 bp
2017-05 .. 2020-09   n=39   -1689.5 bp
2020-09 .. 2023-12   n=39    +328.6 bp
```

2 of 4 positive, with swings of ±1,700 bp. At 144 monthly observations and N_eff 2.89,
this is the expected appearance of a series with no edge.

## 7. Discrepancy against the pre-registration, disclosed

Prereg §2 states "160 months". The harness produces **145 rebalances / 144 monthly
returns**. The 160 figure came from a calendar month-end resample used in the design
diagnostics; the frozen specification rebalances every **22 trading days** after a
253-day warmup, giving `(3443 - 253) / 22 = 145`.

The prereg's derived quantities inherit this: 89 calm months becomes **79 invested**,
and the MDE denominator is `sqrt(79)` rather than `sqrt(89)`. Restated MDE 41.4
bp/month. **No gate outcome changes** — Gate 1 is at t -1.08 and Gate 2 has the wrong
sign — but the prereg's N was optimistic by ~10% and that is recorded rather than
quietly reconciled.

## 8. What this does and does not establish

**Established.** Volatility-conditioned cross-sectional momentum on 7 G10 USD pairs,
with the frozen specification, is not profitable on 2010-2023 discovery data; it loses
to random selection; and the volatility conditioner has the wrong sign once correctly
aligned.

**Not established.** That FX momentum is dead generally. This universe is 7 pairs with
`N_eff = 2.89`; Menkhoff et al. (2012, *JFE* 106(3)) use a far broader cross-section
where a K=2 basket is a much smaller fraction of the universe. A 7-pair G10 test is a
weak instrument for a cross-sectional factor, and that limitation was stated in prereg
§7 before the run.

**Nothing is concluded about carry**, which was never testable here — there is no rate
data in the repository. See prereg §1.

**No parameter will now be swept.** K=2, the 252-day lookback, the 22-day vol window,
the 60-day baseline and the cluster structure are frozen in prereg §3.
