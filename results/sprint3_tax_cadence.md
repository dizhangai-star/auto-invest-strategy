# After-tax layer + cadence for the Wife decision — Sprint 3

Makes the wife's PIE choice a *fair* comparison and settles contribution cadence, then states
the real downside plainly. SPY is the stand-in for a NZ S&P 500 PIE fund's underlying index.
Distribution-aware: the tax overlays are applied to the **1,000 random 10-yr windows** from
Sprint 1 (seed 42), not one lucky start. Total-return, USD, then tax as a labelled layer.

- **Reproduce:** `python3 backtest.py` (deterministic; offline `data/SPY.csv`, `data/QQQ.csv`
  fallback reproduces these exactly).
- **FDR = an asset-based drag.** NZ taxes foreign equity by the *fair dividend rate*: deemed
  income = **5% of the opening balance** each year, taxed at your rate — **independent of the
  actual return**. That is exactly an extra expense ratio of `rate × 5%`/yr on the balance, so
  it is modelled by deflating the total-return path by `exp(-rate×5% × t)` and re-reading the XIRR.

## Task 1 — after-tax: PIE (28% cap) vs a direct FIF hold

| Wife SPY, 10-yr windows | net XIRR p10 | p50 | p90 | tax drag / yr |
|-------------------------|--------------|-----|-----|---------------|
| gross (pre-tax) | 2.2% | **10.7%** | 14.7% | — |
| **PIE @28%** (no FIF/FX) | 0.8% | **9.2%** | 13.2% | 1.40% |
| direct FIF @33% + 0.5% FX | 0.5% | 8.8% | 12.8% | 1.65% |
| direct FIF @39% + 0.5% FX | 0.2% | 8.5% | 12.5% | 1.95% |

The tax is a **left-shift of the whole distribution by ~1.4–2.0%/yr**, not a change of shape —
FDR doesn't care how the market did. The **PIE's edge over a direct hold is small**: the 28%
cap saves only the rate gap × 5% = **0.25%/yr (vs 33%) to 0.55%/yr (vs 39%)**, plus it avoids
the **0.5% FX** per contribution and the **FIF $50k-threshold stacking** (the account owner is
already at that threshold in their own name — the whole reason the wife uses a PIE). The big
number is the tax *level* (~1.4%/yr), shared by any wrapper; the PIE just trims it and removes
the friction. **Two honesty caveats:** FDR taxes a *deemed* 5%, not your gain — **light** when
the market runs hot (you're taxed on 5% while it returns 15%), but **still due in a flat year**.
A direct holder may elect the **comparative-value (CV)** method to pay ~0 in a loss year; a
**PIE cannot** — a small structural cost of the wrapper in bad years.

## Task 2 — cadence: weekly vs monthly DCA (same $/yr)

| Same annual $ | weekly XIRR | monthly XIRR | weekly edge / yr |
|---------------|-------------|--------------|------------------|
| SPY | 11.3% (6.04x) | 11.3% (6.04x) | +0.034% |
| QQQ | 15.2% (12.03x) | 15.1% (12.02x) | +0.039% |

The Hatch FX fee is **0.5% per dollar converted, not per trade**, so buying weekly vs monthly
does **not** change total FX cost — the whole "more fee events" worry is a non-issue. The only
difference is timing: weekly puts money in ~2 weeks sooner on average, worth a **negligible
~0.03–0.04%/yr**. **Pick the cadence that fits cashflow; fees don't decide it.**

## Task 3 — the wife's real downside (cash → equities, not a yield swap)

- **Lump-sum sequence risk:** worst 12-mo SPY total return **−47.4%** (to 2009-03-05). A
  **$20,000** lump entering just before that is worth **$10,529** a year on.
- **Worst peak→trough (buy & hold):** **−55.2%** (2007-10-09 → 2009-03-09), **3.4 yr** to recover.
- **Accumulation balance** over the 10-yr windows fell **−33.9%** (median window) to **−46.7%**
  (worst decile) at its trough — the drawdown she'd actually watch in the account.

A Term PIE **cannot lose her capital**; SPY **can halve**. Moving the term deposit into equities
is a **change in risk level**, not a higher-yield savings swap — and FDR still charges tax in the
down years. The equity premium (the ~9%/yr median net XIRR above) is the pay for bearing that
risk: real, but not free. State the halving, not just the average.

## Takeaway for the Wife decision

The **PIE is the right wrapper** — it caps tax at 28%, kills the 0.5% FX, and sidesteps the FIF
threshold — but its edge over a hypothetical direct hold is a modest **0.25–0.55%/yr**; the tax
*level* (~1.4%/yr, return-independent) is the real cost either way. **Cadence is a wash** — weekly
or monthly, whatever suits cashflow. The decision that actually matters is **risk, not fees**:
this is cash → equities, with a **~50% drawdown** on the table and a **multi-year** recovery. Size
the lump so a halving is survivable; the monthly adds then buy the recovery at a discount.

Plot: `results/sprint3_tax_cadence.png` (top: net-XIRR distribution shifting left with tax;
bottom: SPY rolling 12-mo return with the −47% cash→equities downside shaded).
