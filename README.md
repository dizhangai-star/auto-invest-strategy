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
final values across 1,000 historical start dates, never a single flattering number.

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

- Add `QQQM` (2020+) and `VOO` to confirm the cheaper share classes track their twins.
- Add the NZDUSD overlay to see the currency contribution to the baby's variance.
- Add a `--seed`/randomized start-date study (e.g. 1,000 random 18-year windows) to see the
  *distribution* of outcomes, not a single path — far more honest than one backtest line.
