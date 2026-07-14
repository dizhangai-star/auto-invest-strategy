# Sprint 8 / 8b — Does *when* you buy matter? (weekday anchor + dip double-down)

Two timing studies that both answer the same way: intra-period timing choices move
outcomes by **basis points**, while start-date luck and asset choice move them by
**percentage points**. Each is a dashboard tab reading a committed CSV data-contract; the
engine simulates, the dashboard only summarizes. Total-return prices, USD, pre-tax; data
through 2026-07-10.

## Sprint 8 — buy day of week

The weekly DCA is re-run anchored to each weekday Mon–Fri: buy that day's close, roll
**forward** on a holiday (Mon → Tue), roll **back** only when the week has nothing later
(Fri closure → Thu). Windows are **paired** — the same 1,000 random 18-yr starts (seed 42)
under all five anchors — so the spread isolates the weekday effect from window luck.

| Full-history XIRR by buy day | Mon | Tue | Wed | Thu | Fri |
|---|---|---|---|---|---|
| QQQ | 15.26% | 15.26% | 15.26% | 15.26% | 15.26% |
| SPY | 11.37% | 11.37% | 11.37% | 11.37% | 11.37% |

Paired per-window spread (best − worst anchor): QQQ median **1.9bp**, p90 2.5bp, max 3.0bp;
SPY median **1.3bp**, p90 1.6bp, max 2.2bp — against a ~500bp p10→p90 start-date range on the
same windows. Monday was the best anchor in **92%** (QQQ) / **97%** (SPY) of windows — a real
"weekend effect" (Monday tends to be the week's weakest close), but ~2bp/yr is smaller than
even the 0.5% FX fee's ~3bp/yr drag. **Verdict: pick the day that suits your payroll.**

## Sprint 8b — buy the dip (double down)

Daily DCA ($100/day) that buys **2×** on a day closing ≤ −1/−2/−3% and **skips the next calm
day** (a skip-credit queue — cash-flow-neutral vs plain daily DCA, so the comparison is
fair). Fresh state per window; paired against a plain-daily baseline on the same 1,000
random 18-yr windows.

| Trigger | QQQ: doubles/yr · median window Δ | SPY: doubles/yr · median window Δ |
|---|---|---|
| ≤ −1% | 47.4/yr · +0.27bp/yr | 34.0/yr · +0.43bp/yr |
| ≤ −2% | 21.9/yr · +0.43bp/yr | 11.0/yr · +0.38bp/yr |
| ≤ −3% | 10.2/yr · +0.09bp/yr |  3.4/yr · +0.20bp/yr |

The tilt beats plain daily in **100%** of paired windows — mechanically, shifting the same
dollars onto red-day closes buys slightly cheaper — but the edge is **+0.1–0.4bp/yr**, under
0.06% of terminal wealth. Rarer triggers tilt less, so −3% gains the *least*. **Verdict: it
"works" but the prize is a rounding error; automate a boring schedule and ignore red days.**

## Why the effect is so small

Both strategies only move a little money, a little cheaper, a little sooner. The dip rule is
self-funding (each double repaid by a later skip), so it adds no net time-in-market — it
just shifts a dollar a few days into a dip that mostly mean-reverts within days. The
arithmetic caps the benefit at basis points. This is the same lesson as the Sprint 3
weekly-vs-monthly cadence check: entry-timing micro-optimizations are a wash; automation,
low fees, and simply being invested are what matter.

## Method

- `weekday_buy_dates` / `weekday_anchor_study` and `dip_buy_schedule` / `dip_double_study`
  in `backtest.py`. `simulate_dca` accepts precomputed buy dates and a per-buy amount Series
  (scalar path unchanged, regression-checked).
- Data contract: `results/weekday_anchor.csv`, `results/dip_double.csv`. Dashboard tabs
  **Buy day of week** (view7) and **Buy the dip** (view8) only read these.

Reproduce: `python3 backtest.py && python3 build_report.py && python3 build_dashboard.py`
(network off; prices from `data/*.csv`, which end 2026-07-10).
