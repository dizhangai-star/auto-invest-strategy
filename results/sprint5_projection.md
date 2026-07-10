# Sprint 5 — Projection calculator (dashboard view 3)

**Question it answers:** "if I deposit $X weekly/monthly for N weeks/months/years (plus an
optional lump), what will the portfolio be worth?" — for the Baby plan, the Wife plan, and a
custom QQQ/SPY mix ("my portfolio"), with the honest answer being a **range**, not a number.

## How it works (engine stays the sole source of numbers)

`simulate_dca`'s final value is *exactly* linear in (lump, per-period amount) for a fixed
window/cadence/ticker:

```
final = (1 − fx_fee) · [ lump · g0 + amount · s ]
g0 = P(end) / P(first buy)          s = P(end) · Σᵢ 1 / P(buyᵢ)
```

`backtest.py` persists per-window `(g0, s, n_buys)` to **`results/projection_factors.csv`**
over a grid of {SPY, QQQ} × {weekly, monthly} × {1..18-yr horizons} × 1,000 random start
dates (**seed 42**, same `sample_start_dates` on the aligned frame as Sprint 1 — so starts
are shared across tickers and the paired/blended math stays correlation-preserving).
36,000 rows, ~2.4 MB CSV, ~1.4 MB embedded as JSON in the dashboard (total 7.5 MB).

The dashboard JS only takes **linear combinations and percentiles** of these factors — it is
not a second simulation engine and cannot produce numbers the engine didn't. A ticker mix is
a fixed split of every contribution, held without rebalancing (`final = Σ wₜ·finalₜ`).
Horizons in weeks/months are **snapped to the nearest year on the 1–18 grid** (labelled in
the output); interpolation would fabricate windows that were never simulated.

The assumed-rate figure next to the distribution is a closed-form annuity FV (per-period
rate `(1+r)^(1/ppy)−1`, contributions at period start) — an intuition check only, labelled
as such. The calculator also reports the constant rate the historical p50 is equivalent to.

## Self-checks and tie-outs (all verified)

- **Built-in contract check**: `persist_projection_factors` asserts, for one window per grid
  cell (36 cells, lump and no-lump cases), that the factor formula reproduces
  `simulate_dca(...).final_value` via `np.isclose`. Regeneration fails loudly on any drift.
- **Exactness from the committed CSV**: weekly QQQ 18-yr row → factors $503,299.85 vs
  `simulate_dca` $503,300.21 (rel. err 7×10⁻⁷ = the `%.6g` CSV rounding); monthly SPY 10-yr
  with $20k lump → rel. err 6×10⁻⁷.
- **Baby preset ties out to Sprint 1** (same seed ⇒ identical windows): calculator multiples
  p10/p50/p90 = **3.52x / 5.35x / 6.71x** vs `random_windows.md` 3.52x / 5.35x / 6.71x; the
  implied constant rate **16.6%/yr** equals the committed XIRR p50 (16.6%).
- **Wife preset**: p10/p50/p90 multiples 1.15x / 2.00x / 2.61x and implied 10.8%/yr vs the
  committed 1.15x / 2.00x / 2.61x, XIRR p50 10.7%.
- **Hand-checked blend**: $200/wk, 10 yr, 50/50 QQQ/SPY, 0.5% fee → calculator p50
  $212,616 vs a direct `simulate_dca` loop over the same 1,000 windows $212,616
  (rel. err 1×10⁻⁷).
- Byte-reproducible: two offline regenerations of `projection_factors.csv` and two
  `build_dashboard.py` runs → identical md5.

## Honesty caveats (repeated in the panel itself)

- **Projection = replaying 1999–2026 history, not predicting.** ~1,000 windows per horizon
  drawn from one 27-yr macro path, heavily overlapping at long horizons; no completed 18-yr
  window contains a full dot-com-style QQQ round trip. Concentration risk is *not disproven*,
  not absent.
- Nominal USD, **pre-tax** — Sprint 3 puts PIE/FIF tax at a ~1.4–2.0%/yr left-shift of the
  whole distribution.
- Total invested is always shown next to the percentiles; when **p10 < money put in** the
  panel says so in red (short horizons trigger it: at 1–3 yr, ≥1-in-10 historical windows
  ended below the deposits).
- The end-numbers hide the ride: median-window balance drawdowns of ~39% (baby QQQ) and
  ~34% (wife SPY), worst-decile ~44–47%, sit inside these paths.
