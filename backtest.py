"""
etf_backtest — a basic-but-honest backtest of SPY vs QQQ for two use cases:

  1. Baby:  weekly dollar-cost-averaging (DCA), long horizon, into QQQ/QQQM.
  2. Wife:  lump sum + monthly DCA into the S&P 500 (SPY, proxy for a NZ S&P 500 PIE fund).

Design goals:
  - Use TOTAL-return prices (adjusted close), so dividends are reinvested.
  - Report money-weighted return (XIRR) for DCA, not just total return — that's the
    number that actually reflects what a drip-feed investor earns.
  - Expose PERIOD BIAS: QQQ's "higher return" is highly dependent on when you measure.
    The script prints CAGR for several start dates and shows QQQ's dot-com drawdown,
    so you don't fool yourself with a 2010-onward sample.

Deliberate simplifications (all flagged; easy to extend):
  - Returns are in USD. The NZD/USD layer (unhedged) is NOT modelled here. For the
    baby's US-ETF that's a real extra source of variance; add NZDUSD=X to overlay it.
  - Fund TER is already inside the ETF's price (NAV is net of fees) — so it is NOT
    subtracted again. The only EXTRA cost modelled is the platform FX fee per contribution.
  - Tax (PIE vs FIF) is a separate after-the-fact layer and is not modelled.

Run:  python backtest.py
Deps: pandas numpy yfinance matplotlib   (pip install -r requirements.txt)
"""

from __future__ import annotations
import sys
import argparse
from dataclasses import dataclass
import numpy as np
import pandas as pd

# --------------------------------------------------------------------------------------
# CONFIG — edit these
# --------------------------------------------------------------------------------------
TICKERS = ["SPY", "QQQ"]          # long history; QQQM (2020+) is same index as QQQ, lower fee
START = "1999-03-10"              # QQQ inception; SPY goes back to 1993
FX_FEE = 0.005                    # 0.5% platform FX per contribution (Hatch/Sharesies). PIE funds = 0.0
WEEKLY_CONTRIB = 100.0           # baby: $/week
WIFE_LUMP = 20000.0              # wife: initial lump
WIFE_MONTHLY = 500.0             # wife: $/month
SUBPERIOD_STARTS = ["1999-03-10", "2000-03-01", "2010-01-01", "2015-01-01", "2020-01-01"]
SAVE_PLOTS = True

# Sprint 1 — randomized-window study
RANDOM_N = 1000                  # number of random start dates per scenario
BABY_YEARS = 18                  # baby horizon: 18-yr weekly-DCA windows
WIFE_YEARS = 10                  # wife horizon: ~10-yr lump+monthly windows
SEED = 42                        # default RNG seed (override with --seed)

# Sprint 2 — real-world overlays for the baby (QQQ) decision
TWINS = [("QQQM", "QQQ"), ("VOO", "SPY")]   # (cheaper share class, its long-history twin)
FX_TICKER = "NZDUSD=X"                        # USD per 1 NZD; offline: data/NZDUSD=X.csv

TRADING_DAYS = 252


# --------------------------------------------------------------------------------------
# Data
# --------------------------------------------------------------------------------------
def load_prices(tickers, start) -> pd.DataFrame:
    """Adjusted (total-return) close, one column per ticker. Falls back to local CSVs."""
    try:
        import yfinance as yf
        frames = {}
        for t in tickers:
            s = yf.download(t, start=start, auto_adjust=True, progress=False)["Close"]
            frames[t] = s.squeeze()
        df = pd.DataFrame(frames).dropna(how="all")
        if df.empty:
            raise RuntimeError("empty download")
        return df.dropna()
    except Exception as e:  # offline / blocked network fallback
        print(f"[data] yfinance failed ({e}); trying local CSVs data/<TICKER>.csv", file=sys.stderr)
        frames = {}
        for t in tickers:
            s = pd.read_csv(f"data/{t}.csv", index_col=0, parse_dates=True)["Close"]
            frames[t] = s
        return pd.DataFrame(frames).dropna()


def load_series(ticker) -> pd.Series:
    """One ticker's FULL history. Sprint 2 loads each series alone: forcing QQQM/VOO/FX
    into the shared aligned frame would dropna the common window down to QQQM's 2020 start."""
    return load_prices([ticker], START)[ticker].dropna()


# --------------------------------------------------------------------------------------
# Metrics
# --------------------------------------------------------------------------------------
def cagr(prices: pd.Series) -> float:
    years = (prices.index[-1] - prices.index[0]).days / 365.25
    return (prices.iloc[-1] / prices.iloc[0]) ** (1 / years) - 1


def annualized_vol(prices: pd.Series) -> float:
    return prices.pct_change().dropna().std() * np.sqrt(TRADING_DAYS)


def sharpe(prices: pd.Series, rf: float = 0.0) -> float:
    return (cagr(prices) - rf) / annualized_vol(prices)


def max_drawdown(prices: pd.Series) -> dict:
    """Worst peak-to-trough fall, with peak/trough dates and time to recover."""
    running_max = prices.cummax()
    dd = prices / running_max - 1
    trough = dd.idxmin()
    peak = prices.loc[:trough].idxmax()
    peak_val = prices.loc[peak]
    after = prices.loc[trough:]
    recovered = after[after >= peak_val]
    recovery = recovered.index[0] if len(recovered) else None
    return {
        "max_dd": dd.min(),
        "peak": peak.date(),
        "trough": trough.date(),
        "recovery": recovery.date() if recovery is not None else None,
        "recovery_years": (recovery - trough).days / 365.25 if recovery is not None else None,
    }


def calendar_years(prices: pd.Series) -> pd.Series:
    yr = prices.resample("YE").last()
    return yr.pct_change().dropna()


def summarize(prices: pd.Series) -> dict:
    dd = max_drawdown(prices)
    cy = calendar_years(prices)
    return {
        "CAGR": cagr(prices),
        "Vol": annualized_vol(prices),
        "Sharpe(rf=0)": sharpe(prices),
        "MaxDD": dd["max_dd"],
        "DD peak": dd["peak"],
        "DD trough": dd["trough"],
        "Recover(yrs)": dd["recovery_years"],
        "Best yr": cy.max(),
        "Worst yr": cy.min(),
        "%pos yrs": (cy > 0).mean(),
    }


# --------------------------------------------------------------------------------------
# Money-weighted return (XIRR) — solves for the annual rate that zeroes NPV.
# --------------------------------------------------------------------------------------
def xirr(cashflows: list[float], dates: list[pd.Timestamp]) -> float:
    t = np.array([(d - dates[0]).days / 365.25 for d in dates])
    cf = np.array(cashflows, dtype=float)

    def npv(r):
        return np.sum(cf / (1 + r) ** t)

    lo, hi = -0.9999, 10.0
    if npv(lo) * npv(hi) > 0:      # no sign change -> undefined
        return float("nan")
    for _ in range(200):           # bisection
        mid = (lo + hi) / 2
        v = npv(mid)
        if abs(v) < 1e-6:
            return mid
        if npv(lo) * v < 0:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


# --------------------------------------------------------------------------------------
# DCA simulators
# --------------------------------------------------------------------------------------
@dataclass
class DcaResult:
    invested: float
    final_value: float
    units: float
    xirr: float
    multiple: float          # final / invested
    curve: pd.DataFrame      # date, invested_cum, value


def _contribution_dates(prices: pd.Series, freq: str) -> pd.Series:
    """Price on/after each period boundary (weekly 'W' or month-start 'MS')."""
    return prices.resample(freq).first().dropna()


def simulate_dca(prices: pd.Series, amount: float, freq: str,
                 fx_fee: float = 0.0, lump: float = 0.0) -> DcaResult:
    buys = _contribution_dates(prices, freq)
    units = 0.0
    invested = 0.0
    cfs, cf_dates, curve = [], [], []

    if lump > 0:
        p0 = buys.iloc[0]
        deployed = lump * (1 - fx_fee)
        units += deployed / p0
        invested += lump
        cfs.append(-lump); cf_dates.append(buys.index[0])

    for dt, px in buys.items():
        deployed = amount * (1 - fx_fee)
        units += deployed / px
        invested += amount
        cfs.append(-amount); cf_dates.append(dt)
        curve.append((dt, invested, units * px))

    final_px = prices.iloc[-1]
    final_value = units * final_px
    cfs.append(final_value); cf_dates.append(prices.index[-1])

    curve_df = pd.DataFrame(curve, columns=["date", "invested_cum", "value"]).set_index("date")
    return DcaResult(
        invested=invested, final_value=final_value, units=units,
        xirr=xirr(cfs, cf_dates), multiple=final_value / invested, curve=curve_df,
    )


# --------------------------------------------------------------------------------------
# Sprint 1 — randomized-window distribution study (CLAUDE.md principle #3)
#
# Replace a single start-date CAGR with the SPREAD of outcomes over N random windows.
# Both tickers are sampled with the same seed on the same aligned index, so the start
# dates are identical across QQQ/SPY — the head-to-head "% QQQ beats SPY" is paired.
# --------------------------------------------------------------------------------------
def _dca_value_drawdown(curve: pd.DataFrame) -> float:
    """Worst peak-to-trough fall of the portfolio VALUE during accumulation (what the
    investor actually sees in their balance)."""
    v = curve["value"]
    return (v / v.cummax() - 1).min()


def sample_start_dates(index: pd.DatetimeIndex, years: int, n: int, seed: int) -> list:
    """N random trading days that leave a full `years`-long window before the data ends."""
    cutoff = index[-1] - pd.DateOffset(years=years)
    n_valid = int((index <= cutoff).sum())
    if n_valid < 1:
        raise ValueError(f"history too short for {years}-yr windows")
    rng = np.random.default_rng(seed)
    return [index[i] for i in rng.integers(0, n_valid, size=n)]


def _iter_windows(prices: pd.DataFrame, ticker: str, years: int, freq: str, n: int,
                  amount: float, fx_fee: float, lump: float, seed: int):
    """Yield (start, end, DcaResult) for each of N random `years`-long windows."""
    s = prices[ticker].dropna()
    for st in sample_start_dates(s.index, years, n, seed):
        window = s.loc[st:st + pd.DateOffset(years=years)]
        if len(window) < 50:
            continue
        yield st, window.index[-1], simulate_dca(window, amount, freq, fx_fee=fx_fee, lump=lump)


def simulate_random_windows(prices: pd.DataFrame, ticker: str, years: int, freq: str,
                            n: int, amount: float, fx_fee: float = 0.0, lump: float = 0.0,
                            seed: int = SEED) -> pd.DataFrame:
    """Run the DCA sim over N random `years`-long windows; one row per window."""
    rows = [{"start": st, "end": end, "multiple": r.multiple, "xirr": r.xirr,
             "max_dd": _dca_value_drawdown(r.curve)}
            for st, end, r in _iter_windows(prices, ticker, years, freq, n, amount,
                                            fx_fee, lump, seed)]
    return pd.DataFrame(rows)


def print_random_windows(prices: pd.DataFrame, label: str, years: int, freq: str,
                         amount: float, fx_fee: float, lump: float, n: int,
                         seed: int) -> dict:
    print(f"\n=== Randomized-window study — {label}: {n} random {years}-yr {freq} windows ===")
    results = {}
    for t in prices.columns:
        df = simulate_random_windows(prices, t, years, freq, n, amount,
                                     fx_fee=fx_fee, lump=lump, seed=seed)
        results[t] = df
        q = df[["xirr", "multiple", "max_dd"]].quantile([0.1, 0.5, 0.9])
        print(f"\n  {t}  ({len(df)} windows, {df['start'].min().date()} → "
              f"{df['start'].max().date()} starts)")
        print(f"    XIRR      p10 {pct(q.at[0.1,'xirr'])}   p50 {pct(q.at[0.5,'xirr'])}   "
              f"p90 {pct(q.at[0.9,'xirr'])}")
        print(f"    Multiple  p10 {q.at[0.1,'multiple']:.2f}x   p50 {q.at[0.5,'multiple']:.2f}x   "
              f"p90 {q.at[0.9,'multiple']:.2f}x")
        print(f"    Worst intra-window value drawdown: median {pct(q.at[0.5,'max_dd'])}   "
              f"p10(worst decile) {pct(q.at[0.1,'max_dd'])}")

    if "QQQ" in results and "SPY" in results:
        paired = pd.concat([results["QQQ"].set_index("start")["xirr"],
                            results["SPY"].set_index("start")["xirr"]],
                           axis=1, keys=["QQQ", "SPY"]).dropna()
        gap = paired["QQQ"] - paired["SPY"]
        win = (gap > 0).mean()
        print(f"\n  Head-to-head (paired starts): QQQ beat SPY in {pct(win)} of {len(paired)} "
              f"windows.")
        print(f"    XIRR edge (QQQ−SPY): median {pct(gap.median())}   worst {pct(gap.min())}   "
              f"best {pct(gap.max())}")
    return results


# --------------------------------------------------------------------------------------
# Sprint 1 task 5 — persist per-window results as the Sprint 4 data contract.
# CSVs, not just a PNG, so the dashboard READS these and never re-simulates.
#   results/windows_<scenario>_<ticker>.csv : one row per window (multiple, XIRR, max_dd)
#   results/fan_<scenario>_<ticker>.csv     : p10/p50/p90 wealth-multiple vs elapsed years
# --------------------------------------------------------------------------------------
def persist_window_data(prices: pd.DataFrame, scenario: str, years: int, freq: str,
                        amount: float, fx_fee: float, lump: float, n: int, seed: int,
                        outdir: str = "results"):
    per_year = {"W": 52, "MS": 12}[freq]
    for t in prices.columns:
        rows, trajs = [], []
        for st, end, r in _iter_windows(prices, t, years, freq, n, amount, fx_fee, lump, seed):
            rows.append({"start": st.date(), "end": end.date(), "multiple": r.multiple,
                         "xirr": r.xirr, "max_dd": _dca_value_drawdown(r.curve)})
            trajs.append((r.curve["value"] / r.curve["invested_cum"]).to_numpy())

        pd.DataFrame(rows).to_csv(f"{outdir}/windows_{scenario}_{t}.csv", index=False)

        # Percentile fan: align windows on a common contribution grid (they differ by a
        # step or two), stack, take cross-window percentiles at each elapsed step.
        length = min(len(x) for x in trajs)
        mat = np.vstack([x[:length] for x in trajs])
        fan = pd.DataFrame({
            "years": np.arange(length) / per_year,
            "wealth_mult_p10": np.percentile(mat, 10, axis=0),
            "wealth_mult_p50": np.percentile(mat, 50, axis=0),
            "wealth_mult_p90": np.percentile(mat, 90, axis=0),
        })
        fan.to_csv(f"{outdir}/fan_{scenario}_{t}.csv", index=False)
    print(f"[data] wrote results/windows_{scenario}_*.csv + fan_{scenario}_*.csv")


# --------------------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------------------
def pct(x, dp=1):
    return "n/a" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x*100:.{dp}f}%"


def print_metrics(prices: pd.DataFrame):
    print("\n=== Per-ticker metrics (full common history, total return, USD) ===")
    rows = {t: summarize(prices[t].dropna()) for t in prices.columns}
    tbl = pd.DataFrame(rows).T
    for c in ["CAGR", "Vol", "MaxDD", "Best yr", "Worst yr", "%pos yrs"]:
        tbl[c] = tbl[c].map(lambda v: pct(v))
    tbl["Sharpe(rf=0)"] = tbl["Sharpe(rf=0)"].map(lambda v: f"{v:.2f}")
    tbl["Recover(yrs)"] = tbl["Recover(yrs)"].map(lambda v: "n/a" if v is None or (isinstance(v,float) and np.isnan(v)) else f"{v:.1f}")
    print(tbl.to_string())


def print_period_bias(prices: pd.DataFrame):
    print("\n=== Period bias: CAGR by start date (why 'QQQ wins' depends on the window) ===")
    out = {}
    for start in SUBPERIOD_STARTS:
        seg = prices[prices.index >= start].dropna()
        if len(seg) < 50:
            continue
        out[f"from {start[:7]}"] = {t: pct(cagr(seg[t])) for t in prices.columns}
    print(pd.DataFrame(out).T.to_string())


def print_scenarios(prices: pd.DataFrame):
    print("\n=== Scenario 1 — BABY: weekly DCA (FX fee applied per contribution) ===")
    for t in prices.columns:
        r = simulate_dca(prices[t].dropna(), WEEKLY_CONTRIB, "W", fx_fee=FX_FEE)
        print(f"  {t}: invested ${r.invested:,.0f} -> ${r.final_value:,.0f} "
              f"({r.multiple:.2f}x)  XIRR {pct(r.xirr)}")

    print("\n=== Scenario 2 — WIFE: lump + monthly DCA (PIE fund => FX fee = 0) ===")
    for t in prices.columns:
        r = simulate_dca(prices[t].dropna(), WIFE_MONTHLY, "MS", fx_fee=0.0, lump=WIFE_LUMP)
        print(f"  {t}: invested ${r.invested:,.0f} -> ${r.final_value:,.0f} "
              f"({r.multiple:.2f}x)  XIRR {pct(r.xirr)}")
    print("\n  (SPY here is a stand-in for a NZ S&P 500 PIE fund's underlying index.)")


def make_plots(prices: pd.DataFrame):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as e:
        print(f"[plots] skipped: {e}", file=sys.stderr)
        return

    fig, ax = plt.subplots(2, 1, figsize=(10, 9))
    norm = prices / prices.iloc[0]
    norm.plot(ax=ax[0], logy=True)
    ax[0].set_title("Growth of $1 (total return, log scale)")
    ax[0].set_ylabel("x initial")

    for t in prices.columns:
        s = prices[t].dropna()
        dd = s / s.cummax() - 1
        dd.plot(ax=ax[1], label=t)
    ax[1].set_title("Drawdown from prior peak")
    ax[1].set_ylabel("drawdown")
    ax[1].legend()
    fig.tight_layout()
    fig.savefig("backtest_charts.png", dpi=120)
    print("\n[plots] saved backtest_charts.png")


def make_random_plots(baby: dict, wife: dict):
    """Overlaid XIRR histograms, QQQ vs SPY, for both scenarios."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as e:
        print(f"[plots] random-window plot skipped: {e}", file=sys.stderr)
        return

    fig, ax = plt.subplots(2, 1, figsize=(10, 9))
    for axis, (title, res) in zip(ax, [("Baby — 18-yr weekly DCA", baby),
                                       ("Wife — 10-yr lump + monthly DCA", wife)]):
        for t in res:
            x = res[t]["xirr"].dropna() * 100
            axis.hist(x, bins=40, alpha=0.5, label=f"{t} (median {x.median():.1f}%)")
            axis.axvline(x.median(), linestyle="--", linewidth=1)
        axis.set_title(f"{title}: XIRR distribution over random windows")
        axis.set_xlabel("annualized XIRR (%)")
        axis.set_ylabel("windows")
        axis.legend()
    fig.tight_layout()
    fig.savefig("results/random_windows.png", dpi=120)
    print("[plots] saved results/random_windows.png")


# --------------------------------------------------------------------------------------
# Sprint 2 — real-world overlays for the baby (QQQ) decision
#   1. Do QQQM / VOO track their long-history twins?  (tracking difference vs daily noise)
#   2. NZDUSD overlay: the unhedged currency swing on a USD-denominated ETF.
#   3. The 0.5% platform FX fee per contribution — how much does it actually cost?
# --------------------------------------------------------------------------------------
def print_twins(pairs):
    print("\n=== Sprint 2 · Task 1 — do the cheaper share classes track their twins? ===")
    print("  Tracking difference = annualized total-return gap (the number that matters over a hold).")
    for cheap, twin in pairs:
        df = pd.concat([load_series(cheap), load_series(twin)], axis=1, keys=[cheap, twin]).dropna()
        ca, cb = cagr(df[cheap]), cagr(df[twin])
        r = df.pct_change().dropna()
        te = (r[cheap] - r[twin]).std() * np.sqrt(TRADING_DAYS)
        print(f"  {cheap} vs {twin}  ({df.index[0].date()}→{df.index[-1].date()}, "
              f"{(df.index[-1]-df.index[0]).days/365.25:.1f}yr): tracking diff {pct(ca-cb, 2)}/yr  "
              f"(CAGR {pct(ca)} vs {pct(cb)}), daily corr {r[cheap].corr(r[twin]):.4f}, "
              f"daily TE {pct(te, 2)}/yr")
    print("  (daily TE is mean-reverting close-print/dividend-timing noise; it nets to the tiny")
    print("   tracking difference above, ≈ the TER gap. QQQM/VOO are faithful, cheaper twins.)")


def print_fx_fee_drag():
    print("\n=== Sprint 2 · Task 3 — 0.5% platform FX fee drag (baby weekly DCA into QQQ) ===")
    q = load_series("QQQ")
    r_fee = simulate_dca(q, WEEKLY_CONTRIB, "W", fx_fee=FX_FEE)
    r_no = simulate_dca(q, WEEKLY_CONTRIB, "W", fx_fee=0.0)
    print(f"  {r_fee.invested/WEEKLY_CONTRIB:.0f} weekly buys over "
          f"{(q.index[-1]-q.index[0]).days/365.25:.0f}yr, invested ${r_fee.invested:,.0f}")
    print(f"    with 0.5% FX fee: ${r_fee.final_value:,.0f}  XIRR {pct(r_fee.xirr)}")
    print(f"    no fee:           ${r_no.final_value:,.0f}  XIRR {pct(r_no.xirr)}")
    print(f"    drag: ${r_no.final_value-r_fee.final_value:,.0f} = exactly "
          f"{pct(1-r_fee.final_value/r_no.final_value, 2)} of terminal wealth "
          f"(horizon-independent), XIRR drag {pct(r_no.xirr-r_fee.xirr, 3)}/yr")


def _dual_currency_dca(prices, fx, amount, freq, fx_fee):
    """DCA valued two ways from the SAME nominal contribution: as USD, vs as NZD converted
    to USD at each buy's spot (fx = USD per 1 NZD). Only difference is the currency layer."""
    buys = _contribution_dates(prices, freq)
    u_usd = u_nzd = 0.0
    cf_usd, cf_nzd, dts = [], [], []
    for dt, px in buys.items():
        rate = fx.reindex([dt], method="ffill").iloc[0]
        u_usd += amount * (1 - fx_fee) / px
        u_nzd += (amount * rate) * (1 - fx_fee) / px
        cf_usd.append(-amount); cf_nzd.append(-amount); dts.append(dt)
    fpx = prices.iloc[-1]
    frate = fx.reindex([prices.index[-1]], method="ffill").iloc[0]
    cf_usd.append(u_usd * fpx); cf_nzd.append(u_nzd * fpx / frate); dts.append(prices.index[-1])
    return xirr(cf_usd, dts), xirr(cf_nzd, dts), frate


def print_nzd_overlay():
    print("\n=== Sprint 2 · Task 2 — NZDUSD overlay: unhedged FX on the baby's US ETF ===")
    q = load_series("QQQ")
    fx = load_series(FX_TICKER)             # USD per 1 NZD
    qw = q.loc[fx.index[0]:]                # FX history starts 2003-12; run both legs on it
    x_usd, x_nzd, frate = _dual_currency_dca(qw, fx, WEEKLY_CONTRIB, "W", FX_FEE)
    fxr = fx.pct_change().dropna()
    drift = (fx.iloc[0] / frate) ** (365.25 / (fx.index[-1] - fx.index[0]).days) - 1
    print(f"  window {qw.index[0].date()}→{qw.index[-1].date()} "
          f"({(qw.index[-1]-qw.index[0]).days/365.25:.1f}yr); NZDUSD {fx.iloc[0]:.4f}→{frate:.4f} "
          f"(range {fx.min():.4f}–{fx.max():.4f})")
    print(f"    USD-terms XIRR {pct(x_usd)}   NZD-terms XIRR {pct(x_nzd)}   "
          f"FX contribution {pct(x_nzd-x_usd)}/yr")
    print(f"    NZDUSD annualized vol {pct(fxr.std()*np.sqrt(TRADING_DAYS))}, "
          f"net USD-vs-NZD drift {pct(drift)}/yr")
    print("  (Positive here is backward-looking: the NZD fell vs USD over this window. Unhedged,")
    print("   this ~12%/yr currency swing cuts BOTH ways over the baby's 18yr — a labelled layer.)")


def make_sprint2_plot():
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as e:
        print(f"[plots] sprint2 plot skipped: {e}", file=sys.stderr)
        return
    fig, ax = plt.subplots(2, 1, figsize=(10, 8))
    for cheap, twin in TWINS:
        df = pd.concat([load_series(cheap), load_series(twin)], axis=1, keys=[cheap, twin]).dropna()
        ratio = (df[cheap] / df[cheap].iloc[0]) / (df[twin] / df[twin].iloc[0])
        ratio.plot(ax=ax[0], label=f"{cheap} / {twin}")
    ax[0].axhline(1.0, color="k", lw=0.6, ls=":")
    ax[0].set_title("Cheaper share class vs its twin — cumulative total-return ratio (≈1.0 = tracks)")
    ax[0].set_ylabel("ratio")
    ax[0].legend()
    load_series(FX_TICKER).plot(ax=ax[1])
    ax[1].set_title("NZDUSD=X (USD per 1 NZD) — the unhedged swing on the baby's US ETF")
    ax[1].set_ylabel("USD per NZD")
    fig.tight_layout()
    fig.savefig("results/sprint2_overlays.png", dpi=120)
    print("[plots] saved results/sprint2_overlays.png")


# --------------------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="ETF backtest & DCA distribution study")
    ap.add_argument("--seed", type=int, default=SEED, help="RNG seed for random windows")
    ap.add_argument("--n", type=int, default=RANDOM_N, help="number of random windows")
    args = ap.parse_args()

    prices = load_prices(TICKERS, START)
    prices = prices.dropna()  # align to common window
    print(f"Loaded {prices.columns.tolist()}  {prices.index[0].date()} -> {prices.index[-1].date()}  "
          f"({len(prices)} trading days)")
    print_metrics(prices)
    print_period_bias(prices)
    print_scenarios(prices)

    baby = print_random_windows(prices, "BABY", BABY_YEARS, "W", WEEKLY_CONTRIB,
                                fx_fee=FX_FEE, lump=0.0, n=args.n, seed=args.seed)
    wife = print_random_windows(prices, "WIFE", WIFE_YEARS, "MS", WIFE_MONTHLY,
                                fx_fee=0.0, lump=WIFE_LUMP, n=args.n, seed=args.seed)

    persist_window_data(prices, "baby", BABY_YEARS, "W", WEEKLY_CONTRIB,
                        fx_fee=FX_FEE, lump=0.0, n=args.n, seed=args.seed)
    persist_window_data(prices, "wife", WIFE_YEARS, "MS", WIFE_MONTHLY,
                        fx_fee=0.0, lump=WIFE_LUMP, n=args.n, seed=args.seed)

    print_twins(TWINS)
    print_nzd_overlay()
    print_fx_fee_drag()

    if SAVE_PLOTS:
        make_plots(prices)
        make_random_plots(baby, wife)
        make_sprint2_plot()
    print("\nDone. Edit the CONFIG block at the top to change amounts, tickers, or dates.")


if __name__ == "__main__":
    main()
