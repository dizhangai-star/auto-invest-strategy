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
5. **Persist per-window results** (final multiple, XIRR, p10/p50/p90 wealth trajectories) to
   `results/windows_<ticker>.csv` — structured, not just a PNG. This is the **data contract**
   the later dashboard (Sprint 4) reads; it must never re-simulate.

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

Sprint 0 is shipped. Begin at **Sprint 1** — the randomized-window distribution study
(`simulate_random_windows`, N=1000 deterministic under `--seed`, p10/p50/p90 XIRR & multiple,
% windows QQQ beats SPY). Remember task 5: persist per-window results to
`results/windows_<ticker>.csv` as the data contract for the later dashboard (Sprint 4).
