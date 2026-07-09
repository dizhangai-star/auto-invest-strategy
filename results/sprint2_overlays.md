# Real-world overlays for the Baby decision — Sprint 2

Makes the baby's *actual* instrument and currency exposure honest: the cheaper share class
(**QQQM**, not QQQ), the unhedged **NZD/USD** swing on a US-listed ETF, and the **0.5% Hatch
platform FX fee** per contribution. Total-return prices, USD unless a leg is labelled NZD.

- **Data:** `data/QQQM.csv` (2020-10-13→), `data/VOO.csv` (2010-09-09→), `data/NZDUSD=X.csv`
  (2003-12-01→, USD per 1 NZD), plus the Sprint 0/1 `data/SPY.csv`, `data/QQQ.csv`.
- **Reproduce:** `python3 backtest.py` (deterministic; offline CSV fallback reproduces these exactly).
- Each series is loaded on its **own full history** — QQQM/VOO/FX are *not* force-aligned into
  one frame (the common-window `dropna` would collapse everything to QQQM's 2020 inception).

## Task 1 — do the cheaper share classes track their long-history twins?

The **tracking difference** (annualized total-return gap) is the number that matters over a hold —
not the noisier daily "tracking error".

| Cheaper vs twin | Overlap | Tracking diff / yr | CAGR (cheaper vs twin) | Daily corr | Daily TE / yr |
|-----------------|---------|--------------------|------------------------|-----------|---------------|
| QQQM vs QQQ | 2020-10 → 2026-07 (5.7 yr) | **+0.06%** | 17.4% vs 17.3% | 0.9992 | 0.90% |
| VOO vs SPY | 2010-09 → 2026-07 (15.8 yr) | **+0.04%** | 14.9% vs 14.8% | 0.9985 | 0.93% |

The cheaper share class is fractionally **ahead**, by ≈ its **TER edge** (QQQM 0.15% vs QQQ 0.20%
= 5 bp; VOO 0.03% vs SPY 0.09% ≈ 6 bp). The larger daily "TE" (~0.9%/yr) is **mean-reverting**
close-print / dividend-timing noise (return-difference autocorrelation −0.53; the biggest daily
gaps reverse the next day) — it washes out to the tiny tracking difference above. **Verdict:
QQQM is a faithful, cheaper twin of QQQ. Using it (not QQQ) for the baby is free money.**

## Task 2 — NZDUSD overlay: the unhedged currency layer

Same weekly-$100 DCA into QQQ, valued two ways: contributions as **USD** vs the same nominal as
**NZD** converted to USD at each buy's spot. Run over the FX-data window (2003-12 → 2026-07, 22.6 yr).

| Leg | XIRR | NZDUSD 2003-12 → 2026-07 | FX annualized vol | Net USD-vs-NZD drift |
|-----|------|--------------------------|-------------------|----------------------|
| USD terms | 17.5% | 0.6443 → 0.5677 (range 0.49–0.88) | 12.3% | +0.6% / yr |
| NZD terms | **19.0%** | | | |

**FX contribution: +1.5%/yr** here — but that sign is **backward-looking luck**: the NZD *fell*
vs USD over this window, so a USD asset was worth more in NZD. Unhedged, the ~**12%/yr** currency
volatility (NZDUSD ranged **0.49–0.88**) cuts **both** ways over the baby's 18 yr. This is a real
extra source of variance layered on top of the equity risk — labelled here, never silent.

## Task 3 — the 0.5% platform FX fee per contribution

| Baby weekly DCA into QQQ (1,427 buys, $142,700 invested) | Terminal | XIRR |
|----------------------------------------------------------|----------|------|
| with 0.5% Hatch FX fee | $1,716,055 | 15.2% |
| no fee | $1,724,678 | 15.2% |

The fee is a flat **0.5% haircut on every dollar contributed**, so it costs **exactly 0.50% of
terminal wealth regardless of horizon** ($8,623 here) and only **~0.03%/yr** of XIRR. It is
**small and predictable** — the FX *rate* swing (Task 2) dwarfs the FX *fee*.

## Takeaway for the Baby decision

Instrument choice is settled and cheap: **QQQM** tracks QQQ to within its fee edge, and Hatch's
0.5% FX fee is a negligible ~0.03%/yr drag. The one real, unavoidable overlay is **currency**:
holding a US-listed ETF adds ~12%/yr of unhedged NZD/USD volatility on top of the Nasdaq-100's
own (already large — see Sprint 1's ~40–47% accumulation drawdowns). The recent NZD weakness
flattered NZD returns; **do not** bank on that continuing.

Plot: `results/sprint2_overlays.png` (top: cumulative return ratio of each twin ≈1.0; bottom: NZDUSD=X).
