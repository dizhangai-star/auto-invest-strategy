# Sprint 9 — Would "buy the dip" have helped on the *real* scenario?

Applies the Sprint 8b dip rule to the actual-portfolio scenario from Sprint 7. Same
**NZ$90,000** over the same **2019-02-25 → 2024-10-11** deposit window, but deployed
**daily** into each ticker under an even-daily baseline vs the dip rule (buy 2× on a close
≤ −1/−2/−3%, skip the next calm day), converted NZD→USD at daily spot (0% IBKR-scale FX),
then held to 2026-07-10. The only thing that varies across rows is *when* within the window
the fixed NZD gets deployed.

## Result

| Ticker | Strategy | dip days | Value 2026-07-10 | Multiple | Δ vs even-daily |
|---|---|---|---|---|---|
| QQQ | Even daily (baseline) | — | $149,788 | 2.57x | — |
| QQQ | Dip 2× on ≤ −1% | 262 | $150,062 | 2.58x | **+$274** (+1.1bp/yr) |
| QQQ | Dip 2× on ≤ −2% | 108 | $149,929 | 2.57x | +$141 (+0.9bp/yr) |
| QQQ | Dip 2× on ≤ −3% | 44 | $149,889 | 2.57x | +$101 (+0.8bp/yr) |
| SPY | Even daily (baseline) | — | $122,868 | 2.11x | — |
| SPY | Dip 2× on ≤ −1% | 182 | $123,026 | 2.11x | **+$158** (+0.5bp/yr) |
| SPY | Dip 2× on ≤ −2% | 61 | $122,970 | 2.11x | +$102 (+1.0bp/yr) |
| SPY | Dip 2× on ≤ −3% | 24 | $122,907 | 2.11x | +$39 (+0.2bp/yr) |

**Buy-the-dip barely registers on the real path.** Across all six variants the tilt added
**$39–274** on a $123k–150k result — at most ~1bp/yr, the same rounding-error edge the Sprint
8b window distribution found across 1,000 windows. The even-daily baseline itself lands
within ~0.1% of Sprint 7's weekly DCA (cadence is a wash, Sprint 3). What decided this
outcome was being in the market for the 2019–2026 run, not the day-level timing of deposits.

## Why it doesn't move the needle here

The rule is self-funding — "double today, skip a later calm day" moves a dollar forward by
*days*, into a dip that recovers within days. It holds no cash and adds no net
time-in-market. The stronger buy-the-dip you might picture — hold a cash reserve for months,
deploy a lump into a −20%/−30% crash — is a genuinely different (and riskier) strategy: the
cash drag while waiting usually costs more than the dip discount earns, and 2019–2026 had
only brief, fast-recovering drawdowns to exploit. Not modelled here; flagged as a candidate.

## Method

- `real_dip_variants` in `backtest.py` reuses `dip_buy_schedule` (the 2×/skip amount
  pattern) and Sprint 7's `simulate_nzd_dca_hold` (FX conversion + accumulate-then-hold), so
  only deposit timing varies. NZD total is held at exactly NZ$90,000; USD-deployed differs by
  cents because different days convert at different spots (multiple/XIRR normalize for it).
- Data contract: `results/real_dip.csv`. The **My portfolio vs DCA** dashboard tab reads it
  for the second comparison table below the main chart.

Reproduce: `python3 backtest.py && python3 build_report.py && python3 build_dashboard.py`
(network off; prices from `data/*.csv`, which end 2026-07-10).
