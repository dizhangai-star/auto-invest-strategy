"""
build_dashboard — Sprint 4: interactive Plotly dashboard -> results/dashboard.html.

A COMMUNICATION layer, not new evidence. It reads the committed artifacts:
  - results/windows_<scenario>_<ticker>.csv  (Sprint 1 data contract: one row per window)
  - results/fan_<scenario>_<ticker>.csv      (p10/p50/p90 wealth-multiple trajectories)
  - results/projection_factors.csv           (Sprint 5 calculator factors, per-year 1..18)
  - results/real_vs_dca_timeseries.csv       (Sprint 7: weekly sim value + invested cum)
  - results/real_vs_dca_summary.csv          (Sprint 7: REAL/SPY/QQQ comparison rows)
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
import json
import shutil
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from backtest import (BABY_YEARS, FX_FEE, RANDOM_N, REAL_DEPOSIT_END, REAL_DEPOSIT_START,
                      WEEKLY_CONTRIB, WIFE_LUMP, WIFE_MONTHLY, WIFE_YEARS,
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
# Sprint 5 — interactive projection calculator (+ Sprint 6 fan: the same computation
# looped over the 1..18-yr horizon grid, drawn as a p10-p90 band vs elapsed years).
#
# The engine stays the sole source of numbers: results/projection_factors.csv holds
# per-window linear factors (g0, s) such that simulate_dca's final value is EXACTLY
#     final = (1 - fx_fee) * (lump * g0 + amount * s)
# for any (lump, amount, fee). The JS below only takes linear combinations of those
# factors (ticker blend = fixed contribution split, no rebalancing) and percentiles —
# it is not a second simulation engine and cannot drift from the committed CSV.
# Plain template string with __TOKEN__ substitution (an f-string would fight the JS braces).
# --------------------------------------------------------------------------------------
_PROJ_TEMPLATE = """
<div class="warn"><strong>Projection = replaying 1999&ndash;2026 history, not predicting.</strong>
The ~1,000 windows per horizon are drawn from one 27-yr macro path and overlap heavily &mdash;
no completed 18-yr window contains a full dot-com-style QQQ round trip. Figures are nominal
USD, <strong>pre-tax</strong>: Sprint 3 puts PIE/FIF tax at a ~1.4&ndash;2.0%/yr left-shift of
the whole distribution. Mix = a fixed split of every contribution, held without rebalancing.
And the end-numbers hide the ride: __DD_NOTE__</div>
<div class="presets">
  <button onclick="projPreset('baby')">Baby &mdash; $__BABY_AMT__/wk QQQ, __BABY_YRS__ yr, __BABY_FEE__% FX</button>
  <button onclick="projPreset('wife')">Wife &mdash; $__WIFE_LUMP_LABEL__ lump + $__WIFE_AMT__/mo SPY, __WIFE_YRS__ yr</button>
  <button onclick="projPreset('custom')">Custom &mdash; my portfolio (50/50 start)</button>
</div>
<div class="projform" id="proj_form">
  <label>deposit $<input id="proj_amount" type="number" min="0" step="10" value="__BABY_AMT__"></label>
  <label>every <select id="proj_freq"><option value="W">week</option><option value="MS">month</option></select></label>
  <label>for <input id="proj_hval" type="number" min="1" step="1" value="__BABY_YRS__">
    <select id="proj_hunit"><option value="years">years</option><option value="months">months</option><option value="weeks">weeks</option></select></label>
  <label>lump sum $<input id="proj_lump" type="number" min="0" step="1000" value="0"></label>
  <label>FX fee <input id="proj_fee" type="number" min="0" max="5" step="0.1" value="__BABY_FEE__">%</label>
  <label>mix <input id="proj_qqq" type="range" min="0" max="100" step="5" value="100"><span id="proj_qqqlab">100% QQQ / 0% SPY</span></label>
  <label>assumed <input id="proj_rate" type="number" step="0.5" value="7">%/yr</label>
</div>
<div id="proj_out"></div>
<div id="proj_fan"></div>
<p class="note">Fan: each year&rsquo;s p10/p50/p90 comes from its own ~1,000 independent historical
start dates, not one continuous path &mdash; the p50 line is not a trajectory anyone actually rode
(same construction as the Percentile fan view). Its endpoint equals the stat row above exactly.</p>
<div id="proj_hist"></div>
<script>
const PROJ=__PROJ_JSON__;
const $p=id=>document.getElementById(id);
function pctile(a,q){const p=(a.length-1)*q,lo=Math.floor(p),hi=Math.ceil(p);return a[lo]+(a[hi]-a[lo])*(p-lo);}
function fmt$(x){return "$"+Math.round(x).toLocaleString("en-US");}
function fvFixed(r,ppy,yrs,amount,lump,fee){
  const n=Math.round(yrs*ppy),i=Math.pow(1+r,1/ppy)-1;
  const ann=(Math.abs(i)<1e-12)?n:((Math.pow(1+i,n)-1)/i)*(1+i);
  return (1-fee)*(lump*Math.pow(1+r,yrs)+amount*ann);
}
function impliedRate(target,ppy,yrs,amount,lump,fee){
  let lo=-0.9,hi=1.0;
  if(fvFixed(lo,ppy,yrs,amount,lump,fee)>target||fvFixed(hi,ppy,yrs,amount,lump,fee)<target)return null;
  for(let k=0;k<80;k++){const m=(lo+hi)/2;if(fvFixed(m,ppy,yrs,amount,lump,fee)<target)lo=m;else hi=m;}
  return (lo+hi)/2;
}
function horizonStats(freq,y,lump,amount,fee,wq,ws){
  const cell=PROJ[freq][String(y)];
  const N=cell.n.length,finals=new Array(N),invs=new Array(N);
  for(let i=0;i<N;i++){
    const g0=wq*cell.QQQ.g0[i]+ws*cell.SPY.g0[i],s=wq*cell.QQQ.s[i]+ws*cell.SPY.s[i];
    finals[i]=(1-fee)*(lump*g0+amount*s);
    invs[i]=lump+amount*cell.n[i];
  }
  finals.sort((a,b)=>a-b);invs.sort((a,b)=>a-b);
  return {finals:finals,p10:pctile(finals,.1),p50:pctile(finals,.5),
          p90:pctile(finals,.9),inv:pctile(invs,.5)};
}
function recalcProj(){
  const amount=+$p("proj_amount").value||0,freq=$p("proj_freq").value;
  const hv=+$p("proj_hval").value||0,hu=$p("proj_hunit").value;
  const lump=+$p("proj_lump").value||0,fee=(+$p("proj_fee").value||0)/100;
  const wq=(+$p("proj_qqq").value)/100,ws=1-wq,rate=(+$p("proj_rate").value||0)/100;
  $p("proj_qqqlab").textContent=Math.round(wq*100)+"% QQQ / "+Math.round(ws*100)+"% SPY";
  const yrsRaw=hu==="years"?hv:(hu==="months"?hv/12:hv/52);
  const yrs=Math.min(18,Math.max(1,Math.round(yrsRaw)));
  const ppy=freq==="W"?52:12;
  const end=horizonStats(freq,yrs,lump,amount,fee,wq,ws);
  const finals=end.finals,N=finals.length;
  const p10=end.p10,p50=end.p50,p90=end.p90,inv=end.inv;
  const fv=fvFixed(rate,ppy,yrs,amount,lump,fee),imp=impliedRate(p50,ppy,yrs,amount,lump,fee);
  const snap=Math.abs(yrsRaw-yrs)>1e-9?" &mdash; input snapped to the "+yrs+"-yr historical window grid":"";
  let h='<div class="projstats">'
    +'<div class="stat">total put in (median window)<b>'+fmt$(inv)+'</b></div>'
    +'<div class="stat">p10 &mdash; bad decade<b>'+fmt$(p10)+'</b></div>'
    +'<div class="stat">p50 &mdash; median history<b>'+fmt$(p50)+'</b></div>'
    +'<div class="stat">p90 &mdash; lucky start<b>'+fmt$(p90)+'</b></div>'
    +'<div class="stat">p50 multiple<b>'+(p50/inv).toFixed(2)+'x</b></div></div>';
  h+='<p class="note">Across '+N+' random '+yrs+'-yr historical start dates'+snap
    +'. Quick check at an <em>assumed</em> '+(rate*100).toFixed(1)+'%/yr constant return: '
    +'<strong>'+fmt$(fv)+'</strong> (intuition only, not evidence)'
    +(imp!==null?'; the historical p50 is equivalent to a constant '+(imp*100).toFixed(1)+'%/yr.':'.')
    +'</p>';
  if(p10<inv)h+='<p class="projred">p10 &lt; money put in: in at least 1-in-10 historical windows you ended with less than you deposited.</p>';
  $p("proj_out").innerHTML=h;
  const xs=[0],flo=[(1-fee)*lump],fmid=[(1-fee)*lump],fhi=[(1-fee)*lump],fput=[lump];
  for(let y=1;y<=yrs;y++){
    const st=(y===yrs)?end:horizonStats(freq,y,lump,amount,fee,wq,ws);
    xs.push(y);flo.push(st.p10);fmid.push(st.p50);fhi.push(st.p90);fput.push(st.inv);
  }
  Plotly.react("proj_fan",
    [{x:xs,y:fhi,type:"scatter",mode:"lines",line:{width:0},showlegend:false,
      hovertemplate:"p90 $%{y:,.0f}<extra></extra>"},
     {x:xs,y:flo,type:"scatter",mode:"lines",line:{width:0},fill:"tonexty",
      fillcolor:"rgba(42,120,214,0.16)",name:"p10–p90",
      hovertemplate:"p10 $%{y:,.0f}<extra></extra>"},
     {x:xs,y:fmid,type:"scatter",mode:"lines",line:{color:"#2a78d6",width:2.5},name:"p50",
      hovertemplate:"p50 $%{y:,.0f}<extra></extra>"},
     {x:xs,y:fput,type:"scatter",mode:"lines",line:{color:"#7a7a76",width:1.6,dash:"dot"},
      name:"money put in",hovertemplate:"put in $%{y:,.0f}<extra></extra>"}],
    {margin:{t:30,r:20,b:45,l:55},height:340,hovermode:"x unified",
     legend:{orientation:"h",x:0,y:1.12},
     xaxis:{title:{text:"elapsed years"},dtick:yrs>9?2:1,range:[0,yrs]},
     yaxis:{title:{text:"portfolio value ($, nominal USD, pre-tax)"},tickprefix:"$",rangemode:"tozero"}},
    {displaylogo:false,responsive:true});
  Plotly.react("proj_hist",
    [{x:finals,type:"histogram",nbinsx:60,marker:{color:"#2a78d6"},hovertemplate:"$%{x:,.0f}<extra></extra>"}],
    {margin:{t:30,r:20,b:45,l:55},height:320,showlegend:false,
     xaxis:{title:{text:"final value ($, nominal USD, pre-tax)"},tickprefix:"$"},
     yaxis:{title:{text:"windows"}},
     shapes:[[inv,"#7a7a76","dot"],[p10,"#c0392b","dash"],[p50,"#1a1a1a","solid"],[p90,"#1baf7a","dash"]]
       .map(v=>({type:"line",x0:v[0],x1:v[0],y0:0,y1:1,yref:"paper",line:{color:v[1],width:1.4,dash:v[2]}})),
     annotations:[[inv,"put in"],[p10,"p10"],[p50,"p50"],[p90,"p90"]]
       .map(a=>({x:a[0],y:1.02,yref:"paper",text:a[1],showarrow:false,font:{size:11}}))},
    {displaylogo:false,responsive:true});
}
function projPreset(p){
  const v={baby:{amount:__BABY_AMT__,freq:"W",hval:__BABY_YRS__,lump:0,fee:__BABY_FEE__,qqq:100},
           wife:{amount:__WIFE_AMT__,freq:"MS",hval:__WIFE_YRS__,lump:__WIFE_LUMP__,fee:0,qqq:0},
           custom:{amount:200,freq:"W",hval:10,lump:0,fee:0,qqq:50}}[p];
  $p("proj_amount").value=v.amount;$p("proj_freq").value=v.freq;$p("proj_hval").value=v.hval;
  $p("proj_hunit").value="years";$p("proj_lump").value=v.lump;$p("proj_fee").value=v.fee;
  $p("proj_qqq").value=v.qqq;recalcProj();
}
document.querySelectorAll("#proj_form input,#proj_form select").forEach(x=>x.addEventListener("input",recalcProj));
projPreset("baby");
</script>
"""


def projection_section() -> str:
    """Sprint 5 panel: embed the engine's per-window factors + the client-side calculator."""
    fac = pd.read_csv("results/projection_factors.csv")
    payload = {"W": {}, "MS": {}}
    for (freq, years), cell in fac.groupby(["freq", "years"]):
        payload[freq][str(int(years))] = {
            "n": cell["n_buys"].astype(int).tolist(),
            "QQQ": {"g0": cell["g0_QQQ"].tolist(), "s": cell["s_QQQ"].tolist()},
            "SPY": {"g0": cell["g0_SPY"].tolist(), "s": cell["s_SPY"].tolist()},
        }
    dd = {k: pd.read_csv(f"results/windows_{k}.csv")["max_dd"]
          for k in ("baby_QQQ", "wife_SPY")}
    dd_note = (f"expect the balance itself to fall ~{-dd['baby_QQQ'].median():.0%} in the median "
               f"18-yr QQQ window (~{-dd['baby_QQQ'].quantile(0.1):.0%} worst decile), "
               f"~{-dd['wife_SPY'].median():.0%} median for the wife's lump+monthly SPY — "
               f"see the Outcome distribution and One-path views.")
    html = _PROJ_TEMPLATE.replace("__PROJ_JSON__", json.dumps(payload, separators=(",", ":")))
    for token, value in {
        "__DD_NOTE__": dd_note,
        "__BABY_AMT__": f"{WEEKLY_CONTRIB:.0f}", "__BABY_YRS__": str(BABY_YEARS),
        "__BABY_FEE__": f"{FX_FEE * 100:g}",
        "__WIFE_AMT__": f"{WIFE_MONTHLY:.0f}", "__WIFE_YRS__": str(WIFE_YEARS),
        "__WIFE_LUMP_LABEL__": f"{WIFE_LUMP:,.0f}",   # button text (comma-grouped)
        "__WIFE_LUMP__": f"{WIFE_LUMP:.0f}",          # JS numeric literal (no comma)
    }.items():
        html = html.replace(token, value)
    return html


# --------------------------------------------------------------------------------------
# Sprint 7 — my real portfolio vs the same NZD deposits drip-fed weekly into SPY/QQQ.
# Reads only the committed real_vs_dca_*.csv contract; the comparison numbers are the
# engine's, never recomputed here.
# --------------------------------------------------------------------------------------
def fig_real_vs_dca() -> tuple[go.Figure, str, dict]:
    ts = pd.read_csv("results/real_vs_dca_timeseries.csv", parse_dates=["date"])
    summ = pd.read_csv("results/real_vs_dca_summary.csv").set_index("label")
    real = summ.loc["REAL"]
    asof = ts["date"].iloc[-1]

    fig = go.Figure()
    # milliseconds, not Timestamp: plotly's vline annotation helper can't average datetimes
    fig.add_vline(x=pd.Timestamp(REAL_DEPOSIT_END).timestamp() * 1000,
                  line=dict(color="#888", width=1, dash="dot"),
                  annotation_text="deposits stop", annotation_position="top left",
                  annotation_font_size=11)
    for t in TICKERS:
        fig.add_trace(go.Scatter(
            x=ts["date"], y=ts[f"value_{t}_usd"], name=f"{t} (simulated DCA)",
            line=dict(color=COLORS[t], width=2),
            hovertemplate=f"{t} $%{{y:,.0f}} on %{{x|%Y-%m-%d}}<extra></extra>"))
    fig.add_trace(go.Scatter(
        x=ts["date"], y=ts["invested_usd_cum"], name="money put in (USD)",
        line=dict(color="#7a7a76", width=1.6, dash="dash"),
        hovertemplate="put in $%{y:,.0f} by %{x|%Y-%m-%d}<extra></extra>"))
    fig.add_trace(go.Scatter(
        x=[asof], y=[real["final_usd"]], mode="markers+text", name="my portfolio (actual)",
        marker=dict(color="#1a1a1a", size=11, symbol="diamond"),
        text=[f"actual ${real['final_usd']:,.0f}"], textposition="middle left",
        textfont=dict(size=12),
        hovertemplate="actual $%{y:,.2f} on %{x|%Y-%m-%d}<extra></extra>"))
    fig.update_yaxes(title_text="portfolio value ($, nominal USD, pre-tax)", tickprefix="$",
                     rangemode="tozero")
    fig.update_layout(height=480, hovermode="x unified",
                      legend=dict(orientation="h", y=1.1, x=0))

    rows = []
    for label in ["REAL", "SPY", "QQQ"]:
        r = summ.loc[label]
        name = "My portfolio (actual)" if label == "REAL" else f"{label} (simulated DCA)"
        xirr_txt = pct(r["xirr_usd"]) + (" <em>(approx)</em>" if label == "REAL" else "")
        rows.append(f"<tr><td>{name}</td><td>${r['invested_usd']:,.0f}</td>"
                    f"<td>${r['final_usd']:,.0f}</td><td>{r['multiple_usd']:.2f}x</td>"
                    f"<td>{xirr_txt}</td><td>NZ${r['final_nzd']:,.0f}</td>"
                    f"<td>{r['multiple_nzd']:.2f}x</td></tr>")
    table = ("<table class='cmp'><thead><tr><th></th><th>USD deployed</th>"
             f"<th>value {asof.date()}</th><th>USD multiple</th><th>XIRR (USD)</th>"
             "<th>NZD-terms value</th><th>NZD multiple</th></tr></thead><tbody>"
             + "".join(rows) + "</tbody></table>")
    meta = {"n_buys": int(real["n_buys"]), "weekly_nzd": real["weekly_nzd"],
            "invested_nzd": real["weekly_nzd"] * real["n_buys"], "asof": asof.date()}
    return fig, table, meta


# --------------------------------------------------------------------------------------
CSS = """
* { box-sizing: border-box; }
body { font: 16px/1.6 -apple-system, system-ui, sans-serif; color: #1a1a1a; background: #fcfcfb;
       margin: 0; display: flex; }
.sidenav { flex: 0 0 220px; background: #f7f7f5; border-right: 1px solid #e3e2de; }
.sidenav .navinner { position: sticky; top: 0; max-height: 100vh; overflow-y: auto;
                     padding: 1.5rem 1rem; }
.sidenav .navtitle { font-weight: 700; font-size: .95rem; margin: 0 0 .8rem .6rem; color: #52514e; }
.sidenav a { display: block; padding: .45rem .6rem; border-radius: 5px; color: #333;
             text-decoration: none; font-size: .95rem; }
.sidenav a.active { background: #e8eef8; color: #1a4f9c; font-weight: 600; }
main { flex: 1; min-width: 0; max-width: 1100px; margin: 0 auto; padding: 2rem 1.5rem 5rem; }
.panel { display: none; }
.panel.active { display: block; }
h1 { font-size: 1.7rem; margin: 0 0 .5rem; }
h2 { font-size: 1.2rem; margin: 1rem 0 .4rem; border-bottom: 1px solid #ddd; padding-bottom: .2rem; }
p { color: #333; max-width: 62rem; }
.note { color: #52514e; font-size: .9rem; }
.warn { background: #fff6e8; border-left: 3px solid #eda100; padding: .5rem .8rem; font-size: .9rem; }
.foot { color: #666; font-size: .85rem; margin-top: 4rem; border-top: 1px solid #ddd; padding-top: 1rem; }
.projform { display: flex; flex-wrap: wrap; gap: .5rem 1.3rem; align-items: center;
            margin: .8rem 0 .4rem; font-size: .92rem; }
.projform label { display: flex; align-items: center; gap: .35rem; white-space: nowrap; }
.projform input[type=number] { width: 6.2rem; padding: .15rem .3rem; }
.presets button { margin: 0 .5rem .4rem 0; padding: .3rem .9rem; cursor: pointer;
                  border: 1px solid #bbb; border-radius: 4px; background: #f4f4f2; }
.projstats { display: flex; flex-wrap: wrap; gap: 1.1rem 2.2rem; margin: .8rem 0 .2rem; }
.projstats .stat b { font-size: 1.3rem; display: block; }
.projstats .stat { font-size: .85rem; color: #52514e; }
.projred { color: #c0392b; font-weight: 600; }
table.cmp { border-collapse: collapse; margin: .8rem 0; font-size: .92rem; }
table.cmp th, table.cmp td { border: 1px solid #ddd; padding: .35rem .7rem; text-align: right; }
table.cmp th:first-child, table.cmp td:first-child { text-align: left; }
table.cmp thead { background: #f4f4f2; }
@media (max-width: 800px) {
  body { flex-direction: column; }
  main { margin: 0; }
  .sidenav { flex: none; border-right: 0; border-bottom: 1px solid #e3e2de; }
  .sidenav .navinner { position: static; max-height: none; display: flex; flex-wrap: wrap;
                       align-items: center; gap: .15rem; padding: .6rem 1rem; }
  .sidenav .navtitle { margin: 0 .6rem 0 0; }
}
"""

# Sidebar entries: (panel id, nav label). Hash routing (#id) selects the active panel;
# an unknown or empty hash falls back to the first entry.
PANELS = [("distribution", "Outcome distribution"),
          ("fan", "Percentile fan"),
          ("calculator", "Projection calculator"),
          ("real", "My portfolio vs DCA"),
          ("cycles", "Bull/bear cycles"),
          ("orders", "One path (illustrative)")]

# Plotly figures rendered inside display:none panels get fallback width, so every panel
# activation re-sizes the plots it contains (rAF: after the display change lands).
TAB_JS = """
const panels=[...document.querySelectorAll("section.panel")];
const links=[...document.querySelectorAll(".sidenav a")];
function showPanel(){
  let id=location.hash.slice(1);
  if(!panels.some(p=>p.id===id))id=panels[0].id;
  panels.forEach(p=>p.classList.toggle("active",p.id===id));
  links.forEach(a=>a.classList.toggle("active",a.getAttribute("href")==="#"+id));
  requestAnimationFrame(()=>document.querySelectorAll("#"+id+" .js-plotly-plot")
    .forEach(el=>Plotly.Plots.resize(el)));
}
window.addEventListener("hashchange",showPanel);
showPanel();
"""


def build() -> str:
    prices = pd.concat([load_offline(t) for t in TICKERS], axis=1, keys=TICKERS).dropna()
    f1, dist_notes = fig_distribution()
    f2 = fig_fan()
    proj_html = projection_section()
    f6, real_table, real_meta = fig_real_vs_dca()
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
    nav = "\n".join(f'<a href="#{pid}">{label}</a>' for pid, label in PANELS)
    html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>DCA outcome distributions — QQQ vs SPY</title><style>{CSS}</style></head><body>
<aside class="sidenav">
<div class="navinner">
<div class="navtitle">DCA dashboard</div>
{nav}
</div>
</aside>
<main>
<h1>DCA outcome distributions — QQQ vs SPY</h1>
<p>Interactive companion to the committed <code>results/</code> snapshots. Total-return
prices, USD, pre-tax; data window {window} (offline <code>data/*.csv</code>). The lead view
is the <strong>distribution across randomized start dates</strong> — never one lucky or
unlucky line; use the sidebar to switch views. Built by <code>build_dashboard.py</code>
from the Sprint 1 CSV contract; it re-simulates nothing, so these numbers match
<code>results/random_windows.md</code> exactly.</p>
<div class="warn">Honesty caveats: the baby's 100% QQQ win-rate is a <strong>sample-length
artifact</strong> — ~27 yr of history means the 18-yr "windows" heavily overlap one macro
path in which Nasdaq concentration was never punished end-to-end. Treat concentration risk
as <em>not disproven</em>, not absent. Both scenarios put a ~40–47% balance drawdown on the
table (Outcome distribution notes, Bull/bear cycles spans).</div>

<section class="panel" id="distribution">
<h2>Outcome distribution (the headline view)</h2>
<p class="note">{dist_notes}</p>
{div(f1, 1, first=True)}
</section>

<section class="panel" id="fan">
<h2>Percentile fan — the spread as it unfolds</h2>
<p class="note">Cross-window p10–p90 band and p50 line of portfolio value ÷ money put in,
at each elapsed step (from <code>results/fan_*.csv</code>). Dotted line = break-even. The
terminal p50 sits a hair below the windows-CSV multiple p50 by design (per-step cross-window
percentile, truncated to the shortest window) — see SPRINT_PLAN Sprint 1 note.</p>
{div(f2, 2)}
</section>

<section class="panel" id="calculator">
<h2>Projection calculator — what the window distribution says about <em>your</em> plan</h2>
<p class="note">Deposit, cadence, horizon, lump, fee and QQQ/SPY mix are recomputed
client-side from the committed <code>results/projection_factors.csv</code> — the engine's
per-window linear factors over the same {RANDOM_N:,} random start dates (seed 42) as the
Outcome distribution view, so the Baby preset reproduces
<code>results/random_windows.md</code> exactly. The headline is the p10/p50/p90
<strong>range</strong>; the assumed-rate figure is a labelled intuition check, not
evidence.</p>
{proj_html}
</section>

<section class="panel" id="real">
<h2>My real portfolio vs the same money drip-fed into SPY/QQQ</h2>
<p class="note">Validation of a real track record: NZ${real_meta['invested_nzd']:,.0f} of
actual deposits ({REAL_DEPOSIT_START} → {REAL_DEPOSIT_END}) modelled as
{real_meta['n_buys']} <strong>even weekly buys</strong> of NZ${real_meta['weekly_nzd']:,.2f},
each converted at that week's NZDUSD spot (<strong>0% FX fee</strong> — the real IBKR-scale
cost), buying the week's first trading-day total-return close, then <strong>held with no
further buys</strong> to {real_meta['asof']}. All numbers from the committed
<code>results/real_vs_dca_*.csv</code>.</p>
{real_table}
{div(f6, 6)}
<div class="warn"><strong>Read honestly:</strong> the deposit schedule is an even-split
approximation — the real deposits were lumpy, and timing through 2020/2022 could move the
sim result materially, so the actual-portfolio XIRR is <em>approximate</em>. SPY/QQQ are
benchmarks picked <em>after</em> a decade they dominated (hindsight); a diversified or
stock-picking portfolio carries different risk. The actual portfolio is a single end point —
its path between deposits is unknown. Everything here is nominal USD, pre-tax.</div>
</section>

<section class="panel" id="cycles">
<h2>Bull/bear cycles the windows are sampling from</h2>
<p class="note">Growth of $1 (log). Shaded spans = QQQ bear episodes (any fall below
{BEAR_THRESHOLD:.0%} from a running peak, shaded peak → recovery), computed with the same
drawdown definition as the engine. The {worst['depth']:.0%} dot-com span
({worst['start'].date()} → {worst['end'].date()}) is the risk the randomized windows
under-sample — it appears in full in no completed 18-yr window.</p>
{div(f3, 4)}
</section>

<section class="panel" id="orders">
<h2>Orders on a chart — ONE illustrative path (not evidence)</h2>
<p class="note"><strong>This is a single start date</strong> — exactly what the rest of this
page exists to warn against. It is here only to show the mechanics of weekly DCA (buys land
in crashes too) on the full-history QQQ path. Judge outcomes by the Outcome distribution
and Percentile fan views, not this.</p>
{div(f4, 5)}
</section>

<p class="foot">Generated by <code>python3 build_dashboard.py</code> — reads committed
<code>results/*.csv</code> + <code>data/*.csv</code>, computes no new evidence. Plotly
embedded; opens offline. See <code>results/random_windows.md</code> and
<code>SPRINT_PLAN.md</code> for methodology and caveats.</p>
</main>
<script>{TAB_JS}</script>
</body></html>"""
    with open(OUT, "w") as f:
        f.write(html)
    shutil.copyfile(OUT, "docs/dashboard.html")   # published via GitHub Pages next to index.html
    return OUT


if __name__ == "__main__":
    out = build()
    print(f"[dashboard] wrote {out}")
