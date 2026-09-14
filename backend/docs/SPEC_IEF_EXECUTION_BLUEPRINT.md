# InstitutionalEdgeFutures (IEF) — Live Execution Blueprint

**Date**: 2026-09-12
**Strategy**: `cme_rebal_flow` / `CME_REBAL_FLOW_01`, prereg sha `b6a8143b2e3fcf5a`
**Evidence status**: **CANDIDATE**, not VALIDATED. Arms as EXPERIMENT only, and every surface must say so.
**Venue**: CME Globex, Micro E-mini equity index futures
**Reference implementation**: `ief/calendar_daemon.py`

---

## 0. Deployment Preconditions — three resolved, one blocker remains

The three items flagged on 2026-09-12 are resolved below. One blocker remains and it is not an engineering question.

### RESOLVED 1 — Settlement window and exit routing

**Operator-attested, 2026-09-12.** Trade-at-Settlement is **not listed** on CME Micro equity index contracts (MES, MYM, M2K). The equity index daily settlement window is **15:59:30 to 16:00:00 ET**, a 30-second VWAP ending at the cash close.

**Exit routing**: session $T$ is flattened by a **30-second time-sliced execution beginning at 15:59:30 ET**, participating in the same window the settlement VWAP is computed from. This is the closest achievable approximation to the backtest's settlement-price exit given that TAS is unavailable.

**Provenance**: these two facts are **operator-attested, not independently verified by this desk.** `cmegroup.com` was unreachable on four attempts across two sessions (ECONNRESET, timeout). They are recorded as attested rather than sourced, which is weaker standing than the H.15 publication time in `REAL_YIELD_GOLD_01`, which was fetched and quoted directly. Re-verify against CME's published daily settlement procedure at the first opportunity.

**Residual tracking error**: a time slice across the VWAP window does not reproduce the VWAP exactly. Even participation across 30 seconds gives an expected fill near the window VWAP with a variance scaling in intra-window volatility. `logs/ief_rebal_execution.log` records the exit fill against the official settlement print so this residual is measured rather than assumed. It is the single most important number in the first three months of paper trading.

### RESOLVED 2 — Dual-tier sizing, with a toll-band governor that overrides the cap

Tiers are implemented in `ief/sizing.py`:

| Equity | Mode | Instruments |
| :--- | :--- | :--- |
| < $190,000 | `SINGLE_MES` | MES only. The panel divisor $1/N$ is removed, so weights are 3x the panel values |
| >= $190,000 | `PANEL_3` | MES, MYM, M2K under a declared 4.0x peak-notional cap |

**A 4.0x cap at $190,000 puts every leg outside the measured cost band. The tier boundary alone does not fix it.** At mean target weights:

| Contract | Contracts at $190k, 4.0x | Status |
| :--- | ---: | :--- |
| MES | 5.12 | outside the 1-5 band |
| MYM | **6.71** | outside the 1-5 band |
| M2K | 5.85 | outside the 1-5 band |

Phase 4 measured $M = 1.0829$ at 1-5 contracts and $M = 1.5235$ at 6-20, a **41% toll increase**. Every number in the strategy's record was produced inside the 1-5 band.

`ief/sizing.py` therefore enforces a **toll-band governor**:

$$k_{\text{eff}} = \min\left(\text{LEVERAGE CAP},\ \min_i \frac{5 \cdot \text{notional}_i}{|w_i| \cdot E}\right)$$

| Equity | $k_{\text{eff}}$ at mean weights | Binding constraint |
| ---: | ---: | :--- |
| $150,000 | 3.78x | toll band |
| $190,000 | **2.98x** | toll band |
| $250,000 | 2.27x | toll band |
| $400,000 | 1.42x | toll band |
| $566,000 | 1.00x | toll band |
| $750,000 | 0.76x | **unlevered already breaches the band** |

The multiple is also month-dependent, because weights scale with $|z|$. The December 2023 dry run carries $|z|$ between 1.66 and 2.13, well above average, and the governor reduces 4.0x to **1.86x**.

**This has a gate consequence and it is stated rather than buried.** Gate 3B's volatility-matched CAGR claim holds only at a cap of 4.0x or above; at 3.0x it fails by 1.065pp of CAGR. **A governed deployment running at 1.9x to 3.0x does not carry Gate 3B's matched-CAGR result.** What it does carry is Gate 3A, Sharpe dominance, and Gate 3C, the sign-permutation null, both scale-invariant and both unaffected by the governor.

**Panel-mode ceiling**: above roughly **$566,000** even an unlevered panel breaches the 5-lot band, with MYM binding. Beyond that, either slice orders within the window or re-measure the cost model at the 6-20 band. Contract counts must never drift out of the band silently, which is what the governor exists to prevent.

**Quantisation floor**: at 4.0x, three contracts on every leg needs $111,332; unlevered it needs $445,327. Below the floor, rounding error exceeds the 30 bp signal. The dry run at $190,000 shows a −5.0% quantisation error on the MES leg at 3 contracts.

### RESOLVED 3 — Entry timing and estimator identity, unchanged

- Formation at **16:15 ET on session $T-5$**, after settlement, so the formation close is final. Strictly better than the provisional-at-15:50 scheme it replaces, and no lookahead.
- Sizing at **09:25 ET on session $T-4$**.
- Entry at the **09:30 ET open of session $T-4$**, the pre-registered entry and the source of every measured number.
- Exit as RESOLVED 1.
- Volatility estimator is the **60-session standard deviation of daily log closes**, hard-coded in `ief.sizing.trailing_vol_annualised`. ATR is not used: it is a different estimator and was not what produced the record.

### RESOLVED 4 — Calendar extended through 2030, and an ad-hoc closure defect fixed

`ief/data/exchange_holidays.csv` covers **1993-01-01 to 2030-12-25**: 350 full holidays and 81 early closes, 421 rule-derived and 10 ad-hoc.

Generated by `ief/holiday_rules.py` from published rules, then **validated against the historical record: 298 of 298 known holidays reproduced, zero missing.** The three apparent extras lie outside the reference file's coverage.

**A real defect was found and fixed.** Unscheduled NYSE closures are not rule-derivable and were absent from the original reference file, so the session grid counted them as trading days. Of five historical episodes, one shifts a month grid:

| Episode | Grid effect |
| :--- | :--- |
| 9/11, 2001-09-11 to 14 | none; closures fall outside the final-5 window |
| Reagan funeral, 2004-06-11 | none |
| Ford funeral, 2007-01-02 | none |
| **Hurricane Sandy, 2012-10-29/30** | **formation and entry both shift 2 sessions earlier** |
| Bush funeral, 2018-12-05 | none |

October 2012's evaluated event therefore used a formation date two sessions late and held two sessions instead of four. That is 1 of 371 months, immaterial to the measured result and a genuine defect for a live daemon. All ten closures are now in the schedule, and `CalendarDaemon.confirm_open()` must be called immediately before every transmission so an unscheduled closure discovered after planning cannot become an order into a shut market.

**Dates from 2027 onward are RULE-DERIVED and not operator-verified.** They must be reconciled against CME Group's published holiday calendar before go-live. `HolidayHorizonError` fires on any month within 60 days of the schedule end.

### REMAINING BLOCKER — evidence status

`can_arm()` must return **EXPERIMENT**. `cme_rebal_flow` is **CANDIDATE**: measured edge +30.06 bp, 95% CI [+1.89, +58.23], Gates 1, 2, 3A, 3B, 3C and Control C pass, Gate 4 fails on one era whose own interval spans [−76, +59] bp. No surface may show a profit figure without the CANDIDATE label.

---

## 0b. Verification Status of This Blueprint

| Component | Status |
| :--- | :--- |
| Calendar grid vs evaluated backtest | **371 months cross-checked, 0 unexpected mismatches** |
| Holiday rule engine vs historical record | **298 of 298 reproduced** |
| Horizon assertion beyond schedule end | fires correctly |
| Toll-band governor at the $190k boundary | binds, reduces 4.0x to 2.98x |
| Single-instrument mode below $190k | selects MES only, warns on lost averaging |
| Volatility estimator identity | 60-session log-close sd, exactly 61 closes consumed |
| End-to-end dry run, entry through exit | flattens, audit reconciles |
| Holdout reads | **0**, asserted in the test suite |

Suite: `tests/test_rebal_daemon_dryrun.py`, **9 of 9 passing**. The paper adapter defaults to fills at the touch, reproducing the Phase 4 median of $M = 1.0$; the dry run returns mean $M_{\text{realised}} = 1.0000$ against the measured 1.0829.

## 1. Contract Mapping

| Panel series | Contract | Multiplier | Tick | Tick value | Round-trip toll | Toll source |
| :--- | :--- | ---: | ---: | ---: | ---: | :--- |
| `es_daily` | **MES** | $5 / index pt | 0.25 | $1.25 | **1.018 bp** | Phase 4 measured, $M$ = 1.0829 at 1-5 lots |
| `ym_daily` | **MYM** | $0.50 / index pt | 1.00 | $0.50 | **0.906 bp** | Phase 4 measured |
| `rty_daily` | **M2K** | $5 / index pt | 0.10 | $0.50 | **1.665 bp** | Phase 4 measured |

**Slippage multiplier.** $M = 1.04$ at 1 contract, $M = 1.0829$ at 2-5, rising to 1.5235 at 6-20 and 3.7230 at 21-100. The backtest used the 1-5 band. **Any deployment whose order size exceeds 5 contracts per leg is trading outside the cost model that produced the result**, and at 21-100 contracts the toll multiplies by 3.4x. At $750,000 equity the mean MES order is 5.05 contracts, which sits exactly at the boundary. Orders must be sliced to stay within the measured band, or the toll re-measured.

**Unmeasured roots.** Phase 4 measured $M$ on GC and CL only. ES, YM and RTY multipliers are the conservative default, and no micro contract was measured directly — micros trade a thinner book than the full-size contract. This is an assumption carried into live trading and is tagged as such.

**Exit leg penalty.** The backtest charged 1.5x the round-trip toll to account for the market-on-close exit filling at settlement rather than at the touch. If TAS is used per BLOCKING 1, the realized penalty should be re-measured against that 1.5x assumption in the first three months of live fills.

---

## 2. Order Timing and Execution

All times New York. The session grid comes from the published exchange holiday calendar, never from a realized row count.

| Step | When | Action |
| :--- | :--- | :--- |
| **Formation** | 15:50 ET on session $T-5$ | Compute $S_m = \ln(C_{T-5} / C_{0})$ where $C_0$ is the prior month's final close. Compute $\sigma_m$ from the 60 sessions ending $T-6$. Derive $z_m$, then target weights. |
| **Freeze** | 16:00 ET on session $T-5$ | Persist the weight vector to disk with the formation inputs and a hash. No recomputation afterwards. |
| **Entry** | Open of session $T-4$ | Market order at the open. This is the pre-registered entry and it is NOT 15:58 ET. |
| **Hold** | $T-4$ through $T$ | Four sessions. No stop, no target, no intraday intervention. |
| **Exit** | Settlement of session $T$ | Flatten to cash via TAS, or market-on-close if TAS is unavailable, subject to BLOCKING 1. |

### A correction to the directive's timing

The directive specifies order entry at **15:58 ET on session $T-4$**. The pre-registered specification enters at the **open of session $T-4$**, and that is what produced every measured number in the record.

Entering at 15:58 ET on $T-4$ would discard the entire $T-4$ session return, reducing the holding period from four sessions to three. That is a **different strategy** with a different expected edge, and it has not been measured. The formation signal is complete at the close of $T-5$, so the earliest causal entry is the open of $T-4$, and taking it is what the evidence supports.

If a same-day-close entry is wanted for operational reasons, it requires its own pre-registration and its own evaluation. It must not be substituted silently into a module whose registry entry cites open-of-$T-4$ figures.

### Formation timing

15:50 ET on $T-5$ is 10 minutes before the cash close, so the formation close $C_{T-5}$ is not yet final. Two options, and the choice must be recorded:

1. **Provisional at 15:50, confirmed at 16:00.** Compute at 15:50 for operational readiness, recompute on the settled close, and use the confirmed vector. Adds no lookahead and is the recommended path.
2. **Formation on the $T-6$ close.** Fully settled, but shifts the signal one session earlier and changes the specification.

Option 1 preserves the specification. Option 2 does not.

---

## 3. Capital Allocation and Sizing

### Pre-registered sizing, which is what was measured

$$w_{i,m} = -\frac{\operatorname{clip}(z_{i,m},-2,+2)}{2}\cdot\frac{1}{N_m}\cdot\frac{\sigma_{\text{tgt}}}{\sigma_{i,m}\sqrt{252}},\qquad \sigma_{\text{tgt}}=0.10$$

with $\sigma_{i,m}$ the 60-session standard deviation of daily log closes and gross leverage capped at 3.0 across the panel.

Contracts: $\ n_{i} = \operatorname{round}\!\big(w_{i,m}\cdot E \,/\, (P_i \cdot \text{multiplier}_i)\big)$, floored at 0 and capped at 5 per leg to stay inside the measured toll band.

### On the directive's ATR proposal

The directive proposes sizing from a rolling 20-day ATR. **ATR was not the estimator used in the measured result**, and substituting it changes the position series. Worked example at $100,000 equity and 25 bp of equity risked per 1 ATR:

| Contract | Price | ATR20 | ATR in $ | Contracts | Integer |
| :--- | ---: | ---: | ---: | ---: | ---: |
| MES | 4,366.20 | 40.45 pts | $202.24 | 1.24 | 1 |
| MYM | 34,807.85 | 280.34 pts | $140.17 | 1.78 | 2 |
| M2K | 1,873.86 | 35.26 pts | $176.28 | 1.42 | 1 |

ATR and the 60-day close-to-close standard deviation are both volatility estimators and will usually agree to within a modest factor, but they are not identical: ATR includes gap and intraday range information that a close-to-close estimator excludes, and it responds faster.

**Recommendation**: deploy the pre-registered 60-session close-to-close estimator so live results are comparable to the measured record, and log the ATR-implied size in parallel. If the two diverge materially over six months, that is a finding worth a pre-registration, not a silent substitution.

### Volatility-matched variant

If the Gate 3B matched variant is deployed, `LEVERAGE_CAP` must be declared and enforced. Required multiple is $k = 8.95$ uncapped, giving **peak gross notional of 14.34x equity** against a mean of 2.70x. At micro initial margin of roughly 5 to 10% of notional, 14x consumes 70 to 140% of equity and is not deployable. **Cap at 4.0x**, which is the lowest cap at which Gate 3B passes, with a measured margin of +0.24pp of CAGR over buy-and-hold.

---

## 4. Calendar Daemon

Reference implementation in `ief/calendar_daemon.py`. It builds the forward session grid from the published holiday file and emits the four reference dates per month. It never counts realized data rows.

Contract:

```python
from ief.calendar_daemon import CalendarDaemon
d = CalendarDaemon("app/data/nyse_holidays.csv")
plan = d.month_plan("2026-10")
# MonthPlan(month='2026-10', K=22, prior_close='2026-09-30',
#           formation='2026-10-26', entry='2026-10-27', exit='2026-10-30')
d.action_for("2026-10-26")   # -> 'FORMATION'
d.action_for("2026-10-27")   # -> 'ENTRY'
d.action_for("2026-10-30")   # -> 'EXIT'
d.action_for("2026-10-15")   # -> None
```

Hard requirements, all enforced in the module:

1. **No realized-count lookahead.** The grid is derived only from weekday rules minus the published holiday list.
2. **Horizon assertion.** The holiday file must cover at least 60 days beyond any month being planned, or the daemon raises. The file currently ends 2026-09-07, so **it must be extended before it can plan any month beyond July 2026.**
3. **Explained-mismatch tolerance.** CME Globex carries about 100 holiday trade dates the NYSE calendar lacks. Reference dates come from the NYSE grid because the mandated flow is benchmarked to cash month-end NAV; prices are read on those dates. A month is skipped only when a required date is absent from the price feed.
4. **Idempotence.** Re-running on the same session must not re-enter. State is keyed on `(month, step)` and persisted.
5. **Early-close handling.** The published file carries a `pre_holiday_date` column. Half sessions are valid sessions for grid purposes but the settlement time moves, which matters for the exit leg.

---

## 5. Risk Controls and Instrumentation

| Control | Setting | Rationale |
| :--- | :--- | :--- |
| Max contracts per leg | 5 | Beyond this the toll leaves the measured 1-5 band |
| Max gross leverage | 3.0 unlevered, 4.0 matched | Pre-registered, and the Gate 3B cap |
| Position lifetime | Hard flatten at session $T$ settlement | Carrying past month-end is outside the specification |
| Intra-window intervention | None | No stop, no target. The measured drawdown of −3.96% is the unmanaged figure |
| Kill switch | Flatten and disarm on any daemon exception | A partial fill across a 3-leg panel is worse than no position |
| Fill audit | Log intended vs realized price per leg | Validates the 1.018 bp toll and the 1.5x exit penalty against reality |
| Financing audit | Log the point-in-time rate per event | Carry is 71% of modelled cost and must not go unmeasured |

### Forward validation horizon

At roughly 12 events a year and a measured net Sharpe of 0.642, the identity $t = \text{Sharpe}\sqrt{T}$ gives a live $t$ of 2.00 after $T = (2.00/0.642)^2 \approx 9.7$ years. **Live trading is an execution test, not a validation test.** What it validates within a reasonable horizon is the toll model, the settlement assumption and the daemon, not the edge.

---

## 6. Deployment Sequence

1. Re-verify the settlement window and TAS availability against CME's published procedure. It is currently operator-attested, not sourced.
2. Set equity against the governor table. Panel mode is valid from about $111,000 to $566,000; below $190,000 the daemon selects single-instrument MES; above $566,000 the 5-lot band breaks and the cost model must be re-measured.
3. Reconcile the 2027-2030 rule-derived holidays against CME's published calendar.
4. Run the daemon in dry-run for two full months, diffing its reference dates against the backtest's month plan. Zero mismatches required.
5. Paper trade for three months with full fill audit. Compare realized toll to 1.018 bp and realized exit slippage to the 1.5x assumption.
6. Arm on demo as EXPERIMENT with the CANDIDATE label on every surface.
7. Live only at minimum equity, single instrument if below it, with the fill and financing audits running.

**Do not skip step 5.** The programme's own record contains a module that ran live for months on an unvalidated edge while displaying a profit figure, which is the reason `core/evidence.py` exists.
