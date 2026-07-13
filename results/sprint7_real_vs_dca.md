# Sprint 7 — Real portfolio vs the same money drip-fed into SPY/QQQ

Validation of a real track record. NZ$90,000 was actually deposited into a US-stock
portfolio between **2019-02-25 and 2024-10-11**; that portfolio was worth
**US$82,740.04 on 2026-07-10**. The counterfactual: the same NZ$90,000 modelled as
**294 even weekly buys of NZ$306.12**, each converted to USD at that week's NZDUSD spot
with a **0% FX fee** (the real IBKR-scale cost — not the Hatch 0.5% used elsewhere),
buying SPY or QQQ at the week's first trading-day total-return close, then **held with no
further buys** to 2026-07-10.

## Result

| | USD deployed | Value 2026-07-10 | USD multiple | XIRR (USD) | NZD-terms value | NZD multiple |
|---|---|---|---|---|---|---|
| My portfolio (actual) | $58,205 | $82,740 | 1.42x | 7.8% *(approx)* | NZ$144,158 | 1.60x |
| SPY (simulated DCA) | $58,205 | $122,961 | 2.11x | 16.8% | NZ$214,234 | 2.38x |
| QQQ (simulated DCA) | $58,205 | $149,994 | 2.58x | 21.5% | NZ$261,335 | 2.90x |

The verdict is not close: over this specific window, plain weekly index DCA would have
beaten the actual portfolio by ~$40k (SPY) to ~$67k (QQQ) on the same deposits — roughly
9–14 percentage points of money-weighted return per year. In NZD terms the actual
portfolio still grew 1.60x (the NZD's fall vs USD helped every leg equally).

## Method

- Accumulate-then-hold: `simulate_nzd_dca_hold` in `backtest.py` — contributions stop at
  the last real deposit date, unlike `simulate_dca`, which contributes through valuation.
- Even split: NZ$90,000 ÷ 294 weeks. The code is schedule-shaped, so an actual
  (date, amount) deposit CSV from broker statements can drop in later.
- FX: `NZDUSD=X` spot, forward-filled to each buy date; final NZD-terms value converts
  back at the last available spot.
- The actual-portfolio XIRR assumes the same even schedule for its cashflows — it is
  **approximate**, labelled as such.
- Data contract: `results/real_vs_dca_timeseries.csv` (weekly value + invested-cum) and
  `results/real_vs_dca_summary.csv`; the dashboard tab **My portfolio vs DCA** only reads
  these.

## Read honestly

- **Even-split approximation.** The real deposits were lumpy; timing through the 2020
  crash and 2022 bear could move both the sim values and the approximate XIRR materially.
- **Hindsight benchmark.** SPY/QQQ are being compared *after* a decade they dominated. A
  portfolio that lagged them is the norm, not an anomaly — most active portfolios and most
  non-US markets did too. The honest conclusion is about the *forward* plan, not
  self-blame.
- **Single end point.** The actual portfolio's path between deposits is unknown — only its
  2026-07-10 value is real; drawdowns along the way are not comparable.
- Nominal USD, pre-tax. FIF/PIE tax and the NZD overlay apply equally to all rows and are
  covered in Sprints 2–3.

Reproduce: `python3 backtest.py && python3 build_report.py && python3 build_dashboard.py`
(network off; prices from `data/*.csv`, which end 2026-07-10).
