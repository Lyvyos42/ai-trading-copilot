"""Backtest harness: in-sample/out-of-sample split, metrics, Monte Carlo.

WHAT THIS IS GUARDING AGAINST

A strategy tested once on all the data it was designed against will look
good, because the design absorbed the data. The three defences here are the
cheap ones that catch most of it.

1. AN OUT-OF-SAMPLE TAIL THAT IS NEVER TUNED ON.
   The split is chronological, not random. Shuffling rows before splitting
   leaks the future into the past through overlapping indicators, and a
   200-day SMA computed across a shuffled series is not a 200-day SMA.

2. A MULTIPLE-COMPARISONS CORRECTION.
   Testing k strategy/parameter/instrument combinations and reporting the
   best is not one experiment, it is k. At 26 hypotheses the 5% two-sided
   critical value moves from 1.96 to 3.10, and results that looked
   significant stop being so. `bonferroni_threshold` reports the bar the
   t-statistic actually has to clear, and the caller passes how many
   hypotheses were really tried - including the ones abandoned.

3. MONTE CARLO OVER TRADE ORDER.
   Maximum drawdown depends heavily on the sequence trades arrived in, and
   the observed sequence is one draw. Reshuffling the same trades many times
   gives the distribution of drawdowns the strategy could plausibly have
   produced. For prop-firm work that distribution is the answer, not the
   single realised path: an account is failed by the worst run it meets, not
   the average one.

WHAT IT DOES NOT DO

It does not model slippage, commission, borrow or overnight financing. Those
are instrument- and broker-specific and belong with the execution layer. The
returns here are gross, and a gross Sharpe of 0.9 on a strategy holding
overnight index exposure is not a net Sharpe of 0.9.
"""
from __future__ import annotations

import math
import random
import statistics as st
from dataclasses import asdict, dataclass, field
from typing import Callable, Optional, Sequence

TRADING_DAYS = 252


@dataclass
class Metrics:
    n: int
    win_rate: float
    mean_return: float
    total_return: float
    annualised: float
    volatility: float
    sharpe: float
    sortino: float
    profit_factor: float
    max_drawdown: float
    max_consecutive_losses: int
    t_stat: float
    exposure: float

    def to_dict(self) -> dict:
        return {k: (round(v, 6) if isinstance(v, float) else v)
                for k, v in asdict(self).items()}


def r_multiples_to_returns(r_multiples: Sequence[float],
                           risk_fraction: float = 0.01) -> list[float]:
    """Convert R-multiples into fractional account returns.

    R-multiples are ADDITIVE - a -1R trade loses one unit of risk - while every
    metric in this module compounds, because it takes fractional returns. Feed
    R-multiples in directly and `1 + (-1.0)` is zero: the equity curve hits the
    floor on the first full stop-out and every drawdown reads -100%. That is
    not a large drawdown, it is a unit error, and it looks alarming rather than
    wrong, which is worse.

    Multiplying by the fraction of the account risked per trade makes them
    returns. It also forces the caller to state what they were risking, which
    is the number that decides whether a +0.50R expectancy is a business or a
    rounding error.
    """
    if not 0.0 < risk_fraction < 1.0:
        raise ValueError("risk_fraction must be a fraction of the account")
    return [r * risk_fraction for r in r_multiples]


def equity_curve(returns: Sequence[float]) -> list[float]:
    eq = [1.0]
    for r in returns:
        eq.append(eq[-1] * (1.0 + r))
    return eq


def max_drawdown(returns: Sequence[float]) -> float:
    peak = 1.0
    worst = 0.0
    for v in equity_curve(returns):
        peak = max(peak, v)
        worst = min(worst, v / peak - 1.0)
    return worst


def compute_metrics(returns: Sequence[float],
                    periods_per_year: int = TRADING_DAYS) -> Metrics:
    """Metrics over a per-period return series. Zeros mean "flat that period".

    Zeros are kept in the series rather than dropped, because a strategy that
    is in the market a third of the time and one that is in it always are not
    comparable on per-trade statistics alone. `exposure` reports the share of
    periods actually held.
    """
    rs = list(returns)
    if not rs:
        return Metrics(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)

    active = [r for r in rs if r != 0.0]
    wins = [r for r in active if r > 0]
    losses = [r for r in active if r < 0]

    mean = st.mean(rs)
    vol = st.pstdev(rs) if len(rs) > 1 else 0.0
    downside = st.pstdev([min(r, 0.0) for r in rs]) if len(rs) > 1 else 0.0

    gross_win = sum(wins)
    gross_loss = abs(sum(losses))

    streak = worst_streak = 0
    for r in rs:
        if r < 0:
            streak += 1
            worst_streak = max(worst_streak, streak)
        elif r > 0:
            streak = 0

    scale = math.sqrt(periods_per_year)
    return Metrics(
        n=len(active),
        win_rate=(len(wins) / len(active)) if active else 0.0,
        mean_return=mean,
        total_return=equity_curve(rs)[-1] - 1.0,
        annualised=mean * periods_per_year,
        volatility=vol * scale,
        sharpe=(mean / vol * scale) if vol else 0.0,
        sortino=(mean / downside * scale) if downside else 0.0,
        profit_factor=(gross_win / gross_loss) if gross_loss else float("inf"),
        max_drawdown=max_drawdown(rs),
        max_consecutive_losses=worst_streak,
        # Against a null of zero mean, over the ACTIVE trades. Reported so the
        # caller can compare it against bonferroni_threshold rather than
        # against a habit.
        t_stat=((st.mean(active) / (st.pstdev(active) / math.sqrt(len(active))))
                if len(active) > 1 and st.pstdev(active) else 0.0),
        exposure=(len(active) / len(rs)) if rs else 0.0,
    )


def _inv_norm(p: float) -> float:
    """Inverse standard normal CDF (Acklam). Good to ~1e-9, no SciPy needed."""
    if not 0.0 < p < 1.0:
        raise ValueError("p must be in (0, 1)")
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    plow, phigh = 0.02425, 1 - 0.02425
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
               ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    if p > phigh:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
                ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    q = p - 0.5
    r = q * q
    return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / \
           (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)


def bonferroni_threshold(hypotheses: int, alpha: float = 0.05) -> float:
    """Two-sided critical |t| after correcting for `hypotheses` tests.

    Pass the number actually tried, not the number reported. Four strategies
    across four instruments at two parameter settings is 32, and the bar is
    then 3.16 rather than 1.96.
    """
    hypotheses = max(1, int(hypotheses))
    return abs(_inv_norm(alpha / (2.0 * hypotheses)))


@dataclass
class SplitResult:
    in_sample: Metrics
    out_of_sample: Metrics
    split_index: int
    hypotheses: int
    threshold: float

    @property
    def oos_significant(self) -> bool:
        return abs(self.out_of_sample.t_stat) >= self.threshold

    @property
    def degradation(self) -> float:
        """How much of the in-sample Sharpe survived out of sample.

        Below ~0.5 the in-sample result was mostly fitting. Above 1.0 usually
        means the out-of-sample window was simply an easier regime, which is
        not evidence of anything either.
        """
        if self.in_sample.sharpe == 0:
            return 0.0
        return self.out_of_sample.sharpe / self.in_sample.sharpe

    def to_dict(self) -> dict:
        return {
            "in_sample": self.in_sample.to_dict(),
            "out_of_sample": self.out_of_sample.to_dict(),
            "split_index": self.split_index,
            "hypotheses_tested": self.hypotheses,
            "bonferroni_threshold": round(self.threshold, 4),
            "oos_significant": self.oos_significant,
            "sharpe_retention": round(self.degradation, 4),
        }


def split_test(returns: Sequence[float], is_fraction: float = 0.8,
               hypotheses: int = 1,
               periods_per_year: int = TRADING_DAYS) -> SplitResult:
    """Chronological 80/20 split. The tail is never used for tuning."""
    rs = list(returns)
    cut = max(1, int(len(rs) * is_fraction))
    return SplitResult(
        in_sample=compute_metrics(rs[:cut], periods_per_year),
        out_of_sample=compute_metrics(rs[cut:], periods_per_year),
        split_index=cut,
        hypotheses=hypotheses,
        threshold=bonferroni_threshold(hypotheses),
    )


@dataclass
class MonteCarloResult:
    runs: int
    dd_median: float
    dd_p95: float
    dd_p99: float
    dd_worst: float
    ruin_probability: float
    ruin_threshold: float
    final_p05: float
    final_median: float

    def to_dict(self) -> dict:
        return {k: (round(v, 6) if isinstance(v, float) else v)
                for k, v in asdict(self).items()}


def monte_carlo(returns: Sequence[float], runs: int = 10_000,
                ruin_threshold: float = -0.10,
                seed: int = 20260907) -> MonteCarloResult:
    """Reshuffle trade ORDER and re-measure drawdown, `runs` times.

    Shuffling preserves the multiset of returns and destroys their sequence,
    which is exactly the question: given these trades, how bad could the path
    have been? It deliberately does NOT preserve autocorrelation, so where
    returns are genuinely serially dependent this overstates how much the
    order could have varied. For overnight index returns the serial
    correlation is small; for a trend strategy it would not be, and a
    stationary block bootstrap would be the right tool instead.

    `ruin_threshold` is the drawdown that ends the account - for a prop
    evaluation, the plan's own maximum drawdown as a fraction of the account.
    """
    rs = [r for r in returns]
    if not rs:
        return MonteCarloResult(0, 0, 0, 0, 0, 0, ruin_threshold, 0, 0)

    rng = random.Random(seed)
    dds: list[float] = []
    finals: list[float] = []
    ruined = 0
    order = list(rs)
    for _ in range(runs):
        rng.shuffle(order)
        peak = 1.0
        eq = 1.0
        worst = 0.0
        hit = False
        for r in order:
            eq *= (1.0 + r)
            peak = max(peak, eq)
            dd = eq / peak - 1.0
            if dd < worst:
                worst = dd
            if not hit and dd <= ruin_threshold:
                hit = True
        dds.append(worst)
        finals.append(eq - 1.0)
        ruined += 1 if hit else 0

    dds.sort()
    finals.sort()

    def pct(xs: list[float], p: float) -> float:
        return xs[min(len(xs) - 1, int(len(xs) * p))]

    return MonteCarloResult(
        runs=runs,
        dd_median=pct(dds, 0.50),
        dd_p95=pct(dds, 0.05),   # dds are negative and sorted ascending
        dd_p99=pct(dds, 0.01),
        dd_worst=dds[0],
        ruin_probability=ruined / runs,
        ruin_threshold=ruin_threshold,
        final_p05=pct(finals, 0.05),
        final_median=pct(finals, 0.50),
    )


@dataclass
class Report:
    strategy: str
    symbol: str
    split: SplitResult
    mc: MonteCarloResult
    full: Metrics
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"strategy": self.strategy, "symbol": self.symbol,
                "full_sample": self.full.to_dict(),
                "split": self.split.to_dict(), "monte_carlo": self.mc.to_dict(),
                "notes": self.notes}

    def render(self) -> str:
        f, s, m = self.full, self.split, self.mc
        lines = [
            f"{self.strategy} on {self.symbol}",
            f"  full sample   n={f.n}  win {f.win_rate*100:.1f}%  "
            f"ann {f.annualised*100:.2f}%  Sharpe {f.sharpe:.2f}  "
            f"Sortino {f.sortino:.2f}  PF {f.profit_factor:.2f}",
            f"                maxDD {f.max_drawdown*100:.1f}%  "
            f"worst streak {f.max_consecutive_losses}  "
            f"exposure {f.exposure*100:.0f}%",
            f"  in-sample     Sharpe {s.in_sample.sharpe:.2f}  "
            f"t {s.in_sample.t_stat:.2f}",
            f"  out-of-sample Sharpe {s.out_of_sample.sharpe:.2f}  "
            f"t {s.out_of_sample.t_stat:.2f}  "
            f"(threshold {s.threshold:.2f} at {s.hypotheses} hypotheses) "
            f"-> {'PASS' if s.oos_significant else 'not significant'}",
            f"  retention     {s.degradation:.2f} of in-sample Sharpe",
            f"  monte carlo   {m.runs} runs   median DD {m.dd_median*100:.1f}%  "
            f"p95 {m.dd_p95*100:.1f}%  p99 {m.dd_p99*100:.1f}%  "
            f"worst {m.dd_worst*100:.1f}%",
            f"                P(drawdown reaches {m.ruin_threshold*100:.0f}%) = "
            f"{m.ruin_probability*100:.1f}%",
        ]
        lines += [f"  note          {n}" for n in self.notes]
        return "\n".join(lines)


def evaluate(strategy_name: str, symbol: str, returns: Sequence[float],
             hypotheses: int = 1, ruin_threshold: float = -0.10,
             mc_runs: int = 10_000, is_fraction: float = 0.8,
             periods_per_year: int = TRADING_DAYS,
             notes: Optional[list[str]] = None) -> Report:
    return Report(
        strategy=strategy_name, symbol=symbol,
        full=compute_metrics(returns, periods_per_year),
        split=split_test(returns, is_fraction, hypotheses, periods_per_year),
        # Monte Carlo over the trades that happened, not the flat periods.
        mc=monte_carlo([r for r in returns if r != 0.0], mc_runs, ruin_threshold),
        notes=notes or [],
    )
