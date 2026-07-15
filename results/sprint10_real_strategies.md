# Sprint 10 — Weekly vs daily vs buy-the-dip on the *real* chart

Sprint 7 drip-fed the real NZ$90k into SPY/QQQ **weekly**. This adds two more cadences to
the same "My portfolio vs DCA" chart so all three sit side by side: **daily** (even over
every trading day) and **buy-the-dip** (daily, doubling on a close ≤ −3% and skipping a
later calm day — the Sprint 8b rule at the −3% threshold). Same NZ$90,000, same
**2019-02-25 → 2024-10-11** deposit window, converted NZD→USD at spot (0% IBKR-scale FX),
then held to 2026-07-10. Only *when* the fixed NZD gets deployed changes across cadences.

## Result

| | USD deployed | Value 2026-07-10 | Multiple | XIRR | Δ vs weekly |
|---|---|---|---|---|---|
| My portfolio (actual) | $58,205 | $82,740 | 1.42x | 7.8% *(approx)* | — |
| QQQ · weekly | $58,205 | $149,994 | 2.58x | 21.5% | — baseline |
| QQQ · daily | $58,204 | $149,788 | 2.57x | 21.5% | −$206 (−2.9bp/yr) |
| QQQ · dip −3% | $58,221 | $149,889 | 2.57x | 21.5% | −$105 (−2.1bp/yr) |
| SPY · weekly | $58,205 | $122,961 | 2.11x | 16.8% | — baseline |
| SPY · daily | $58,204 | $122,868 | 2.11x | 16.8% | −$93 (−1.5bp/yr) |
| SPY · dip −3% | $58,216 | $122,907 | 2.11x | 16.8% | −$54 (−1.3bp/yr) |

**Cadence is a wash — again.** All three curves for a ticker land within ~0.15% of each
other (≤ ~3bp/yr of XIRR), so on the chart the three SPY lines and the three QQQ lines
collapse into two clusters rather than six distinct paths. That overlap *is* the result: the
gap between SPY (2.11x) and QQQ (2.58x), and between either benchmark and the real 1.42x, is
what actually mattered — not weekly-vs-daily-vs-dip.

Here weekly edges out daily by a hair (and dip lands between) because weekly deploys each
week's chunk on the first trading day, i.e. marginally *earlier* on average in a decade that
mostly rose — the same "time-in-market beats timing" effect, in miniature. The dip tilt's
tiny sign flips vs Sprint 9's even-daily baseline (there dip was slightly *positive*): the
comparison anchor differs (weekly here vs even-daily in Sprint 9), and both deltas are
basis-point noise either way.

## Method

- `run_real_vs_dca` in `backtest.py` now loops `REAL_STRATEGIES` (weekly/daily/dip) per
  ticker, reusing `_real_strategy_schedule` (weekly = the Sprint 7 even-weekly grid; daily =
  even over trading days; dip = `dip_buy_schedule` at `REAL_DIP_THRESHOLD` = −3%) and the
  Sprint 7 `simulate_nzd_dca_hold` for FX conversion + accumulate-then-hold.
- Persists six value curves + a keyed summary to `results/real_vs_dca_*.csv`; the dashboard's
  "My portfolio vs DCA" tab plots them (weekly solid, daily dashed, dip dotted, colored per
  ticker) and tabulates all six + the actual portfolio. Re-simulates nothing in the browser.
- The dedicated −1/−2/−3% dip-threshold sensitivity table (Sprint 9, `real_dip.csv`) stays
  below the chart; the daily and dip −3% numbers above tie out to it exactly.
