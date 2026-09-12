# RESULTS — TSMOM_FUTURES_01

**Prereg**: `prereg/TSMOM_FUTURES_01.md`, sha `44253c9c30427a8c`, sealed before any return or Sharpe ratio was computed on futures.
**Harness**: `_tsmom_futures.py`
**Run**: 2026-09-12, discovery only (`ts < 2024-01-01`), 3,255 daily sessions across 12.59 years (2011-05-27 to 2023-12-29).
**Holdout**: NOT READ. Gates 1, 2, and 3 failed; prereg section 4 mechanically blocks holdout execution.

---

## 1. Verdict — FAILED (Gates 1, 2, 3 FAIL; Gate 4 PASS)

| Gate | Requirement | Measured | Verdict |
| :--- | :--- | :--- | :--- |
| **Gate 1: Economic Alpha** | Net Sharpe $\ge 0.60$ and $\text{CAGR} > 0$ | Sharpe: **0.27**, CAGR: **+1.75%** | **FAIL** |
| **Gate 2: Trend vs Static Long-Only** | $\Delta\text{Sharpe} \ge +0.20$ over Control A | $\Delta\text{Sharpe}$: **-0.25** | **FAIL** |
| **Gate 3: Significance vs Random Null** | $z \ge 2.00$ vs Control B (1,000 draws) | $z = \mathbf{+1.14}$ | **FAIL** |
| **Gate 4: Temporal Stability** | Net Sharpe $> 0$ in $\ge 3/4$ Eras | **3 of 4** sub-eras passed | **PASS** |

Causality assertion PASSED across truncated prefix cuts.

---

## 2. Empirical Performance Summary

```
Evaluation Horizon:     12.59 years (3,255 sessions, 2011-05-27 to 2023-12-29)
Rebalance Schedule:     Monthly (22 trading sessions), 148 rebalance events
Assets:                 ES, YM, CL, GC (full window); RTY added post 2017-07-10
Total Turnover Toll:    23.80 bp over 12.6 years (1.89 bp/year)
```

| Metric | TSMOM Net | TSMOM Gross | Control A Net (Static Long-Only) | Delta (TSMOM - CtrlA) |
| :--- | :---: | :---: | :---: | :---: |
| **CAGR** | 1.75% | 1.77% | **4.17%** | -2.42% |
| **Annualized Vol** | **7.10%** | **7.10%** | 8.25% | -1.15% |
| **Sharpe Ratio** | 0.27 | 0.28 | **0.52** | **-0.25** |
| **Max Drawdown** | -22.11% | -22.06% | **-19.09%** | 1.16x |
| **MAR Ratio** | 0.08 | 0.08 | **0.22** | 0.36x |
| **Terminal Wealth**| 1.24x | 1.25x | **1.67x** | -0.43x |

### Turnover Toll is Non-Binding on CLOB
On the CME Central Limit Order Book with micro contract pricing, total execution toll was **1.89 bp/year** ($0.0189\%$/year). The difference between Gross Sharpe (0.28) and Net Sharpe (0.27) is a negligible 0.01.
Wall 1 is completely dismantled on a CLOB for monthly rebalanced futures. The failure of TSMOM is **purely a signal and alpha failure**, not an execution cost artifact.

---

## 3. The Control Comparisons: Why TSMOM Failed

### Control A — Static Risk Parity Crushes Trend Following
Control A applies identical inverse-volatility sizing to the exact same five assets, but with a permanent `+1.0` sign:
- Static Long-Only generated **Sharpe 0.52** and **CAGR 4.17%** with **-19.09% Max Drawdown**.
- TSMOM generated **Sharpe 0.27** and **CAGR 1.75%** with **-22.11% Max Drawdown**.
- In the 2011–2023 post-GFC macroeconomic regime, dynamic trend following on a 12-month lookback was an active detractor: flipping short on equities during cyclical pullbacks resulted in selling bottoms and getting whipsawed on aggressive V-bottom liquidity recoveries (late 2011, early 2016, late 2018, mid 2020).

### Control B — Random Sign Null (1,000 Monte Carlo Draws)
```
Control B Mean Sharpe:  -0.009 (properly centred on zero)
Control B Std:          0.248
TSMOM z-score:          +1.14
```
TSMOM displays positive directional skill over pure coin flips ($z = +1.14$, beating 87.3% of random allocations), but falls well short of the $z \ge 2.00$ hurdle.

---

## 4. Chronological Sub-Era Breakdown (Gate 4)

| Era | Window | Sessions | Net Sharpe | CAGR | Max Drawdown | Verdict |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Era 1: Post-GFC / Euro Debt** | 2011–2014 | 812 | 0.09 | +0.40% | -12.3% | **PASS** |
| **Era 2: Commodity Crash** | 2014–2017 | 816 | **0.76** | **+5.42%** | **-10.1%** | **PASS** |
| **Era 3: QT / COVID Shock** | 2017–2020 | 823 | -0.06 | -0.85% | -22.1% | **FAIL** |
| **Era 4: Rate Shock / Tightening**| 2020–2023 | 798 | 0.41 | +2.57% | -10.7% | **PASS** |

- **Era 2 (2014–2017)** was the golden era for TSMOM: it caught the prolonged structural collapse in WTI Crude Oil from \$105 to \$26.
- **Era 3 (2017–2020)** broke the strategy: sharp equity drawdowns followed by lightning-fast stimulus-driven V-reversals caused severe momentum whipsaws (MaxDD -22.1%).
- **Era 4 (2020–2023)** recovered (Sharpe 0.41) by riding the inflation commodity rally and post-2022 equity adjustments.
- Net Sharpe was positive in 3 of 4 eras, passing Gate 4.

---

## 5. Architectural Conclusion

1. **Execution Reality Established**:
   On CME CLOB venues, monthly multi-asset trend execution incurs less than 2 bp/year in toll. The execution vehicle is fully viable.
2. **Canonical 12-Month Momentum is Insufficient**:
   Classical Moskowitz 12-month TSMOM across a 5-contract equity/commodity basket does not generate standalone alpha over a static risk parity basket. The post-2010 regime of swift central bank interventions shortened trend persistence and increased mean-reversion whipsaws at the 12-month horizon.
3. **Evidence Registry Entry**:
   `tsmom_futures` is filed as **FAILED** in the evidence registry.
