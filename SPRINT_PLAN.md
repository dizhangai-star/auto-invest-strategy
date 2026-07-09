# Sprint Plan — ETF Backtest & DCA Analysis

Goal of the whole effort: give two **real NZ household decisions** an honest,
distribution-aware evidence base — not a single flattering backtest line.

- **Baby** — weekly DCA into QQQM (Nasdaq-100), ~18 yr, Hatch Kids, 0.5% FX/contribution.
- **Wife** — lump + monthly DCA into a NZ S&P 500 PIE (SPY proxy), cash→equities, PIE tax.

Every sprint below must end with an output that changes/confirms one of these two decisions.

---

## Sprint 0 — Baseline verified  ✅ SHIPPED

`backtest.py` already computes per-ticker metrics, period-bias CAGR table, two DCA
scenarios (XIRR + multiple), and growth/drawdown plots. This sprint just **proves it runs
on real data** and locks a reference output.

**Status:** all three tasks done and committed (`9496a66`). Offline CSV fallback re-verified
to reproduce `results/baseline.md` exactly (window 1999-03-10 → 2026-07-08, 6874 days, 0 NaNs;
QQQ −83.0% / 12.4-yr recovery present; both DCA XIRRs match). `backtest_charts.png` is
intentionally gitignored (regenerated, not committed).

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

## Sprint 1 — Randomized-window distribution study  ✅ done (incl. task 5, validated)

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
5. **Persist per-window results** (final multiple, XIRR, p10/p50/p90 wealth trajectories) to
   `results/windows_<ticker>.csv` — structured, not just a PNG. This is the **data contract**
   the later dashboard (Sprint 4) reads; it must never re-simulate.
   → done: `persist_window_data()` writes, per scenario × ticker,
   `results/windows_<scenario>_<ticker>.csv` (one row per window: multiple, XIRR, max_dd) and
   `results/fan_<scenario>_<ticker>.csv` (p10/p50/p90 wealth-multiple vs elapsed years, for the
   Sprint 4 percentile fan). **Regenerate the committed reference with network off** (live
   yfinance re-adjusts and shifts the numbers) — same offline convention as `baseline.md`.
   → **validated (2026-07): offline regeneration is byte-identical to the committed CSVs, and
   `windows_*.csv` ties out exactly to `random_windows.md` (XIRR p10/p50/p90 + multiples,
   win-rates 100%/96.4%), 0 NaNs.** Note for Sprint 4: the fan's terminal p50 is a hair below
   `windows.csv` multiple p50 by design (cross-window percentile per elapsed step, truncated to
   the shortest window) — don't try to reconcile the gap.

**Done when:** we can state, e.g., "over 1000 random 18-yr paths, QQQ beat SPY in X% of
them, but the bottom decile was Y% worse" — the concentration-risk answer with numbers.

**Result** (`results/random_windows.md`, `python3 backtest.py && python3 build_report.py`):
over 1000 random 18-yr weekly-DCA paths (seed 42) QQQ beat SPY in **100%**, median XIRR
16.6% vs 11.3%. **But** that 100% is a *sample-length artifact* — 27 yr of history allows only
~9 yr of distinct 18-yr starts, so the "windows" heavily overlap one macro path; no completed
18-yr window since 1999 has punished QQQ's concentration. Treat concentration risk as *not
disproven*, not absent. Wife's 10-yr study (more distinct starts) shows the honest downside:
SPY XIRR p10 falls to 2.2%, and both scenarios put a ~40–47% balance drawdown on the table.

---

## Sprint 2 — Real-world overlays for the *Baby* decision  ✅ SHIPPED

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

**Result** (`results/sprint2_overlays.md`, `python3 backtest.py && python3 build_report.py`):
QQQM tracks QQQ to **+0.06%/yr** and VOO tracks SPY to **+0.04%/yr** — the cheaper share class is
ahead by ≈ its TER edge (daily "TE" ~0.9% is mean-reverting print noise, autocorr −0.53, that
washes out). Using **QQQM is free money**. The 0.5% Hatch FX fee is a flat **0.50% of terminal
wealth (horizon-independent), ~0.03%/yr** XIRR — negligible. The one real overlay is **currency**:
the unhedged NZDUSD (2003-12→now, range **0.49–0.88**, ~**12%/yr** vol) added +1.5%/yr *in this
window only because the NZD fell* — backward-looking luck that cuts both ways over the baby's 18 yr.
New data: `data/QQQM.csv`, `data/VOO.csv`, `data/NZDUSD=X.csv` (offline fallback reproduces exactly).

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

## Sprint 4 — Interactive dashboard  *(deferred; off critical path)*

A **communication / intuition layer**, not new evidence. It *reads* the outputs of Sprints
1–3 (via the Sprint 1 data contract) and never re-simulates. Built only after the research
core is static and stable. Detailed scoping in `~/.claude/plans/second-thing-that-i-typed-panda.md`.

**Library decision (researched — don't rebuild the wheel):** no off-the-shelf backtest lib
models our core unit (distribution across randomized windows), so no heavyweight framework.
Reject **vectorbt** (now OSS maintenance-mode; engine around a single-path object). Use
**Plotly** as the rendering layer → single self-contained `results/dashboard.html`
(`include_plotlyjs=True`, opens offline, versions like the PNG); optionally borrow
**QuantStats** for the boilerplate distribution/drawdown tearsheet. Streamlit/Dash rejected
(need a running server; break the committed-reproducible-artifact model).

**Tasks**
1. **Outcome distribution** (lead view) — Plotly histogram/violin of XIRR & multiple, QQQ vs
   SPY, per scenario.
2. **Percentile fan** — filled p10–p90 band + p50 line from the window trajectories. Keeps
   the distribution, not one line, front-and-center.
3. **Bull/bear cycles** — `add_vrect` shaded spans from the engine's existing drawdown cycles
   (e.g. QQQ −83% dot-com span, 12.4-yr recovery). Reuse `backtest.py` drawdown logic; don't
   re-detect regimes.
4. **Orders on chart** — DCA-buy markers on a single price path, **labelled as one illustrative
   path** (CLAUDE.md #3). Secondary section, never the landing view.

**Done when:** a committed self-contained `results/dashboard.html` renders all four views with
network off, and its numbers match the committed `results/` tables/CSVs exactly (no divergent
recompute). Guardrail: lead with the distribution; the single-path view stays clearly secondary.

---

## Reporting & hosting — `build_report.py` → `docs/index.html` (GitHub Pages)

The **always-current lightweight report** (distinct from Sprint 4's richer interactive
dashboard): a single static HTML page that *stitches* the committed snapshots, live from
Sprint 1 onward. Sprint 4's `results/dashboard.html` is the deferred interactive layer; this
`docs/index.html` is the zero-dependency page we can publish today.

- **`build_report.py`** is a *tiny, separate* script (stdlib only) that stitches the
  committed `results/*.md` + `*.png` into one self-contained `docs/index.html` (PNGs
  base64-embedded → portable, opens offline). It computes **no numbers** — the engine
  (`backtest.py`) owns those — so the page can never drift from the reference snapshots.
- **Contract:** each sprint drops a `results/<name>.md` (+ optional `<name>.png`) and adds
  one line to `SECTIONS` in `build_report.py`. Honesty caveats live in the markdown, so they
  carry into the page for free.
- **Regenerate:** `python3 backtest.py && python3 build_report.py`.
- **Host:** **GitHub Pages**, source = **`main` branch, `/docs` folder** (Settings → Pages).
  The page is static and self-contained, so no Pages build step is needed. One-time repo
  setting; after that every `build_report.py` commit updates the live page.

**Done when:** Pages is enabled on `/docs` and `docs/index.html` renders every sprint's
section + chart at the published URL.

## Cross-cutting rules (from CLAUDE.md — non-negotiable)

- Total-return prices only; XIRR is the headline for DCA, CAGR reported alongside with the gap explained.
- Never a single start date. Currency + tax are explicit overlays, never baked in silently.
- Don't double-count TER (it's in NAV); only extra cost is platform FX.
- Be honest, not reassuring — if the data undercuts QQQ concentration, say so.

## Engine gotchas (learned in-sprint)

- **Adding a ticker ≠ adding to `TICKERS`.** `load_prices([...])` ends with a cross-ticker
  `dropna` that collapses the frame to the *shortest* history's start (QQQM ⇒ 2020, silently).
  To use a fund on its own full history, load it alone via `load_series(ticker)` (Sprint 2).
- **Offline CSV name = yfinance symbol verbatim**, incl. FX: `data/NZDUSD=X.csv` (bare `NZDUSD`
  404s on Yahoo). Keeps the online and offline branches on one string.
- **Committed PNGs aren't byte-reproducible** (matplotlib) — a rerun churns them. Only commit the
  PNG for the sprint you changed; `git checkout -- results/<other>.png` drops spurious diffs.
- **"Tracking diff" vs "tracking error":** the decision number is the annualized *total-return
  gap* (≈TER, <0.1%); the daily return-diff std (~0.9%/yr) is mean-reverting print noise. Lead
  with the gap.

## Sequencing & priority

`Sprint 0 → Sprint 1` first (distribution is the core insight). Sprint 2 and 3 are
independent and can follow in either order, driven by which decision needs answering sooner.

## Repo

Remote: https://github.com/dizhangai-star/auto-invest-strategy.git
Git initialized and v0 (`backtest.py`, `README.md`, `requirements.txt`, both `CLAUDE.md`)
plus this plan committed and pushed to `main`.

## Next session

Sprint 0 is shipped; **Sprint 1 is done** (distribution study + `results/random_windows.md`,
plus the task-5 CSV data contract `results/{windows,fan}_*.csv`) and the report pipeline
(`build_report.py` → `docs/index.html`) is in place. Next, in a **fresh session**:

- **One-time:** enable GitHub Pages (Settings → Pages → source `main` / `/docs`) so
  `docs/index.html` goes live; push `main` first.
- **Sprint 2 is shipped** (baby: QQQM/VOO tracking + NZDUSD overlay + FX-fee drag →
  `results/sprint2_overlays.md/.png`). Next is **Sprint 3** (wife: after-tax PIE-vs-FIF +
  fee/cadence) — the remaining decision-driving sprint.
- Per-sprint contract: drop `results/<name>.md` (+ `.png`), add a line to `SECTIONS` in
  `build_report.py`, rerun both scripts.
