# Pre-Registration — WEINSTEIN_STAGE_01

**Written**: 2026-09-12, BEFORE any strategy return, Sharpe ratio, or drawdown was computed for acceptance.
**Type**: Long-horizon equity trend/cycle regime filter. Daily panel (`spy_daily`).
**Origin**: Candidate 3 from `@chart-fanatics` (Ted Zhang & Clement Ang) — Stan Weinstein 4-Stage Market Cycle.
**Discovery Scope**: 1993-01-29 to 2023-12-29 (7,786 daily sessions).
**Holdout Status**: 2024-01-02 to 2026-09-04 (672 sessions) is STRICTLY SEALED.

---

## 1. The Claim Under Test

> A 30-week (150-day) simple moving average paired with a 2-week (10-day) positive slope persistence isolates Stage 2 (Markup) from Stages 1 (Accumulation), 3 (Distribution), and 4 (Decline). Allocating 100% to SPY during Stage 2 and stepping aside into 100% cash during non-Stage 2 regimes avoids catastrophic bear-market drawdowns without surrendering the long-term equity risk premium, even after accounting for asymmetric cash drag, transaction tolls, and multi-month overnight financing.

The distinctive claim is that market timing on a 30-week moving average provides **drawdown truncation that outweighs the foregone equity drift and cash drag** incurred while sitting out 35% of the time.

---

## 2. The Mandatory Control Architecture: Buy-and-Hold Symmetrically Financed

A long-only equity market-timing model cannot be tested against zero. A naive strategy that buys and holds SPY over 1993–2023 earns ~8.01%/year gross simply by existing. Testing against zero would mistake unconditional market beta for timing alpha.

### The Primary Control: SPY Buy-and-Hold
Every metric evaluated for Weinstein Stage Analysis must be benchmarked directly against Buy-and-Hold SPY evaluated on the identical session window:
1. **Gross Equity Return**: Weinstein sits in cash ~34.7% of the time. During equity bull markets, cash drag directly surrenders gross points.
2. **Drawdown Avoidance**: The sole justification for sitting in cash is avoiding severe drawdowns (-50% in 2000–2002, -55% in 2007–2009). The reduction in Maximum Drawdown must exceed the foregone gross return on a risk-adjusted basis.

### Dual Venue Financing Tolls (Enforced Symmetrically)
Multi-month holds make spread toll secondary, while financing drag becomes the governing cost barrier:
- **Round-Trip Turnover Toll**:
  - Modelled SP500 toll: 0.80 bp raw spread $\times$ 4.3 slippage multiplier + commission $\approx$ 4.09 bp per round trip.
  - Across 30.9 years, 229 regime flips = 3.7 RT/year $\approx$ 15.1 bp/year ($0.151\%$/year).
- **Venue A: Retail CFD Financing (MT5 / Broker)**:
  - Benchmark rate: $\text{SOFR} + 2.5\%$ broker markup $\approx 7.80\%$/year.
  - With dividend adjustment credit ($\approx 1.50\%$ yield): net financing drag $\approx 6.30\%$/year.
  - Applied symmetrically: Buy-and-Hold pays 365 days/year ($6.30\%$/year). Weinstein pays only while invested ($65.3\% \times 6.30\% \approx 4.11\%$/year).
- **Venue B: CME Futures Basis Decay (ES / MES)**:
  - Basis decay: $(r - q) \approx 3.80\%$/year (SOFR minus dividend yield, zero broker financing markup).
  - Commission: CME Micro E-mini \$1.04 RT $\approx 0.20$ bp.
  - Applied symmetrically: Buy-and-Hold pays $3.80\%$/year. Weinstein pays $65.3\% \times 3.80\% \approx 2.48\%$/year.
- **Venue C: Cash Equity (Unlevered ETF / 401k / IRA)**:
  - Long positions pay $0.0\%$ financing.
  - Cash earns the risk-free rate (SOFR) while uninvested: $34.7\% \times r_f$.

---

## 3. Frozen Specification — ONE Variant, Zero Sweeps

```
timeframe        Daily (spy_daily)
SMA_N            150 days (30 trading weeks * 5 days)
SLOPE_LAG        10 days (2 trading weeks)
STAGE 2 (LONG)   close[t] > SMA150[t]  AND  SMA150[t] > SMA150[t - 10]
EXIT (CASH)      close[t] <= SMA150[t] OR   SMA150[t] <= SMA150[t - 10]
ENTRY EXECUTION  open[t + 1], market
EXIT EXECUTION   open[t + 1], market
POSITION         1.0 (Long) or 0.0 (Cash) — Zero shorting
TOLL             4.09 bp per round trip
FINANCING_CFD    7.80% annual (gross) / 6.30% annual (net of dividend)
FINANCING_FUT    3.80% annual basis decay
```

**Zero parameter sweeps.** The 150-day window and 10-day slope lookback are frozen here. If the strategy fails the pre-registered gates, the verdict is **FAILED** — not "tune to 140 days or 200 days."

---

## 4. Pre-Registered Gates

* **Gate 1 — Risk-Adjusted Alpha Over Buy-and-Hold**:
  Weinstein Sharpe ratio must exceed Buy-and-Hold Sharpe ratio by at least $+0.10$ under both Venue A (CFD) and Venue B (Futures) net financing models.
* **Gate 2 — Drawdown Truncation**:
  Maximum peak-to-trough drawdown of Weinstein must be less than $60\%$ of Buy-and-Hold Max Drawdown:
  $$\text{MaxDD}_{\text{Weinstein}} \le 0.60 \times \text{MaxDD}_{\text{B\&H}}$$
  And MAR ratio ($\text{CAGR} / |\text{MaxDD}|$) must exceed Buy-and-Hold MAR by at least $1.25\times$.
* **Gate 3 — Temporal Stability Across Regimes**:
  Weinstein Sharpe must meet or exceed Buy-and-Hold Sharpe in at least 2 of 3 chronological sub-eras:
  - Era 1 (Pre-GFC): 1993-01-29 to 2007-12-31
  - Era 2 (ZIRP / QE): 2008-01-01 to 2021-12-31
  - Era 3 (Rate Shock / QT): 2022-01-01 to 2023-12-29
* **Gate 4 — Net Economic Viability**:
  Net terminal wealth after all financing and turnover tolls must strictly exceed initial capital on both venues ($\text{CAGR}_{\text{net}} > 0$).

---

## 5. Causality and Lookahead Declaration

| Variable | Inputs Used | Causal at Decision Time |
| :--- | :--- | :--- |
| `SMA150[t]` | `close[t-149..t]` | Yes |
| `Slope[t]` | `SMA150[t]`, `SMA150[t-10]` | Yes |
| `Stage2[t]` | `close[t]`, `SMA150[t]`, `Slope[t]` | Yes — evaluated at close of session `t` |
| `Trade Execution` | `open[t+1]` | Yes — executes at market open of session `t+1` |

`assert_causal()` verifies that signal generation on truncated history prefixes produces identical outputs across all evaluated cuts.

---

## 6. Honest Prior

Market timing via a single moving average typically avoids prolonged structural bear markets (2000–2002, 2008) at the expense of whipsaws during choppy sideways markets (e.g. 1994, 2011, 2015).
Because SPY exhibits strong positive drift, sitting in cash 35% of the time means gross CAGR will almost certainly trail Buy-and-Hold. The question is whether drawdown avoidance and financing savings (sitting in cash avoids CFD/Futures carry cost) provide enough of an edge to elevate the Sharpe and MAR ratios past Gates 1 and 2.
