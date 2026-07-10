"""
build_dashboard — Sprint 4: interactive Plotly dashboard -> results/dashboard.html.

A COMMUNICATION layer, not new evidence. It reads the committed artifacts:
  - results/windows_<scenario>_<ticker>.csv  (Sprint 1 data contract: one row per window)
  - results/fan_<scenario>_<ticker>.csv      (p10/p50/p90 wealth-multiple trajectories)
  - data/<TICKER>.csv                        (offline total-return prices)
and NEVER re-simulates the distribution — so its numbers cannot drift from the
committed results/ tables. The only computation here is presentational: bear-market
spans from the engine's own drawdown definition, and ONE illustrative DCA path
(clearly labelled as such) for the orders view.

Deliberately network-free: prices come from data/*.csv, never yfinance, so the
committed dashboard.html is reproducible byte-for-byte (fixed Plotly div ids).

Run:  python3 build_dashboard.py     (after backtest.py has produced results/)
Deps: pandas, numpy, plotly
"""
from __future__ import annotations
import shutil
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from backtest import (FX_FEE, WEEKLY_CONTRIB, WIFE_LUMP, WIFE_MONTHLY,
                      _contribution_dates, simulate_dca, pct)

OUT = "results/dashboard.html"
TICKERS = ["QQQ", "SPY"]
# dataviz palette (validated): categorical slot 1 (blue) = QQQ, slot 2 (aqua) = SPY
COLORS = {"QQQ": "#2a78d6", "SPY": "#1baf7a"}
BEAR_THRESHOLD = -0.20
SCENARIOS = [
    ("baby", f"Baby — 18-yr weekly DCA (${WEEKLY_CONTRIB:.0f}/wk, {FX_FEE:.1%} FX fee)"),
    ("wife", f"Wife — 10-yr lump ${WIFE_LUMP:,.0f} + ${WIFE_MONTHLY:.0f}/mo (PIE, no FX fee)"),
]
SHORT = {"baby": "Baby (18-yr weekly)", "wife": "Wife (10-yr lump + monthly)"}


def load_offline(ticker: str) -> pd.Series:
    """Committed total-return prices only — the dashboard must not touch the network."""
    return pd.read_csv(f"data/{ticker}.csv", index_col=0, parse_dates=True)["Close"].dropna()


def _rgba(hex_color: str, alpha: float) -> str:
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    return f"rgba({r},{g},{b},{alpha})"


# --------------------------------------------------------------------------------------
# View 1 (lead) — outcome distribution across randomized windows
# --------------------------------------------------------------------------------------
def fig_distribution() -> tuple[go.Figure, str]:
    fig = make_subplots(
        rows=2, cols=2, vertical_spacing=0.16, horizontal_spacing=0.08,
        subplot_titles=[f"{SHORT[s]} — {m}" for s, _ in SCENARIOS
                        for m in ("XIRR", "final multiple")])
    notes = []
    for i, (scen, label) in enumerate(SCENARIOS, start=1):
        dfs = {t: pd.read_csv(f"results/windows_{scen}_{t}.csv", parse_dates=["start"])
               for t in TICKERS}
        for t in TICKERS:
            fig.add_trace(go.Histogram(
                x=dfs[t]["xirr"] * 100, name=t, legendgroup=t, showlegend=(i == 1),
                marker_color=COLORS[t], opacity=0.55, nbinsx=40,
                hovertemplate=f"{t} XIRR %{{x:.1f}}%: %{{y}} windows<extra></extra>",
            ), row=i, col=1)
            fig.add_trace(go.Histogram(
                x=dfs[t]["multiple"], name=t, legendgroup=t, showlegend=False,
                marker_color=COLORS[t], opacity=0.55, nbinsx=40,
                hovertemplate=f"{t} %{{x:.2f}}x: %{{y}} windows<extra></extra>",
            ), row=i, col=2)
        paired = pd.concat([dfs[t].set_index("start")["xirr"] for t in TICKERS],
                           axis=1, keys=TICKERS).dropna()
        win = (paired["QQQ"] > paired["SPY"]).mean()
        stats = " · ".join(
            f"{t} p10/p50/p90 {pct(dfs[t]['xirr'].quantile(.1))}/"
            f"{pct(dfs[t]['xirr'].quantile(.5))}/{pct(dfs[t]['xirr'].quantile(.9))}"
            for t in TICKERS)
        notes.append(f"<strong>{label}</strong> ({len(paired)} paired windows): XIRR {stats}; "
                     f"QQQ beat SPY in {pct(win)} of windows; worst intra-window balance "
                     f"drawdown (p10) QQQ {pct(dfs['QQQ']['max_dd'].quantile(.1))}, "
                     f"SPY {pct(dfs['SPY']['max_dd'].quantile(.1))}.")
        fig.update_xaxes(title_text="annualized XIRR (%)", row=i, col=1)
        fig.update_xaxes(title_text="final value / invested (x)", row=i, col=2)
        fig.update_yaxes(title_text="windows", row=i, col=1)
    fig.update_layout(barmode="overlay", height=680,
                      legend=dict(orientation="h", y=1.08, x=0))
    return fig, "<br>".join(notes)


# --------------------------------------------------------------------------------------
# View 2 — percentile fan (p10–p90 band + p50 line) from the window trajectories
# --------------------------------------------------------------------------------------
def fig_fan() -> go.Figure:
    fig = make_subplots(rows=1, cols=2, horizontal_spacing=0.08,
                        subplot_titles=[SHORT[s] for s, _ in SCENARIOS])
    for i, (scen, _) in enumerate(SCENARIOS, start=1):
        for t in TICKERS:
            fan = pd.read_csv(f"results/fan_{scen}_{t}.csv")
            fig.add_trace(go.Scatter(
                x=fan["years"], y=fan["wealth_mult_p90"], mode="lines",
                line=dict(width=0), legendgroup=t, showlegend=False,
                hovertemplate=f"{t} p90 %{{y:.2f}}x at %{{x:.1f}}y<extra></extra>",
            ), row=1, col=i)
            fig.add_trace(go.Scatter(
                x=fan["years"], y=fan["wealth_mult_p10"], mode="lines",
                line=dict(width=0), fill="tonexty", fillcolor=_rgba(COLORS[t], 0.18),
                legendgroup=t, showlegend=False,
                hovertemplate=f"{t} p10 %{{y:.2f}}x at %{{x:.1f}}y<extra></extra>",
            ), row=1, col=i)
            fig.add_trace(go.Scatter(
                x=fan["years"], y=fan["wealth_mult_p50"], mode="lines",
                name=f"{t} p50 (band = p10–p90)", legendgroup=t, showlegend=(i == 1),
                line=dict(color=COLORS[t], width=2),
                hovertemplate=f"{t} p50 %{{y:.2f}}x at %{{x:.1f}}y<extra></extra>",
            ), row=1, col=i)
        fig.add_hline(y=1.0, line=dict(color="#888", width=1, dash="dot"), row=1, col=i)
        fig.update_xaxes(title_text="years since first contribution", row=1, col=i)
    fig.update_yaxes(title_text="portfolio value / money put in (x)", row=1, col=1)
    fig.update_layout(height=440, legend=dict(orientation="h", y=1.15, x=0))
    return fig


# --------------------------------------------------------------------------------------
# View 3 — bull/bear cycles: growth of $1 with bear spans shaded.
# Spans use the engine's drawdown definition (price / running max − 1); a "bear" is any
# episode dipping below −20%, shaded peak → recovery. No independent regime detection.
# --------------------------------------------------------------------------------------
def bear_spans(prices: pd.Series, threshold: float = BEAR_THRESHOLD) -> list[dict]:
    dd = prices / prices.cummax() - 1
    spans, start, depth = [], None, 0.0
    for date, v in dd.items():
        if v == 0:
            if start is not None and depth <= threshold:
                spans.append({"start": start, "end": date, "depth": depth})
            start, depth = None, 0.0
        else:
            start = start or date
            depth = min(depth, v)
    if start is not None and depth <= threshold:      # still underwater at data end
        spans.append({"start": start, "end": dd.index[-1], "depth": depth})
    return spans


def fig_cycles(prices: pd.DataFrame) -> tuple[go.Figure, list[dict]]:
    fig = go.Figure()
    spans = bear_spans(prices["QQQ"])
    for sp in spans:
        fig.add_vrect(x0=sp["start"], x1=sp["end"], fillcolor="rgba(120,120,120,0.16)",
                      line_width=0, annotation_text=f"{sp['depth']:.0%}",
                      annotation_position="top left", annotation_font_size=11)
    norm = prices / prices.iloc[0]
    for t in TICKERS:
        fig.add_trace(go.Scatter(
            x=norm.index, y=norm[t], name=t, line=dict(color=COLORS[t], width=2),
            hovertemplate=f"{t} %{{y:.2f}}x on %{{x|%Y-%m-%d}}<extra></extra>"))
    fig.update_yaxes(type="log", title_text="growth of $1 (log)")
    fig.update_layout(height=460, legend=dict(orientation="h", y=1.1, x=0))
    return fig, spans


# --------------------------------------------------------------------------------------
# View 4 (secondary, illustrative ONLY) — DCA buy orders on one price path
# --------------------------------------------------------------------------------------
def fig_orders(prices: pd.Series) -> go.Figure:
    r = simulate_dca(prices, WEEKLY_CONTRIB, "W", fx_fee=FX_FEE)
    buys = _contribution_dates(prices, "W")
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.06,
                        row_heights=[0.55, 0.45],
                        subplot_titles=["QQQ price with weekly buys (ONE path)",
                                        "Portfolio value vs money put in (same path)"])
    fig.add_trace(go.Scatter(
        x=buys.index, y=buys, mode="markers", name=f"weekly ${WEEKLY_CONTRIB:.0f} buy",
        marker=dict(color=_rgba(COLORS["SPY"], 0.4), size=4),
        hovertemplate="buy @ %{y:.2f} on %{x|%Y-%m-%d}<extra></extra>"), row=1, col=1)
    fig.add_trace(go.Scatter(x=prices.index, y=prices, name="QQQ price",
                             line=dict(color=COLORS["QQQ"], width=1.5),
                             hovertemplate="%{y:.2f} on %{x|%Y-%m-%d}<extra></extra>"),
                  row=1, col=1)
    fig.add_trace(go.Scatter(x=r.curve.index, y=r.curve["value"], name="portfolio value",
                             line=dict(color=COLORS["QQQ"], width=2),
                             hovertemplate="$%{y:,.0f} on %{x|%Y-%m-%d}<extra></extra>"),
                  row=2, col=1)
    fig.add_trace(go.Scatter(x=r.curve.index, y=r.curve["invested_cum"],
                             name="money put in", line=dict(color="#888", width=1.5, dash="dash"),
                             hovertemplate="$%{y:,.0f} in by %{x|%Y-%m-%d}<extra></extra>"),
                  row=2, col=1)
    fig.update_yaxes(type="log", title_text="price (log)", row=1, col=1)
    fig.update_yaxes(title_text="USD", row=2, col=1)
    fig.update_layout(height=620, legend=dict(orientation="h", y=1.12, x=0))
    print(f"[dashboard] illustrative path: {len(buys)} buys, "
          f"${r.invested:,.0f} -> ${r.final_value:,.0f} ({r.multiple:.2f}x), XIRR {pct(r.xirr)}")
    return fig


# --------------------------------------------------------------------------------------
CSS = """
* { box-sizing: border-box; }
body { font: 16px/1.6 -apple-system, system-ui, sans-serif; color: #1a1a1a; background: #fcfcfb;
       max-width: 1100px; margin: 0 auto; padding: 2rem 1.25rem 5rem; }
h1 { font-size: 1.7rem; margin: 0 0 .5rem; }
h2 { font-size: 1.2rem; margin: 2.5rem 0 .4rem; border-bottom: 1px solid #ddd; padding-bottom: .2rem; }
p { color: #333; max-width: 62rem; }
.note { color: #52514e; font-size: .9rem; }
.warn { background: #fff6e8; border-left: 3px solid #eda100; padding: .5rem .8rem; font-size: .9rem; }
.foot { color: #666; font-size: .85rem; margin-top: 4rem; border-top: 1px solid #ddd; padding-top: 1rem; }
"""


def build() -> str:
    prices = pd.concat([load_offline(t) for t in TICKERS], axis=1, keys=TICKERS).dropna()
    f1, dist_notes = fig_distribution()
    f2 = fig_fan()
    f3, spans = fig_cycles(prices)
    f4 = fig_orders(prices["QQQ"])
    worst = min(spans, key=lambda s: s["depth"])
    print(f"[dashboard] QQQ bear spans (<= {BEAR_THRESHOLD:.0%}): "
          + ", ".join(f"{s['start'].date()}→{s['end'].date()} {s['depth']:.0%}" for s in spans))

    def div(fig: go.Figure, i: int, first: bool = False) -> str:
        return fig.to_html(full_html=False, include_plotlyjs="inline" if first else False,
                           div_id=f"view{i}", auto_play=False,
                           config={"displaylogo": False, "responsive": True})

    window = f"{prices.index[0].date()} → {prices.index[-1].date()}"
    html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>DCA outcome distributions — QQQ vs SPY</title><style>{CSS}</style></head><body>
<h1>DCA outcome distributions — QQQ vs SPY</h1>
<p>Interactive companion to the committed <code>results/</code> snapshots. Total-return
prices, USD, pre-tax; data window {window} (offline <code>data/*.csv</code>). The lead view
is the <strong>distribution across randomized start dates</strong> — never one lucky or
unlucky line. Built by <code>build_dashboard.py</code> from the Sprint 1 CSV contract; it
re-simulates nothing, so these numbers match <code>results/random_windows.md</code> exactly.</p>
<div class="warn">Honesty caveats: the baby's 100% QQQ win-rate is a <strong>sample-length
artifact</strong> — ~27 yr of history means the 18-yr "windows" heavily overlap one macro
path in which Nasdaq concentration was never punished end-to-end. Treat concentration risk
as <em>not disproven</em>, not absent. Both scenarios put a ~40–47% balance drawdown on the
table (view 1 notes, view 3 spans).</div>

<h2>1 · Outcome distribution (the headline view)</h2>
<p class="note">{dist_notes}</p>
{div(f1, 1, first=True)}

<h2>2 · Percentile fan — the spread as it unfolds</h2>
<p class="note">Cross-window p10–p90 band and p50 line of portfolio value ÷ money put in,
at each elapsed step (from <code>results/fan_*.csv</code>). Dotted line = break-even. The
terminal p50 sits a hair below the windows-CSV multiple p50 by design (per-step cross-window
percentile, truncated to the shortest window) — see SPRINT_PLAN Sprint 1 note.</p>
{div(f2, 2)}

<h2>3 · Bull/bear cycles the windows are sampling from</h2>
<p class="note">Growth of $1 (log). Shaded spans = QQQ bear episodes (any fall below
{BEAR_THRESHOLD:.0%} from a running peak, shaded peak → recovery), computed with the same
drawdown definition as the engine. The {worst['depth']:.0%} dot-com span
({worst['start'].date()} → {worst['end'].date()}) is the risk the randomized windows
under-sample — it appears in full in no completed 18-yr window.</p>
{div(f3, 3)}

<h2>4 · Orders on a chart — ONE illustrative path (not evidence)</h2>
<p class="note"><strong>This is a single start date</strong> — exactly what the rest of this
page exists to warn against. It is here only to show the mechanics of weekly DCA (buys land
in crashes too) on the full-history QQQ path. Judge outcomes by views 1–2, not this.</p>
{div(f4, 4)}

<p class="foot">Generated by <code>python3 build_dashboard.py</code> — reads committed
<code>results/*.csv</code> + <code>data/*.csv</code>, computes no new evidence. Plotly
embedded; opens offline. See <code>results/random_windows.md</code> and
<code>SPRINT_PLAN.md</code> for methodology and caveats.</p>
</body></html>"""
    with open(OUT, "w") as f:
        f.write(html)
    shutil.copyfile(OUT, "docs/dashboard.html")   # published via GitHub Pages next to index.html
    return OUT


if __name__ == "__main__":
    out = build()
    print(f"[dashboard] wrote {out}")
