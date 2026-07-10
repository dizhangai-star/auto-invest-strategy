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
build_dashboard.py # Plotly dashboard from committed results/*.csv + data/*.csv (offline; re-simulates nothing)
requirements.txt   # pandas, numpy, yfinance, matplotlib, plotly
README.md          # run instructions + caveats
data/              # optional offline CSV fallback (data/SPY.csv, data/QQQ.csv)
results/           # per-sprint snapshots: <name>.md (numbers + honesty caveats) + <name>.png
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

Optional remaining candidate: add Sprint 3's after-tax overlay to the interactive
dashboard if the static report section proves insufficient.

## Working style

Direct, data-driven, concise. Show the numbers and the code. Prefer a small correct result
now over a large speculative one. Push back when the evidence warrants it.
