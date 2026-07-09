# Randomized-window distribution study — Sprint 1

The core deliverable (CLAUDE.md principle #3): replace a single start-date CAGR with the
**spread of outcomes** over many random windows. Total-return prices, USD, pre-tax.

- **Data:** 1999-03-10 → 2026-07-08 offline CSVs (`data/SPY.csv`, `data/QQQ.csv`).
- **Reproduce:** `python backtest.py --seed 42 --n 1000` (deterministic; same seed → same numbers).
- **Method:** N random start dates on the aligned QQQ/SPY index; each runs the DCA sim over a
  full `years`-long window. QQQ and SPY draw the **same** start dates (paired head-to-head).
- Intra-window drawdown = worst peak-to-trough fall of the **portfolio value** during
  accumulation (what the investor sees in the balance), not the index drawdown.

## Baby — 18-yr weekly $100 DCA, 0.5% FX fee/contribution (n=1000, seed 42)

| Ticker | XIRR p10 / p50 / p90 | Multiple p10 / p50 / p90 | Worst value DD: median / worst decile |
|--------|----------------------|--------------------------|----------------------------------------|
| SPY | 9.1% / 11.3% / 13.7% | 2.41x / 3.06x / 3.91x | −41.1% / −46.9% |
| QQQ | 12.7% / 16.6% / 18.6% | 3.52x / 5.35x / 6.71x | −39.4% / −44.0% |

**Head-to-head (paired starts):** QQQ beat SPY in **100.0%** of 1000 windows. XIRR edge
(QQQ−SPY): median **+4.8%**, worst **+2.7%**, best +6.2%.

## Wife — 10-yr lump $20,000 + monthly $500 DCA, PIE (FX fee = 0) (n=1000, seed 42)

| Ticker | XIRR p10 / p50 / p90 | Multiple p10 / p50 / p90 | Worst value DD: median / worst decile |
|--------|----------------------|--------------------------|----------------------------------------|
| SPY | 2.2% / 10.7% / 14.7% | 1.15x / 2.00x / 2.61x | −33.9% / −46.7% |
| QQQ | 4.8% / 15.2% / 20.4% | 1.36x / 2.69x / 3.80x | −36.3% / −45.7% |

**Head-to-head (paired starts):** QQQ beat SPY in **96.4%** of 1000 windows. XIRR edge
(QQQ−SPY): median **+4.5%**, worst **−0.7%**, best +7.7%.

Plot: `results/random_windows.png` (overlaid XIRR histograms, both scenarios).

## Reading this honestly — the important caveat

**"QQQ beat SPY in 100% of 18-yr windows" is NOT evidence QQQ's concentration is safe.**
It is an artifact of history length. We have ~27 years of data, so every 18-yr window must
start in a **~9-year span (1999-03 → 2008-07)**. The 1000 "random" windows are heavily
**overlapping resamples of essentially one macro path** — they are not independent draws, and
the effective sample size is a handful, not 1000. The p10/p90 spread understates true
uncertainty for the same reason.

Crucially, the one regime that *did* punish QQQ — buying at the 2000 peak — still favours QQQ
over a full **18-yr DCA**, because (a) dollar-cost-averaging keeps buying all the way down
through the −83% dot-com crash, lowering the average cost, and (b) an 18-yr window that starts
in 2000-2008 always extends into the 2010s-2020s tech boom. Our data simply **does not contain**
an 18-yr DCA window where QQQ's concentration lost. That is a limit of the sample, not a law.

The wife's 10-yr study is more informative precisely because it admits more distinct starts
(1999→2016) and a wider outcome spread: SPY's 10-yr XIRR p10 falls to **2.2%** and QQQ's to
**4.8%** — a reminder that a 10-yr horizon can deliver near-cash returns from a bad entry, and
QQQ's edge, while still 96% of the time, has a losing tail (worst window −0.7% vs SPY).

**Takeaway for the decisions:** QQQ's historical edge over an 18-yr DCA is real and robust *in
this sample*, but the sample cannot see a genuinely adverse 18-yr Nasdaq regime because none has
completed since 1999. Treat the concentration risk as **not disproven**, not as absent. The
honest downside to weigh is the drawdown, not the win-rate: both scenarios put a ~40-47% peak-
to-trough fall of the balance squarely on the table during accumulation.
