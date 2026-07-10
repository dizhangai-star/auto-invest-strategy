# Sprint 4 — Interactive dashboard (communication layer, not new evidence)

The **[interactive dashboard](dashboard.html)** (`results/dashboard.html`, copied to
`docs/dashboard.html` for GitHub Pages) renders four Plotly views from the committed
artifacts — it *reads* the Sprint 1 data contract (`results/windows_*.csv`,
`results/fan_*.csv`) and offline `data/*.csv` prices, and **re-simulates nothing**, so its
numbers match `random_windows.md` exactly (verified: XIRR p10/p50/p90, win-rates
100%/96.4%, drawdown p10s all tie out).

- **1 · Outcome distribution** (lead view): XIRR + final-multiple histograms, QQQ vs SPY,
  both scenarios, with the p10/p50/p90 and win-rate stats inline.
- **2 · Percentile fan**: p10–p90 band + p50 line of wealth-multiple vs elapsed years,
  from `fan_*.csv` — the spread stays front-and-center, never one line.
- **3 · Bull/bear cycles**: growth-of-$1 (log) with QQQ bear spans (≤ −20%, peak→recovery)
  shaded via the engine's own drawdown definition. The −83% dot-com span
  (2000-03-28 → 2015-02-20) plus 2018 −23%, 2020 −29%, 2022 −35%, 2025 −23%.
- **4 · Orders on chart**: weekly DCA buys on the full-history QQQ path — **labelled as
  ONE illustrative path**, deliberately last, with a warning that it is exactly the
  single-start-date view the rest of the page exists to correct.

Honesty notes carried into the page itself: the baby's 100% win-rate is a sample-length
artifact (overlapping windows, one macro path); both scenarios show a ~40–47% worst-decile
balance drawdown; the dot-com span appears in full in no completed 18-yr window.

Build: `python3 build_dashboard.py` (offline by construction — reads only committed CSVs,
never yfinance; output is byte-reproducible, fixed Plotly div ids). Self-contained HTML
(Plotly inlined, ~6 MB), opens with network off.
