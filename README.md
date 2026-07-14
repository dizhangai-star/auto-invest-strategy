# ETF Backtest — SPY vs QQQ (basic, honest)

A small backtest to build intuition for the two setups you're planning:

- **Baby** — weekly DCA into QQQ (Nasdaq-100) over a long horizon.
- **Wife** — lump sum + monthly DCA into the S&P 500 (SPY stands in for a NZ S&P 500 PIE fund).

## Run it (in Claude Code, on your machine)

```bash
pip install -r requirements.txt
python backtest.py
python build_dashboard.py    # interactive Plotly dashboard -> results/dashboard.html
                             # (reads the committed results/*.csv + data/*.csv; no network)
```

The dashboard is a left-sidebar tabbed page (one view at a time; hash-routed, so tabs are
bookmarkable). It includes an **interactive projection calculator** (its own tab): deposit amount,
cadence, horizon, lump, FX fee and QQQ/SPY mix are recomputed client-side from the committed
`results/projection_factors.csv` (per-window linear factors from the engine) — p10/p50/p90
final values across 1,000 historical start dates, never a single flattering number, plus a
fan chart of the p10–p90 value range over the years en route (vs money put in). A
**My portfolio vs DCA** tab (Sprint 7) validates a real track record — actual NZD deposits
(2019–2024) vs the same money drip-fed weekly into SPY/QQQ, from the committed
`results/real_vs_dca_*.csv`. Three buy-timing tabs (Sprints 8/8b/9) test whether *when* you
buy matters: **Buy day of week** (weekly DCA anchored Mon–Fri) and **Buy the dip** (daily DCA
that doubles on a −1/−2/−3% day and skips the next), plus a dip comparison on the real
scenario inside the **My portfolio vs DCA** tab. The consistent finding: intra-period timing
moves outcomes by basis points, while start-date luck and asset choice move them by
percentage points.

Your machine has open internet, so `yfinance` pulls real total-return history for you.
(The Claude web sandbox can't reach Yahoo Finance, which is why this is built to run locally.)

Edit the `CONFIG` block at the top of `backtest.py` to change contribution amounts,
tickers, start dates, or the FX fee.

## What it computes

- **Per-ticker metrics** — CAGR, annualized volatility, Sharpe (rf=0), max drawdown
  with peak/trough dates and years-to-recover, best/worst calendar year, % positive years.
- **Period bias** — CAGR from several start dates side by side. This is the point of the
  whole exercise: QQQ's apparent edge over SPY shrinks or reverses depending on whether
  your window includes the 2000–02 dot-com crash. Don't trust a 2010-onward sample.
- **Two DCA scenarios** — reports total invested, final value, growth multiple, and
  **XIRR** (money-weighted return — the honest number for a drip-feed, not the headline CAGR).
- **Charts** — growth of $1 (log scale) and drawdown, saved to `backtest_charts.png`.

## What it deliberately does NOT model (all easy extensions)

1. **Currency.** Everything is in USD. For the baby's actual US-listed QQQ, the unhedged
   NZD/USD move is a real extra swing — overlay it by pulling `NZDUSD=X` and converting.
2. **Fund TER is not double-counted.** An ETF's price is already net of its management fee,
   so the only *extra* cost modelled is the platform **FX fee per contribution** (0.5% for
   Hatch/Sharesies; set to 0 for a NZ PIE fund).
3. **Tax.** PIE (28% PIR cap) vs FIF is an after-the-fact layer, not in these returns.

## Offline fallback

If `yfinance` is ever blocked, drop CSVs at `data/SPY.csv`, `data/QQQ.csv`
(a `Date` index and a `Close` column of adjusted/total-return prices) and it will use those.

## Sensible next steps

All of the originally planned extensions have shipped — the randomized start-date study
(Sprint 1), the QQQM/VOO tracking check and NZDUSD overlay (Sprint 2), the after-tax layer
(Sprint 3), the dashboard and calculator (Sprints 4–6), the real-portfolio validation
(Sprint 7), and the buy-timing studies (Sprints 8/8b/9 — weekday, dip double-down, and the
dip on the real scenario). See `SPRINT_PLAN.md` for results and the remaining optional
candidates (e.g. replacing Sprint 7's even-split assumption with the actual per-deposit
schedule, or modelling a cash-reserve buy-the-dip with a drawdown trigger).
