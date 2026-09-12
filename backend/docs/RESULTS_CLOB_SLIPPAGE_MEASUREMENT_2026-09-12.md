# RESULTS — CLOB Slippage Measurement (Phase 4)

**Measured**: 2026-09-12. **Sample**: 4,573,432 `tbbo` prints, GLBX.MDP3,
**2023-10-01 → 2023-11-01**, strictly inside the discovery window.
**Spec**: `docs/SPEC_FUTURES_INGESTION.md` §6 Phase 4. **Cost**: $9.98.
**Holdout**: untouched. The sample end date precedes `DISCOVERY_END` by 61 days.

---

## 1. The question

Every toll in this programme divides by a **4.3x slippage multiplier**, measured
on 7 of 7 live FVG fills on an MT5 retail account (median 3.3x, worst 34.7x on
gold). It was treated as a property of execution. `SPEC_FUTURES_INGESTION.md` §0
required it be **re-measured** on a central limit order book rather than assumed
to carry over *or* assumed to be 1.0.

```
M  =  |trade price - pre-trade mid|  /  (0.5 * pre-trade spread)
```

`M = 1.0` is execution exactly at the touch. A round trip crosses the spread
once, paying two half-spreads, so **round-trip cost = spread x M**.

## 2. Method, and one thing settled empirically

`tbbo` pairs every trade print with the top-of-book quote. Two filters applied:
prints with `side = 'N'` (open-auction, no aggressor) and any crossed or locked
book (`bid >= ask`) are removed — 19,187 auction prints on GC, 0 crossed books
after that filter.

**Whether the quoted BBO is pre- or post-trade was not assumed.** Both
conventions were tested and the data chose:

```
same-row BBO      96.8% of prints at the touch
previous-row BBO  80.1% of prints at the touch
```

The same-row quote is the pre-trade state, so that convention is used.

## 3. Headline — the 4.3x multiplier does not survive

| root | prints | 1-tick spread | inside | **AT TOUCH** | through | mean M | median M | p99 |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| GC | 2,003,181 | 91.5% | 0.32% | **96.78%** | 2.90% | 1.0928 | **1.0000** | 3.00 |
| CL | 2,570,251 | 87.6% | 3.21% | **93.92%** | 2.87% | 1.0401 | **1.0000** | 3.00 |

**Median M is exactly 1.0000 on both roots.** Against the dealing desk's 4.3x
mean and 3.3x median, this is a different execution regime, not a smaller number
in the same regime.

**The finding is about venue, not about markets.** A dealing desk quoted a
spread and then filled worse than it, by a factor that did not depend on order
size. A CLOB fills at the touch and charges only for depth actually consumed.
The 4.3x was **rent**, not microstructure.

## 4. The qualification that matters — M scales with size

| order size (contracts) | GC mean M | CL mean M |
| :--- | ---: | ---: |
| 1 | 1.0417 | 1.0039 |
| 2–5 | 1.0829 | 1.0515 |
| 6–20 | 1.5235 | 1.3202 |
| 21–100 | **3.7230** | **3.2443** |
| 100+ | 6.1875 | 2.3939 |

At sweep level — one aggressor order consuming several resting orders, grouped
by shared `ts_event`:

| sweep size | GC n | GC mean M | CL n | CL mean M |
| :--- | ---: | ---: | ---: | ---: |
| <= 10 | 31,444 | 1.690 | 53,583 | 1.531 |
| 11–50 | 14,002 | 2.296 | 16,309 | 2.187 |
| 51–200 | 1,606 | **4.523** | 1,570 | **3.827** |
| 200+ | 86 | **12.654** | 107 | **8.766** |

**A 51–200 lot GC sweep costs 4.52x — worse than the retail CFD figure.** So
"futures are cheap" is false as a general claim. Futures are cheap *at small
size*. The cost curve is the finding; the median is only its left edge.

## 5. Why this rescues the micro contracts specifically

A micro is 1/10 the notional of its parent, so an exposure equal to one full GC
contract is 10 MGC — and the **bp cost of crossing one tick is identical**
between micro and full-size ($1.00 on $19,500 versus $10.00 on $195,000, both
0.513 bp). What differs is commission as a share of notional, and book depth.

At 1–5 contracts, measured `M = 1.04–1.08`:

| micro | notional | tick bp | spread toll | commission bp | **total** | CFD it replaces |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| **MGC** | $19,500 | 0.513 | 0.555 | 0.533 | **1.089** | XAUUSD **5.00** |
| MYM | $17,000 | 0.294 | 0.319 | 0.612 | **0.930** | — |
| MES | $22,500 | 0.556 | 0.602 | 0.462 | **1.064** | — |
| M2K | $9,250 | 0.541 | 0.585 | 1.124 | **1.710** | — |
| MCL | $7,500 | 1.333 | 1.402 | 1.387 | **2.789** | EURUSD 2.88 |

**MGC at 1.09 bp against XAUUSD's 5.00 bp is a 4.6x reduction — the first
measured relief of Wall 1 in this programme.** Every previous attempt assumed it.

**MCL is the exception and it is not marginal — it is no better.** 2.79 bp
against the EURUSD CFD's 2.88 bp, because commission on a $7,500 notional is
1.39 bp on its own. Micro crude does not escape Wall 1.

## 6. Limitations — what this does NOT establish

1. **Only GC and CL were measured.** ES, YM and RTY were not. The cost model
   applies a conservative default to them and tags it
   `ASSUMED (this root was NOT measured)`. ES is the most liquid future listed
   and its true M is probably *lower*, but that is a guess, not a measurement.
2. **No micro contract was measured.** MGC and MCL trade their **own, thinner
   books**, not GC's and CL's. Tick-in-bp is identical, but depth is not, and
   depth is exactly what M prices. This is the largest open assumption.
3. **This measures what the market achieved, not what our orders would.** Every
   print is someone else's fill. We had no queue position and no rejects. The
   MT5 4.3x, by contrast, was measured on *our own* fills — so the comparison is
   slightly unfair to the CLOB's disadvantage and should be re-checked against
   live micro fills.
4. **One month, one regime.** October 2023 was not a stress period. The size-cost
   curve steepens precisely when volatility spikes, which is when strategies
   trade most.
5. **Commission is ESTIMATED.** $1.04 RT all-in is plausible for micros but no
   broker schedule is on file; it is tagged `ESTIMATED` in the cost model. It is
   32–50% of total toll on MGC/MES and therefore worth sourcing properly.

## 7. Consequence for the programme

`TOLL_BREAKEVEN_01` §3 bounds passive rehabilitation at `edge/toll >= 0.767`,
derived from `Delta_max <= spread = toll / 4.3`. **That derivation is venue-
specific and does not hold on a CLOB**, where toll is `spread * M` with
`M ~ 1.05` at small size, so `Delta_max / toll ~ 0.95` rather than 0.233. The
sealed document is not amended — its arithmetic was correct for the venue it was
written about — but any future CLOB pre-registration must re-derive the bound
rather than import 0.767.

More directly: a strategy with gross expectancy of **1.5–4.0 bp** was
untradeable on the MT5 book and is arithmetically viable on micro equity-index
or gold futures. Several refuted candidates sit in that band on gross. **None of
them is thereby resurrected** — each was refuted on its own evidence, most at
the gross level where toll is irrelevant (`SQUEEZE_EXPANSION_01` grossed −0.90
bp; `VOLMOM_01` −12.28 bp net with the conditioner backwards). Migrating a
refuted strategy to a cheaper venue is a **new test on a new venue** requiring a
new pre-registration with gates fixed in advance, not a re-run until the venue is
favourable.
