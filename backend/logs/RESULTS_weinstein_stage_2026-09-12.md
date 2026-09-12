# RESULTS — WEINSTEIN_STAGE_01

**Prereg**: `prereg/WEINSTEIN_STAGE_01.md`, sha `493f9a30732cac89`, sealed before any return or Sharpe ratio was computed.
**Harness**: `_weinstein_stage.py`
**Run**: 2026-09-12, discovery only (`ts < 2024-01-01`), 7,786 SPY daily sessions (1993-01-29 to 2023-12-29).
**Holdout**: NOT READ. Gates 1 and 3 failed; prereg section 4 mechanically blocks holdout execution.

---

## 1. Verdict — FAILED (Gates 1 & 3 FAIL, Gates 2 & 4 PASS)

| Gate | Requirement | Measured | Verdict |
| :--- | :--- | :--- | :--- |
| **Gate 1: Alpha over B&H** | $\Delta\text{Sharpe} \ge +0.10$ on Fut & CFD | Fut: **-0.01**, CFD: **-0.03** | **FAIL** |
| **Gate 2: Drawdown Truncation** | $\text{MaxDD} \le 0.60\times\text{B\&H}$, $\text{MAR} \ge 1.25\times$ | DD Ratio: **0.46x**, MAR Ratio: **1.44x** | **PASS** |
| **Gate 3: Temporal Stability** | $\text{Sharpe}_{\text{W}} \ge \text{Sharpe}_{\text{BH}}$ in $\ge 2/3$ Eras | **1 of 3** sub-eras passed | **FAIL** |
| **Gate 4: Net Viability** | $\text{CAGR}_{\text{net}} > 0$ on Fut & CFD | Fut: **+2.65%**, CFD: **+0.96%** | **PASS** |

Causality assertion PASSED on `spy_daily` across four truncation cuts.

---

## 2. The Core Arithmetic: Drawdown Truncation is Not Free Alpha

The hypothesis of Stan Weinstein Stage 2 filtering is that stepping aside into cash avoids catastrophic drawdowns without sacrificing long-term returns. The empirical backtest over 30.3 years (7,625 evaluated sessions) separates fact from marketing:

```
Time in Market:       66.6% (33.4% spent in cash)
Regime Flips:         228 transitions = 114 round trips (3.77 RT/year)
Annual Turnover Toll: 15.4 bp/year (0.154%/year) — spread toll is negligible
```

### Full 30.3-Year Discovery Horizon (1993–2023)

| Metric | Gross B&H | Gross Weinstein | Venue B Fut B&H | Venue B Fut Weinstein | Venue A CFD B&H | Venue A CFD Weinstein |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **CAGR** | **8.04%** | 5.28% | **4.01%** | 2.65% | **1.44%** | 0.96% |
| **Annual Vol** | 18.79% | **11.07%** | 18.79% | **11.07%** | 18.79% | **11.07%** |
| **Sharpe Ratio** | 0.51 | **0.52** | **0.30** | 0.29 | **0.17** | 0.14 |
| **Max Drawdown** | -56.70% | **-27.48%** | -68.48% | **-31.43%** | -74.81% | **-34.48%** |
| **MAR Ratio** | 0.14 | **0.19** | 0.06 | **0.08** | 0.02 | **0.03** |
| **Terminal Wealth**| **10.39x** | 4.74x | **3.28x** | 2.21x | **1.54x** | 1.33x |

1. **Drawdown Avoidance is Real (Gate 2 PASS)**:
   Weinstein cuts maximum drawdown by more than half across all venues (-27.5% vs -56.7% gross; -31.4% vs -68.5% on futures). Peak-to-trough drawdowns during the 2000–2002 Dot-Com bust and the 2008 GFC are successfully truncated.
2. **Sharpe is Invariant to Proportional De-risking (Gate 1 FAIL)**:
   While annualized volatility drops by 41% (18.8% $\to$ 11.1%), annual return drops by 34% (8.04% $\to$ 5.28%). Because both mean and standard deviation contract in roughly equal proportion, the Sharpe ratio ($\mu / \sigma$) barely moves (+0.01 gross, -0.01 on Futures, -0.03 on CFD).
3. **The Compounding Penalty**:
   Missing 33.4% of sessions costs 2.76%/year in gross CAGR. Over 30 years, that compounding penalty is devastating: B&H turns \$1 into \$10.39, while Weinstein turns \$1 into \$4.74. Drawdown avoidance preserves emotional comfort, but foregoes more than half of terminal wealth.

---

## 3. Sub-Era Breakdown: Why Gate 3 Failed

Evaluated on Venue B (CME Futures basis decay $3.80\%$/year):

| Era | Window | Sessions | B&H Sharpe | Weinstein Sharpe | $\Delta$ Sharpe | MaxDD (B&H / W) | Verdict |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Era 1: Pre-GFC** | 1993–2007 | 3,599 | **0.33** | 0.28 | -0.05 | -53.9% / -27.7% | **FAIL** |
| **Era 2: ZIRP / QE** | 2008–2021 | 3,526 | 0.33 | **0.37** | **+0.03** | -55.2% / -31.4% | **PASS** |
| **Era 3: Rate Shock** | 2022–2023 | 500 | **-0.10** | -0.24 | -0.14 | -29.2% / -14.1% | **FAIL** |

- **Era 1 (Pre-GFC)**: The strong 1990s bull market penalized sitting in cash. Weinstein lagged B&H by 5 Sharpe points.
- **Era 2 (ZIRP / QE)**: Weinstein avoided the worst of 2008 (-55% B&H vs -31% W), slightly outperforming on Sharpe (+0.03).
- **Era 3 (Rate Shock 2022–2023)**: In a choppy, non-trending rate-hike regime with multiple bear market rallies, Weinstein suffered repeated whipsaws (entering late on rallies, exiting near troughs), generating a Sharpe of -0.24 vs -0.10 for B&H.

---

## 4. Architectural Diagnosis

1. **Long-Only Market Timing Cannot Overcome Equity Drift**:
   Unlike short-term statistical arbitrage where edge scales with trade count, long-horizon market timing sits in the shadow of the equity risk premium ($\approx 8\%$/year). Every session spent in cash has an expected cost of $+3.2\text{ bp}$.
2. **Financing Carry Asymmetry**:
   While Weinstein avoids financing drag while in cash (saving 33.4% of financing costs), the foregone market upside during the first 10–20 days of cyclical market recoveries (which occur when price is still below the 150-day moving average) exceeds all financing savings.
3. **Registry Classification**:
   Weinstein Stage Analysis is formally filed as **FAILED** in the evidence registry. It will not arm.
