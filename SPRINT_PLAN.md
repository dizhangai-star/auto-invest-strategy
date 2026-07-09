# Sprint Plan — ETF Backtest & DCA Analysis

Goal of the whole effort: give two **real NZ household decisions** an honest,
distribution-aware evidence base — not a single flattering backtest line.

- **Baby** — weekly DCA into QQQM (Nasdaq-100), ~18 yr, Hatch Kids, 0.5% FX/contribution.
- **Wife** — lump + monthly DCA into a NZ S&P 500 PIE (SPY proxy), cash→equities, PIE tax.

Every sprint below must end with an output that changes/confirms one of these two decisions.

---

## Sprint 0 — Baseline verified (mostly built)

`backtest.py` already computes per-ticker metrics, period-bias CAGR table, two DCA
scenarios (XIRR + multiple), and growth/drawdown plots. This sprint just **proves it runs
on real data** and locks a reference output.

**Tasks**
1. Run `python backtest.py` locally (needs open internet for yfinance). → verify: prints
   full common-history window SPY 1999→today, no NaNs, plot saved.
2. Snapshot the baseline numbers into `results/baseline.md` (CAGR, MaxDD, both XIRRs).
   → verify: QQQ MaxDD shows the ~-83% dot-com fall and its recovery years (sanity check
   the engine isn't hiding the risk).
3. Save real total-return CSVs to `data/SPY.csv`, `data/QQQ.csv` so the sandbox/CI can run
   offline. → verify: `backtest.py` reproduces same numbers with network off.

**Done when:** one committed reference run exists that anyone can reproduce offline.

---

## Sprint 1 — Randomized-window distribution study  *(highest value; do first)*

The point of the whole project (CLAUDE.md principle #3). Replace single-start-date CAGR
with the **spread of outcomes** over many overlapping/random windows.

**Tasks**
1. Add `simulate_random_windows(prices, ticker, years, freq, n)` — sample N random start
   dates, run the DCA sim over each `years`-long window, collect final multiple + XIRR.
2. Baby config: 18-yr weekly-DCA windows, QQQ vs SPY. Wife config: ~10-yr lump+monthly.
   → verify: N=1000, deterministic under a fixed `--seed`.
3. Report **distribution, not a point**: p10 / p50 / p90 XIRR and multiple, % of windows
   where QQQ beats SPY, worst-window drawdown during the accumulation.
4. Plot: histogram / violin of XIRR for QQQ vs SPY, both scenarios.

**Done when:** we can state, e.g., "over 1000 random 18-yr paths, QQQ beat SPY in X% of
them, but the bottom decile was Y% worse" — the concentration-risk answer with numbers.

---

## Sprint 2 — Real-world overlays for the *Baby* decision

Make the baby's actual instrument and currency exposure honest.

**Tasks**
1. Add `QQQM` and `VOO` to the ticker set; confirm they track QQQ/SPY since ~2020 (tracking
   diff should be tiny, ≈ TER gap). → verify: annualized tracking error < ~0.1%.
2. NZDUSD overlay: pull `NZDUSD=X`, convert the USD DCA path to NZD. → verify: report the
   NZD-vs-USD XIRR gap so the unhedged FX variance is a labelled layer, not silent.
3. Fold the 0.5% platform FX/contribution explicitly (already in engine) and show its drag
   over 18 yr of weekly buys.

**Done when:** the baby scenario is reportable in NZD, net of FX fee, with QQQM (not QQQ)
as the instrument, and we know the currency swing's size.

---

## Sprint 3 — After-tax layer + fee sensitivity for the *Wife* decision

Make the PIE-vs-alternative comparison fair, and settle contribution cadence.

**Tasks**
1. After-tax layer: PIE (28% PIR cap, no FIF/FX) vs a hypothetical direct-hold under FIF
   FDR (deemed 5%). → verify: apply as a clearly-labelled overlay on the same pre-tax path;
   show both net XIRRs.
2. Fee/cadence sensitivity: weekly vs monthly DCA — trade off more FX-fee events vs fewer,
   larger buys. → verify: quantify the annual drag difference.
3. Frame the wife's downside explicitly (CLAUDE.md #6): worst 12-mo drawdown from the
   lump-sum entry, sequence risk on the monthly adds.

**Done when:** wife's decision doc shows net-of-tax outcomes and states the real downside
(a cash→equities risk change), not just an expected return.

---

## Reporting & hosting — `build_report.py` → `results/index.html`

A single HTML page presents the whole study; it is the shareable artifact for the two
household decisions.

- **`build_report.py`** is a *tiny, separate* script (stdlib only) that stitches the
  committed `results/*.md` + `*.png` into one self-contained `results/index.html` (PNGs
  base64-embedded → portable, opens offline). It computes **no numbers** — the engine
  (`backtest.py`) owns those — so the page can never drift from the reference snapshots.
- **Contract:** each sprint drops a `results/<name>.md` (+ optional `<name>.png`) and adds
  one line to `SECTIONS` in `build_report.py`. Honesty caveats live in the markdown, so they
  carry into the page for free.
- **Regenerate:** `python backtest.py && python build_report.py`.
- **Host:** publish `results/index.html` via **GitHub Pages** (repo already on GitHub).
  Point Pages at `/results` on `main` (or copy to `/docs`); the page is static and
  self-contained, so no build step is needed on the Pages side.

**Done when:** `results/index.html` renders every sprint's section + chart and is reachable
at the Pages URL.

## Cross-cutting rules (from CLAUDE.md — non-negotiable)

- Total-return prices only; XIRR is the headline for DCA, CAGR reported alongside with the gap explained.
- Never a single start date. Currency + tax are explicit overlays, never baked in silently.
- Don't double-count TER (it's in NAV); only extra cost is platform FX.
- Be honest, not reassuring — if the data undercuts QQQ concentration, say so.

## Sequencing & priority

`Sprint 0 → Sprint 1` first (distribution is the core insight). Sprint 2 and 3 are
independent and can follow in either order, driven by which decision needs answering sooner.

## Repo

Remote: https://github.com/dizhangai-star/auto-invest-strategy.git
Git initialized and v0 (`backtest.py`, `README.md`, `requirements.txt`, both `CLAUDE.md`)
plus this plan committed and pushed to `main`.

## Next session

Real work starts in a **fresh session** to keep context clean. Begin at **Sprint 0**:
run `backtest.py` on real data, snapshot `results/baseline.md`, save offline CSVs — then
proceed to the Sprint 1 randomized-window study.
