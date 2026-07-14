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

**Status:** ✅ SHIPPED (`results/sprint3_tax_cadence.md/.png`, `python3 backtest.py && python3 build_report.py`).

**Result:** the tax overlay is applied to the 1,000 random 10-yr windows (not one start).
**FDR = a fixed asset drag** (deemed 5% of opening balance × your rate, return-independent) →
models as an extra expense ratio, shifting the whole net-XIRR distribution left by ~1.4–2.0%/yr.
Wife SPY net-XIRR p50: gross **10.7%** → **PIE @28% 9.2%** (drag 1.40%/yr) → direct FIF @39%+FX
8.5% (1.95%/yr). The **PIE's edge over a direct hold is small** — the rate cap saves only
0.25%/yr (vs 33%) to 0.55%/yr (vs 39%), plus it kills the 0.5% FX and the FIF $50k stacking; the
tax *level* (~1.4%/yr) is the real cost either way. Caveat: FDR is light in hot markets but still
due in flat years, and a PIE can't elect CV to pay ~0 in a loss year (a direct holder can).
**Cadence is a wash** — the FX fee is per-dollar not per-trade, so weekly vs monthly differ by
only ~0.03–0.04%/yr (timing). The decision that matters is **risk, not fees**: worst 12-mo SPY
−47.4%, worst peak→trough −55.2% (3.4-yr recovery), accumulation balance drawdown −33.9% median
to −46.7% worst-decile. This is cash → equities — a change in risk level, stated plainly.

---

## Sprint 4 — Interactive dashboard  ✅ SHIPPED *(communication layer, not new evidence)*

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

**Result** (`build_dashboard.py` → `results/dashboard.html`, copied to `docs/dashboard.html`
for Pages; section `results/sprint4_dashboard.md` added to the report): all four views ship.
Key implementation choices — the script is **offline by construction** (reads only the
committed `results/{windows,fan}_*.csv` + `data/*.csv`, never yfinance), so unlike
`backtest.py` a live rerun cannot drift it; output is **byte-reproducible** (verified: two
runs, identical md5; fixed Plotly `div_id`s). Distribution stats in the page are computed
from the CSVs and tie out to `random_windows.md` exactly (XIRR p10/p50/p90 both scenarios,
win-rates 100%/96.4%, drawdown p10s). Bear spans (QQQ ≤ −20%, engine's dd definition):
dot-com −83% 2000-03→2015-02, 2018 −23%, 2020 −29%, 2022 −35%, 2025 −23%. Verified in a
real browser: all four divs render, only network request is the page itself (self-contained).
QuantStats skipped — nothing it adds that the four custom views don't. Built in parallel with
Sprint 3 (independent: it consumes the Sprint 1 contract only); Sprint 3's after-tax overlay
is a candidate future view, not yet in the dashboard.

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
- **FDR tax = an asset-based drag, not a gains tax.** Deemed income = 5% of opening balance ×
  rate, *independent of return*, so it's exactly an extra expense ratio → model by deflating the
  total-return path `exp(-rate×5%·t)` and re-read the XIRR (Sprint 3 `apply_asset_drag`). The
  deflation level cancels in each buy's growth ratio, so the drag lands over the true holding
  period, not retroactively.
- **`apply_asset_drag` on a frame:** `prices * 1d_array` broadcasts to *columns*, not rows —
  use `prices.mul(deflator, axis=0)` so it works for a Series *and* a DataFrame.
- **Avoid PNG churn on a partial run:** to regenerate just one sprint's artifacts, call that
  sprint's functions in isolation (force offline, `import backtest`, call the fns) rather than
  full `main()`, which re-churns every sprint's non-reproducible matplotlib PNG.

## Sequencing & priority

`Sprint 0 → Sprint 1` first (distribution is the core insight). Sprint 2 and 3 are
independent and can follow in either order, driven by which decision needs answering sooner.

## Repo

Remote: https://github.com/dizhangai-star/auto-invest-strategy.git
Git initialized and v0 (`backtest.py`, `README.md`, `requirements.txt`, both `CLAUDE.md`)
plus this plan committed and pushed to `main`.

## Bottom line so far — the two decisions (Sprints 0–3)

The **research core is complete**: both live decisions now have a distribution-aware, after-fee,
after-tax evidence base. What the numbers say:

**Baby — QQQM / Nasdaq-100, ~18-yr weekly DCA (Hatch Kids).**
- Over 1,000 random 18-yr windows QQQ beat SPY in **100%**, median XIRR **16.6% vs 11.3%** — but
  that 100% is a **sample-length artifact** (27 yr of history ⇒ only ~9 yr of distinct 18-yr
  starts, heavily overlapping one macro path). Concentration risk is **not disproven, just
  untested** here — QQQ's −83% dot-com fall (12.4-yr recovery) sits *inside* every window.
- Instrument/fee questions are **settled and cheap**: QQQM tracks QQQ to **+0.06%/yr** (≈ its TER
  edge — free money vs QQQ); the 0.5% Hatch FX fee is a flat 0.5% of terminal wealth (**~0.03%/yr**).
- The one **real, unavoidable overlay is currency**: unhedged NZDUSD adds ~**12%/yr** of vol; the
  recent NZD weakness flattered NZD returns (+1.5%/yr *in this window only*) — don't bank on it.

**Wife — NZ S&P 500 PIE, lump + monthly DCA (cash → equities).**
- Tax is a **fixed left-shift** of the whole net-XIRR distribution (~1.4–2.0%/yr), return-independent.
  Wife SPY net p50: gross **10.7%** → **PIE @28% 9.2%** → direct FIF @39%+FX 8.5%.
- The **PIE's edge over a direct hold is modest** (rate cap saves 0.25–0.55%/yr, + kills 0.5% FX
  + FIF $50k stacking); the tax *level* (~1.4%/yr) is the real cost either way. **Cadence is a
  wash** (FX fee is per-dollar, not per-trade ⇒ weekly vs monthly differ ~0.03%/yr).
- The decision that matters is **risk, not fees**: worst 12-mo SPY **−47.4%**, worst peak→trough
  **−55.2%** (3.4-yr recovery), accumulation balance drawdown **−33.9%** median to **−46.7%**
  worst-decile. A Term PIE can't lose capital; SPY can halve. Size the lump to survive a halving.

**Cross-cutting methodological wins:** distribution-over-single-date (random windows) is the
project's core honesty lever; overlays (FX, tax) are *always* labelled layers, never baked in;
the offline-CSV reference keeps every committed number byte-reproducible; and the engine owns all
numbers while `build_report.py` only presents them, so the page can't drift.

## Sprint 5 — Projection calculator  ✅ SHIPPED *(its own dashboard tab; engine stays sole source of numbers)*

Answers the forward question ("deposit $X weekly/monthly for N periods → what's the pot?")
for Baby, Wife, and a custom QQQ/SPY mix, as a **p10/p50/p90 range** from the Sprint 1
random-window machinery — plus a clearly-labelled assumed-rate FV as an intuition check.

**Design:** `simulate_dca`'s final value is exactly linear in (lump, amount):
`final = (1−fee)·(lump·g0 + amount·s)` with `g0 = P(end)/P(first buy)`,
`s = P(end)·Σ 1/P(buyᵢ)`. `backtest.py` persists per-window `(g0, s, n_buys)` over
{SPY,QQQ} × {W,MS} × {1..18 yr} × 1,000 windows (seed 42, starts shared across tickers) →
`results/projection_factors.csv` (36,000 rows); `build_dashboard.py` embeds it as JSON and
the panel's JS only does linear combinations + percentiles. Ticker mix = fixed contribution
split, never rebalanced. Week/month horizons snap to the nearest year on the grid (labelled).

**Rejected alternative** (documented so it isn't re-litigated): embedding price arrays +
reciprocal prefix sums for arbitrary fractional horizons — smaller payload, but it makes JS
a second simulation engine with real drift edge cases (partial resample buckets, end-of-window
valuation) vs the "dashboard re-simulates nothing" rule.

**Result:** built-in `np.isclose` contract check per grid cell at regeneration; factor formula
matches `simulate_dca` from the committed CSV to ~7×10⁻⁷ (= `%.6g` rounding); Baby preset ties
out to `random_windows.md` exactly (3.52x/5.35x/6.71x, implied 16.6%/yr = XIRR p50); Wife
preset likewise (1.15x/2.00x/2.61x); a $200/wk 10-yr 50/50 blend hand-checks against a direct
`simulate_dca` loop to 1×10⁻⁷. Both artifacts byte-reproducible (two regenerations, identical
md5); dashboard now 7.5 MB, still fully offline. Verified in a real browser: presets, snap
note, and the red "p10 < money put in" warning all fire. Honesty caveats sit inside the panel
itself (one macro path, pre-tax, drawdowns en route). See `results/sprint5_projection.md`.

## Sprint 5b — Dashboard layout: left-sidebar tabs  ✅ SHIPPED *(readability only, no numbers touched)*

`dashboard.html` restructured from one long scroll into a left-sidebar tabbed layout: five
panels (Outcome distribution / Percentile fan / Projection calculator / Bull/bear cycles /
One path), hash-routed (`#calculator` etc. — back-button and bookmarks work), one panel
visible at a time. Still a single self-contained offline file, Plotly inlined once; the
h1 + honesty-caveat box sit above the panels, visible on every tab (never hidden behind
one). Implementation notes: panels are `display:none` until active, and plots are re-sized
on each activation (Plotly renders at fallback width inside hidden containers); the sidebar
stretches to full page height with a sticky inner nav; `main` is centered via flex auto
margins (reset on mobile, where auto cross-axis margins shrink-wrap and caused overflow);
<800px the sidebar becomes a top link row. Verified in a real browser: tab switching,
full-width plots on first activation, calculator recalc, reload-on-hash, back/forward,
mobile no-overflow. Prose "view N" cross-references replaced with panel names throughout.

## Sprint 6 — Projection fan graph (Calculator tab)  ✅ SHIPPED *(no engine change, no new data)*

The calculator gained a **fan chart of projected value vs elapsed years** (p10–p90 band,
p50 line, dotted "money put in" line) above the endpoint histogram. Zero engine change:
`projection_factors.csv` already carries every integer horizon 1..18 yr, so the fan is the
existing linear-combination + percentile computation looped over the year grid — the
per-horizon block was factored into one JS helper (`horizonStats`) shared by the stat row,
histogram, and fan, so they cannot disagree by construction. Year 0 anchors at
`(1 − fee)·lump`. Verified in a real browser: fan endpoint ≡ stat row exactly (baby
$331,024/$503,300/$631,093; wife likewise), baby p50 multiple 5.35× still ties to
`random_windows.md`, mobile no-overflow, two builds byte-identical. Honesty caveat in the
panel: each year's percentiles come from independent windows — the p50 line is not a path
anyone rode; a true within-window trajectory was again rejected (would need per-step engine
data and make the JS a second simulator). See `results/sprint6_projection_fan.md`.

## Sprint 7 — Real portfolio vs simulated SPY/QQQ DCA  ✅ SHIPPED

Validation of the user's real track record: NZ$90,000 deposited 2019-02-25 → 2024-10-11,
actually worth US$82,740.04 on 2026-07-10 — vs the same money as an even weekly DCA into
SPY/QQQ (NZD→USD at weekly spot, 0% FX fee to match real IBKR-scale costs, buys at the
engine's standard first-trading-day close), held after the last deposit.

**Tasks**
1. Extend `data/*.csv` through 2026-07-10 (append-only; fresh-pull overlap must match
   committed history exactly) → verify: `git diff` shows only appended rows; offline rerun
   byte-stable. *(NZDUSD=X failed the overlap guardrail — Yahoo FX closes drift ~0.4% —
   left untouched; the engine ffills FX so 07-09 covers the 07-10 conversion.)*
2. Engine: `simulate_nzd_dca_hold` (accumulate-then-hold, which `simulate_dca` can't
   express) + `even_nzd_schedule` (schedule-shaped: a real deposit CSV can drop in later)
   → verify: 294 buys within the window, NZD sums to 90,000, invested flat after last
   deposit, curve endpoint == summary final.
3. Data contract: `results/real_vs_dca_timeseries.csv` + `real_vs_dca_summary.csv`
   (REAL row = actual value on the same assumed cashflows → **approximate** XIRR).
4. Dashboard tab **My portfolio vs DCA** (`#real`): value-vs-time chart (sim SPY/QQQ,
   invested-cum, deposits-stop vline, actual-value marker) + comparison table, reading
   only the committed CSVs → verify: real browser, tab renders, other tabs unaffected.
5. `results/sprint7_real_vs_dca.md` + `SECTIONS` line in `build_report.py`.

**Done when:** the dashboard shows the comparison from committed CSVs only, with the
even-split/hindsight/approx-XIRR caveats stated on the panel.

**Result** *(reproduce: `python3 backtest.py && python3 build_report.py &&
python3 build_dashboard.py`, network off)*: even weekly DCA on the same deposits
(US$58,205 deployed) would have reached **$122,961 (SPY, 2.11x, 16.8% XIRR)** or
**$149,994 (QQQ, 2.58x, 21.5%)** vs the actual **$82,740 (1.42x, ~7.8% approx)** —
a ~9–14 %/yr money-weighted gap. Honesty framing in `results/sprint7_real_vs_dca.md`:
even-split approximation, hindsight benchmark choice, single-end-point actual path.

## Sprint 8 / 8b — Buy-timing sensitivity: weekday anchor + dip double-down  ✅ SHIPPED

Two timing studies prompted by "does *when* in the week / news cycle I buy matter?" Both
land the same way: intra-period timing moves outcomes by basis points; start-date luck moves
them by percentage points.

**Sprint 8 — buy day of week:** re-run the weekly DCA anchored Mon–Fri (holiday rolls
forward within the week, back only for a Fri closure). `weekday_buy_dates` /
`weekday_anchor_study`; 1,000 paired 18-yr windows (seed 42) under all five anchors →
`results/weekday_anchor.csv`, dashboard tab **Buy day of week** (view7).

**Sprint 8b — dip double-down:** daily $100 DCA that buys 2× on a close ≤ −1/−2/−3% and skips
the next calm day (skip-credit queue, cash-flow-neutral). `dip_buy_schedule` /
`dip_double_study`; `simulate_dca` generalized to accept precomputed buys + a per-buy amount
Series (scalar path regression-checked) → `results/dip_double.csv`, dashboard tab **Buy the
dip** (view8).

**Result** *(reproduce network-off)*: best-vs-worst weekday ≈ **1.3–1.9bp/yr median** (max
3.0bp) vs ~500bp start-date luck; Monday best in 92–97% of windows ("weekend effect"). Dip
tilt beats plain daily in **100%** of windows but only **+0.1–0.4bp/yr** (<0.06% of terminal
wealth); rarer triggers gain less. Both verdicts: automate a boring schedule, ignore the
calendar and red days. Snapshot `results/sprint8_timing.md`.

## Sprint 9 — Dip double-down on the *real* scenario  ✅ SHIPPED

Applies the Sprint 8b rule to Sprint 7's actual-portfolio scenario: the same NZ$90k over the
same 2019-02-25 → 2024-10-11 window, deployed **daily** into SPY/QQQ under even-daily vs dip
1/2/3%, NZD→USD at daily spot, held to 2026-07-10. `real_dip_variants` reuses
`dip_buy_schedule` + `simulate_nzd_dca_hold` so only deposit timing varies →
`results/real_dip.csv`; extends the **My portfolio vs DCA** tab with a second table (real
panel only — all other tabs byte-identical).

**Result** *(reproduce network-off)*: the dip tilt added **$39–274** on a $123k–150k result
(≤ ~1bp/yr) — the same rounding-error edge as the window distribution. Being invested for the
2019–2026 run decided it, not deposit timing. Snapshot `results/sprint9_real_dip.md`. Flagged
follow-up: the *stronger* buy-the-dip (hold a cash reserve, deploy a lump into a −20%/−30%
drawdown) is a different, riskier strategy — cash drag vs discount — not yet modelled.

## Next session

**All sprints (0–9, plus the 5b layout pass) are shipped and the site is live.**
Nothing required remains.

- **GitHub Pages: ✅ done** — enabled on `main` / `/docs`, status "built", live at
  https://dizhangai-star.github.io/auto-invest-strategy/ (verified 2026-07 via the GitHub API).
- **Sprint 4 is shipped** (interactive Plotly dashboard → `results/dashboard.html` +
  `docs/dashboard.html`, `python3 build_dashboard.py` — reads the Sprint 1 CSV contract +
  offline `data/*.csv`, never re-simulates).
- **Sprint 5 is shipped** (projection calculator, its own dashboard tab — client-side p10/p50/p90
  projections from `results/projection_factors.csv`; the Custom preset takes the user's own
  portfolio numbers whenever provided).
- **Sprint 6 is shipped** (projection fan graph in the calculator — p10/p50/p90 value vs
  elapsed years from the same factors, no engine change).
- **Sprint 7 is shipped** (real portfolio vs simulated SPY/QQQ weekly DCA — accumulate-then-
  hold sim, `results/real_vs_dca_*.csv` contract, "My portfolio vs DCA" dashboard tab).
- **Sprints 8/8b/9 are shipped** (buy-timing studies — weekday anchor, dip double-down, and
  the dip applied to the real scenario; `results/weekday_anchor.csv`, `dip_double.csv`,
  `real_dip.csv`; dashboard tabs **Buy day of week** / **Buy the dip** + the real-panel dip
  table). Headline: timing tweaks are basis points, not the lever.
- **Remaining candidate work (optional, not committed):**
  - Sprint 7 fidelity upgrade: export the user's actual per-deposit schedule (date, NZD
    amount) — likely via an IBKR connector/Flex export — and drop it into
    `even_nzd_schedule`'s slot in `run_real_vs_dca`, replacing the even-split assumption.
  - Stronger buy-the-dip (follow-up to Sprint 9): hold a cash reserve and deploy a lump into
    a drawdown-from-peak trigger (−10%/−20%/−30%), modelling the cash-drag-vs-discount
    tradeoff — the version with real timing risk, unlike the self-funded daily rule.
  - Extend the dashboard with Sprint 3's after-tax overlay (interactive PIR-rate / PIE-vs-FIF
    toggle) if the static section proves insufficient.
  - Sequence-of-returns / withdrawal phase — still genuinely out of scope; becomes relevant
    within ~5 yr of the baby's 18-yr horizon.
- Per-sprint contract (if extending): drop `results/<name>.md` (+ `.png`), add a line to `SECTIONS`
  in `build_report.py`, rerun both scripts (regenerate the committed reference **network-off**).
