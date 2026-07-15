# CLAUDE.md — ETF Backtest & DCA Analysis

Context for Claude Code. Read this first; it defines what we're deciding and the
methodology standards that keep the analysis honest.

## Purpose

Build intuition and evidence for two **real, live investment decisions** for a NZ household —
not a generic US backtest. Every output should tie back to one of the two setups below.
The goal is understanding the *distribution and risk* of outcomes, not producing a single
flattering return number.

## The two decisions this informs

**1. Baby (long horizon, ~18 yr) — QQQ / Nasdaq-100**
- Weekly DCA into **QQQM** (same index as QQQ, 0.15% vs 0.20% TER, built for buy-and-hold).
- Held in the **child's name via a Hatch Kids Account** → the child gets her own FIF
  threshold, so a direct US ETF is fine here.
- There is **no NZ-PIE Nasdaq-100 fund**, so this must be the actual US-listed ETF.
- Cost that applies: **0.5% platform FX per contribution** (Hatch). Brokerage is free on
  Hatch Kids auto-invest.
- Open question to pressure-test: is the extra concentration/volatility of the Nasdaq-100
  worth it vs the S&P 500 over an 18-yr DCA? Show both sides with data.

**2. Wife (switch from a Term PIE) — S&P 500**
- Lump sum + monthly DCA into a **NZ S&P 500 PIE fund** (Kernel S&P 500 @ 0.25%, or
  Smartshares USF @ 0.34%). SPY is the modelling stand-in for the underlying index.
- PIE → **no FIF, no FX, tax capped at 28% PIR**, held in her own name.
- Critical framing: this is **cash → equities**, a real change in risk level, not a
  higher-yield savings swap. Analysis must make the downside (drawdown, sequence risk)
  explicit, not bury it.

## NZ domain context (do not give generic US-centric advice)

- **FIF** (Foreign Investment Fund): direct offshore shares over **NZ$50k cost basis**
  (per taxpayer, aggregated across all accounts) are taxed on a deemed 5% return (FDR).
  The account owner already holds direct US ETFs near/over this threshold in their own name
  via IBKR — which is *why* the baby's holding goes in the child's name and the wife's uses
  a PIE.
- **PIE** funds sidestep FIF entirely and cap tax at 28%. Trade-off is a higher fund TER.
- Platforms in scope: **Hatch Kids** (baby), **Kernel / InvestNow** (wife). IBKR is
  excluded on purpose (cheapest, but can't give the kids structure and stacks FIF).

## Analytical principles (non-negotiable)

1. **Total return.** Always use adjusted/total-return prices (dividends reinvested).
2. **XIRR for DCA.** Money-weighted return is the honest metric for drip-feeding, not the
   buy-and-hold CAGR. Report both and explain the gap.
3. **Expose period bias.** Never present a single start date. QQQ's edge over SPY is
   window-dependent (it fell ~83% in 2000–02, ~15 yr to recover). Report multiple windows
   and, ideally, a **randomized-start-date distribution** (e.g. 1,000 random 18-yr paths) so
   we see the spread of outcomes, not one lucky/unlucky line.
4. **Don't double-count fees.** ETF TER is already inside the price (NAV is net of fees).
   The only *extra* modelled cost is platform FX per contribution (0 for PIE funds).
5. **Currency and tax are explicit overlays, never silent.** Base sims are USD, pre-tax.
   NZD/USD (unhedged) and PIE/FIF tax are added as clearly-labelled layers when relevant.
6. **Be honest, not reassuring.** Surface drawdowns, recovery times, and worst-case paths
   plainly. If the data undercuts the plan (e.g. QQQ's concentration risk), say so directly
   and challenge the assumption rather than confirming it.

## Project structure

```
backtest.py        # engine: data load, metrics, XIRR, DCA sims, period-bias, plots
build_report.py    # stdlib-only: stitch results/*.md + *.png -> docs/index.html (computes no numbers)
build_dashboard.py # Plotly dashboard from committed results/*.csv + data/*.csv (offline; re-simulates
                   #   nothing — calculator JS only linearly combines committed factors, never simulates)
requirements.txt   # pandas, numpy, yfinance, matplotlib, plotly
README.md          # run instructions + caveats
data/              # optional offline CSV fallback (data/SPY.csv, data/QQQ.csv)
results/           # per-sprint snapshots (<name>.md + .png) + committed dashboard data-contract
                   #   CSVs (windows_*, fan_*, projection_factors.csv) — regenerate network-off
docs/              # generated index.html for GitHub Pages (source: main /docs) — do not hand-edit
```

All tunables live in the `CONFIG` block at the top of `backtest.py`.

## Run

```bash
pip install -r requirements.txt
python3 backtest.py          # use python3 — `python` is not on PATH on this machine
python3 build_report.py      # stitch results/*.md + *.png -> docs/index.html (GitHub Pages)
python3 build_dashboard.py   # results/dashboard.html (+ docs/ copy) from committed CSVs — no network needed
```

`yfinance` needs open internet (works locally; the Claude web sandbox can't reach Yahoo).

To verify the offline CSV fallback reproduces `results/baseline.md` (no network): stub
`yfinance` so `yf.download` raises, which forces the `data/*.csv` branch in `load_prices`.

To verify `dashboard.html` in a browser tool: serve it (`python3 -m http.server` in
`results/`) — Playwright/preview tools block `file://` URLs.

**Reproducibility — regenerate committed reference artifacts (`results/*.md`, `*.csv`) with
the network OFF.** Live yfinance re-adjusts adjusted-close between calls, so same-seed runs
drift (same date range, subtly different numbers) — not byte-reproducible. The committed
reference is always the offline (`data/*.csv`) one; a live `python3 backtest.py` will show
`results/` as modified, which is expected, not a real change.

## Out of scope for now (flagged, not hidden)

- Sequence-of-returns / withdrawal phase — this is accumulation only. Becomes relevant
  within ~5 yr of the baby's 18-yr horizon.

## Roadmap — ✅ all shipped (see SPRINT_PLAN.md for results)

1. ✅ Randomized-window study → outcome distributions (Sprint 1).
2. ✅ QQQM + VOO tracking check (Sprint 2 — QQQM ahead by ≈ its TER edge; use QQQM).
3. ✅ NZDUSD overlay for the baby scenario (Sprint 2).
4. ✅ After-tax layer: PIE 28% vs FIF FDR (Sprint 3).
5. ✅ Fee sensitivity: weekly vs monthly DCA (Sprint 3 — a wash, ~0.03%/yr).
6. ✅ Projection calculator — its own dashboard tab, client-side p10/p50/p90 from
   `results/projection_factors.csv` (Sprint 5; dashboard restructured to a left-sidebar
   tabbed layout in Sprint 5b).
7. ✅ Projection fan graph — calculator tab, p10/p50/p90 value vs elapsed years from the
   same factors, no engine change (Sprint 6).
8. ✅ Real-portfolio validation — the user's actual NZ$90k of deposits (2019–2024) vs an
   even weekly DCA into SPY/QQQ, accumulate-then-hold, own dashboard tab reading
   `results/real_vs_dca_*.csv` (Sprint 7).
9. ✅ Buy day-of-week sensitivity (Sprint 8 — Mon–Fri anchors, paired windows: best-vs-worst
   day ≈ 1–3bp/yr vs ~500bp of start-date luck; pick the day that suits your payroll).
   Dashboard tab "Buy day of week" (view7) from `results/weekday_anchor.csv`.
10. ✅ Dip double-down vs plain daily DCA (Sprint 8b — 2x on a ≤−1/−2/−3% day, skip next calm
    day: wins ~every paired window but only +0.1–0.4bp/yr ≈ <0.06% of terminal wealth; not
    worth manual effort). Dashboard tab "Buy the dip" (view8) from `results/dip_double.csv`.
11. ✅ Dip strategy on the REAL scenario (Sprint 9 — same NZ$90k/window deployed daily,
    even vs dip 1/2/3%: added only $40–270 on a $123–150k result, ≤~1bp/yr). Extends the
    "My portfolio vs DCA" tab with a second table from `results/real_dip.csv`.
12. ✅ Cadence variants on the real chart (Sprint 10 — the same NZ$90k/window into SPY/QQQ
    under weekly/daily/dip −3%, all seven series (+ the actual portfolio) on the "My
    portfolio vs DCA" chart & table). Curves overlap into two clusters: cadence moved the
    result ≤~3bp/yr; the SPY-vs-QQQ gap and time-in-market moved it by multiples. Engine adds
    `REAL_STRATEGIES`/`_real_strategy_schedule`; `results/real_vs_dca_*.csv` now carry six
    curves + a keyed summary.
13. ✅ FIF calculator for the baby's account (Sprint 11 — added to the Projection calculator
    tab, below the projection): (a) when cumulative NZD **cost basis** crosses the NZ$50k
    de-minimis (pure arithmetic on deposits — cost, not market value, so buy-only DCA still
    triggers it), and (b) the annual **FDR** tax per NZ tax year once FIF applies (5% of the
    1-April market value at the child's own progressive rates). The per-year opening value is
    the **same p10/p50/p90 window distribution** as the fan — it reuses the projection's global
    `horizonStats`, no second engine — so the tax is a bad-decade/median/lucky-start range.
    Reads the shared deposit/cadence/horizon/lump/FX-fee/mix from the projection form; only
    prior-contributions / threshold / start-date are FIF-specific. No engine or CSV change —
    `fif_section()` in `build_dashboard.py`. Key takeaway surfaced: "buy, never sell" does NOT
    avoid FIF (it's an annual deemed-income tax, not a realisation tax), and the child — not
    Hatch — is the taxpayer (parent files her IR3).

Open: the user's actual per-deposit schedule (date, NZD amount — likely via an IBKR
connector/Flex export) to replace Sprint 7's even-split assumption in `even_nzd_schedule`;
the same numbers feed the calculator's Custom preset. Optional candidate: add Sprint 3's
after-tax overlay to the interactive dashboard if the static report section proves
insufficient.

## Working style

Direct, data-driven, concise. Show the numbers and the code. Prefer a small correct result
now over a large speculative one. Push back when the evidence warrants it.
