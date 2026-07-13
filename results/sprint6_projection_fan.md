# Sprint 6 — Projection fan graph (Calculator tab)

**Question it answers:** "what would the journey look like along the way?" — the Sprint 5
calculator gave the endpoint range only; this adds a **fan chart of projected portfolio value
vs elapsed years** (p10–p90 band, p50 line, and a dotted "money put in" line), driven by the
same inputs (deposit, cadence, lump, FX fee, QQQ/SPY mix, horizon).

## How it works (engine stays the sole source of numbers)

No new data and no engine change. `results/projection_factors.csv` already holds per-window
`(g0, s, n_buys)` for **every integer horizon 1..18 yr** × {weekly, monthly} × 1,000 random
start dates (seed 42), all embedded in the dashboard since Sprint 5. The fan is the same
linear-combination + percentile computation the endpoint stats already use, run once per
year on the grid:

```
value_y(window i) = (1 − fx_fee) · [ lump · g0ᵢ(y) + amount · sᵢ(y) ]   for y = 1..H
fan(y) = percentile over the 1,000 windows at horizon y;  year 0 = (1 − fee)·lump
```

The per-horizon block was factored into one JS helper (`horizonStats`); the endpoint stat
row, histogram, and fan all call it, so they **cannot disagree by construction**. The
"money put in" line is `lump + amount · median n_buys(y)`.

## Self-checks and tie-outs (all verified in a real browser)

- **Fan endpoint ≡ stat row, exactly** (same cells, same code path): baby preset fan ends at
  p10/p50/p90 = **$331,024 / $503,300 / $631,093**, identical to the stat row; wife preset
  $92,278 / $161,390 / $210,352 likewise.
- **Baby p50 multiple 5.35×** at 18-yr weekly still ties out to `random_windows.md`
  (Sprint 1, same seed ⇒ identical windows).
- **Year-0 anchor**: wife preset fan starts at $20,000 = the lump (fee 0), "put in" line
  starts at the lump for both presets.
- Fan has H+1 points (year 0..H): 19 for the baby preset, 11 for the wife preset; horizons
  entered in weeks/months snap to the same 1–18 yr grid as before.
- Byte-reproducible: two `build_dashboard.py` runs → identical md5 (`results/` and `docs/`
  copies identical). Mobile (375 px): no horizontal overflow, fan resizes into the panel.

## Honesty caveats (repeated in the panel itself)

- **The fan is not a path.** Each year's p10/p50/p90 comes from its own ~1,000 independent
  historical start dates — the p50 line is not a trajectory anyone actually rode (same
  construction as the Percentile fan view). Real single paths wobble across the band;
  the smooth line *understates* the ride.
- A true within-window trajectory (value at each contribution date) would need new per-step
  data from `backtest.py`; rejected (as in Sprint 5) to keep the JS from becoming a second
  simulation engine. The cross-window fan is the zero-engine-change honest equivalent.
- All Sprint 5 caveats carry over: replaying 1999–2026 history (not predicting), nominal
  USD pre-tax, drawdowns of ~34–47% sit *inside* these smooth-looking bands.
