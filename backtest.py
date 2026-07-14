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

# Sprint 3 — after-tax layer + cadence sensitivity for the wife (SPY/PIE) decision
FDR_RATE = 0.05                  # FIF/PIE "fair dividend rate": deemed 5% of opening value is income
PIE_PIR = 0.28                   # PIE prescribed-investor-rate cap (no FIF, no FX)
MARGINAL_RATES = [0.33, 0.39]    # a direct FIF hold is taxed at the investor's marginal rate

# Sprint 5 — projection factor grid for the dashboard's client-side calculator
PROJ_HORIZON_YEARS = range(1, 19)   # 1..18-yr windows, both cadences, RANDOM_N windows each

# Sprint 8b — dip double-down: daily DCA, 2x on a big down day, skip the next calm day
DIP_DAILY_BASE = 100.0                 # $/trading day
DIP_THRESHOLDS = [0.01, 0.02, 0.03]    # close-to-close daily drop that triggers the double

# Sprint 7 — real-portfolio validation: the user's actual NZD deposits vs a weekly DCA
REAL_DEPOSIT_TOTAL_NZD = 90_000.0   # total deposited (NZD), modelled as an even weekly split
REAL_DEPOSIT_START = "2019-02-25"   # first real deposit
REAL_DEPOSIT_END = "2024-10-11"     # last real deposit; the sim holds (no buys) after this
REAL_PORTFOLIO_USD = 82_740.04      # actual portfolio value at REAL_PORTFOLIO_ASOF
REAL_PORTFOLIO_ASOF = "2026-07-10"  # the Friday close the actual value was read at
REAL_FX_FEE = 0.0                   # user's real FX cost is IBKR-scale (~0), not Hatch's 0.5%
# Sprint 10 — the same NZD, same window, deployed under 3 cadences on the real chart:
# weekly (Sprint 7 baseline), even-daily, and buy-the-dip (Sprint 8b rule at this threshold).
REAL_STRATEGIES = ["weekly", "daily", "dip"]
REAL_DIP_THRESHOLD = 0.03           # the "buy the dip" line: 2x on a close <= -3% (see DIP_THRESHOLDS)

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


def simulate_dca(prices: pd.Series, amount: float | pd.Series, freq: str,
                 fx_fee: float = 0.0, lump: float = 0.0,
                 buys: pd.Series | None = None) -> DcaResult:
    """`amount` is either a fixed $ per buy, or a pd.Series of per-buy dollars indexed
    like `buys` (Sprint 8b variable schedules). Zero-amount days must not be in `buys`."""
    if buys is None:
        buys = _contribution_dates(prices, freq)
    per_buy = amount if isinstance(amount, pd.Series) else None
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
        a = per_buy.at[dt] if per_buy is not None else amount
        deployed = a * (1 - fx_fee)
        units += deployed / px
        invested += a
        cfs.append(-a); cf_dates.append(dt)
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
# Sprint 5 — projection factor grid (client-side calculator data contract)
#
# The dashboard's projection calculator recomputes the outcome distribution for ARBITRARY
# inputs (amount, lump, fee, ticker weights) without re-running Python. simulate_dca's
# final value is exactly linear in (lump, amount) for a fixed window/cadence/ticker:
#     final = (1 - fx_fee) * [ lump * g0 + amount * s ]
#     g0 = P(end) / P(first buy)          s = P(end) * sum_i 1 / P(buy_i)
# so we persist per-window (g0, s, n_buys) over a horizons x cadence grid; the dashboard
# JS only takes linear combinations + percentiles — the engine stays the sole source of
# numbers. Same seed and start-sampling as Sprint 1, so the calculator's Baby preset
# replays the exact windows behind results/windows_baby_QQQ.csv.
# --------------------------------------------------------------------------------------
def projection_factors(prices: pd.DataFrame, years: int, freq: str,
                       n: int = RANDOM_N, seed: int = SEED) -> pd.DataFrame:
    """Per-window linear factors (g0, s) per ticker + shared n_buys, for N random
    `years`-long windows. Starts are sampled once on the aligned frame, so they are
    shared across tickers — a weight-blend of finals stays correlation-preserving."""
    rows = []
    for st in sample_start_dates(prices.index, years, n, seed):
        window = prices.loc[st:st + pd.DateOffset(years=years)]
        if len(window) < 50:
            continue
        buys = window.resample(freq).first().dropna()   # _contribution_dates, both columns
        end_px = window.iloc[-1]
        row = {"start": st.date(), "end": window.index[-1].date(), "n_buys": len(buys)}
        for t in prices.columns:
            row[f"g0_{t}"] = end_px[t] / buys[t].iloc[0]
            row[f"s_{t}"] = end_px[t] * (1.0 / buys[t]).sum()
        rows.append(row)
    return pd.DataFrame(rows)


def _check_factor_contract(prices: pd.DataFrame, factors: pd.DataFrame,
                           years: int, freq: str):
    """The factor formula must reproduce simulate_dca's final_value exactly — one window
    per grid cell, one lump and one no-lump case. Fails loudly on any drift."""
    row = factors.iloc[0]
    st = pd.Timestamp(row["start"])
    cases = [(prices.columns[0], 250.0, 10000.0), (prices.columns[-1], 100.0, 0.0)]
    for t, amount, lump in cases:
        window = prices[t].loc[st:st + pd.DateOffset(years=years)]
        ref = simulate_dca(window, amount, freq, fx_fee=FX_FEE, lump=lump).final_value
        via = (1 - FX_FEE) * (lump * row[f"g0_{t}"] + amount * row[f"s_{t}"])
        assert np.isclose(ref, via), f"factor contract drift: {freq} {years}y {t}: {ref} != {via}"


def persist_projection_factors(prices: pd.DataFrame, horizons=PROJ_HORIZON_YEARS,
                               n: int = RANDOM_N, seed: int = SEED,
                               outdir: str = "results"):
    frames = []
    for years in horizons:
        for freq in ("W", "MS"):
            f = projection_factors(prices, years, freq, n=n, seed=seed)
            _check_factor_contract(prices, f, years, freq)
            f.insert(0, "freq", freq)
            f.insert(1, "years", years)
            frames.append(f)
    out = pd.concat(frames, ignore_index=True)
    out.to_csv(f"{outdir}/projection_factors.csv", index=False, float_format="%.6g")
    print(f"[data] wrote {outdir}/projection_factors.csv "
          f"({len(out)} rows: {len(list(horizons))} horizons x W/MS, n={n} windows each)")


# --------------------------------------------------------------------------------------
# Sprint 8 — does the buy day-of-week matter? (weekly DCA anchored Mon..Fri)
#
# The base sims buy at the FIRST trading day of each Mon-Sun week (resample('W').first()),
# i.e. Monday's close, rolling to Tuesday on a Monday holiday. Here every anchor day gets
# the same treatment: buy the target weekday's close; on a holiday roll FORWARD within the
# same week (Mon holiday -> Tue), and only when nothing later exists in that week (Fri
# holiday) roll BACK (-> Thu). Windows are PAIRED: the same random 18-yr starts (Sprint 1
# seed) are re-run under all five anchors, so the per-window max-min spread isolates the
# weekday effect from window luck. A window starting mid-week takes its first buy at the
# anchor's next occurrence — exactly what a real drip-feed starter would do.
# --------------------------------------------------------------------------------------
WEEKDAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri"]


def weekday_buy_dates(prices: pd.Series, weekday: int) -> pd.DatetimeIndex:
    """One buy date per Mon-Sun week: first trading day with dow >= `weekday` (0=Mon),
    else the week's last trading day (only a Fri/short-week closure falls backward)."""
    idx = prices.index
    wk = idx.to_period("W-SUN")
    elig = idx.weekday >= weekday
    first_elig = pd.Series(idx[elig], index=wk[elig]).groupby(level=0).first()
    last_all = pd.Series(idx, index=wk).groupby(level=0).last()
    return pd.DatetimeIndex(first_elig.reindex(last_all.index).fillna(last_all).values)


def weekday_anchor_study(prices: pd.DataFrame, years: int = BABY_YEARS,
                         n: int = RANDOM_N, seed: int = SEED,
                         outdir: str = "results") -> pd.DataFrame:
    """Full-history + N paired random windows, weekly DCA under each Mon..Fri anchor.
    Persists results/weekday_anchor.csv (scope = 'full' | 'window') for the dashboard."""
    rows = []
    for t in prices.columns:
        s = prices[t].dropna()
        anchor_buys = {d: s.loc[weekday_buy_dates(s, d)] for d in range(5)}
        for d, label in enumerate(WEEKDAY_LABELS):
            r = simulate_dca(s, WEEKLY_CONTRIB, "W", fx_fee=FX_FEE, buys=anchor_buys[d])
            rows.append({"scope": "full", "ticker": t, "anchor": label,
                         "start": s.index[0].date(), "end": s.index[-1].date(),
                         "xirr": r.xirr, "multiple": r.multiple})
        for st in sample_start_dates(s.index, years, n, seed):
            window = s.loc[st:st + pd.DateOffset(years=years)]
            if len(window) < 50:
                continue
            for d, label in enumerate(WEEKDAY_LABELS):
                buys = anchor_buys[d].loc[window.index[0]:window.index[-1]]
                r = simulate_dca(window, WEEKLY_CONTRIB, "W", fx_fee=FX_FEE, buys=buys)
                rows.append({"scope": "window", "ticker": t, "anchor": label,
                             "start": st.date(), "end": window.index[-1].date(),
                             "xirr": r.xirr, "multiple": r.multiple})
    df = pd.DataFrame(rows)
    df.to_csv(f"{outdir}/weekday_anchor.csv", index=False, float_format="%.6g")
    print(f"[data] wrote {outdir}/weekday_anchor.csv "
          f"({len(df)} rows: full history + {n} paired {years}-yr windows x 5 anchors)")
    return df


def print_weekday_anchor(df: pd.DataFrame):
    print("\n=== Sprint 8 — buy day-of-week: weekly DCA anchored Mon..Fri ===")
    full = df[df["scope"] == "full"]
    win = df[df["scope"] == "window"]
    for t in full["ticker"].unique():
        f = full[full["ticker"] == t].set_index("anchor")
        print(f"\n  {t} full history ({f['start'].iloc[0]} → {f['end'].iloc[0]}):")
        print("    " + "   ".join(f"{a} XIRR {pct(f.at[a, 'xirr'], 2)}"
                                  for a in WEEKDAY_LABELS))
        # duplicate random starts re-run the same deterministic window — drop before pivot
        w = (win[win["ticker"] == t].drop_duplicates(["start", "anchor"])
             .pivot(index="start", columns="anchor", values="xirr"))
        spread = w.max(axis=1) - w.min(axis=1)
        best = w.idxmax(axis=1).value_counts(normalize=True)
        med = {a: w[a].median() for a in WEEKDAY_LABELS}
        print("    windows p50 XIRR: " + "   ".join(f"{a} {pct(med[a], 2)}"
                                                    for a in WEEKDAY_LABELS))
        print(f"    paired per-window spread (max−min across anchors): "
              f"median {pct(spread.median(), 3)}   p90 {pct(spread.quantile(0.9), 3)}   "
              f"max {pct(spread.max(), 3)}")
        print("    best anchor by window: "
              + "  ".join(f"{a} {pct(best.get(a, 0.0), 0)}" for a in WEEKDAY_LABELS))
    print("  (Compare the spread to the p10→p90 window range in the Sprint 1 study — "
          "start-date luck, not weekday, is the variable that matters.)")


# --------------------------------------------------------------------------------------
# Sprint 8b — "double down on a bad day": daily DCA with a dip-triggered 2x buy.
#
# Rule (a skip-credit queue, per the household's own spec):
#   - buy $DIP_DAILY_BASE at every trading day's close;
#   - a day whose close-to-close return is <= -threshold buys 2x and queues ONE skip
#     credit (trigger days are never skipped, and always queue their own credit);
#   - a calm day with credits pending buys $0 and consumes one credit.
# Nearly cash-flow-neutral vs plain daily DCA: every extra $100 on a crash day is funded
# by a skipped calm day, so a PAIRED comparison against the plain daily baseline on the
# same random windows isolates the timing tilt. Fresh credit state per window.
# --------------------------------------------------------------------------------------
def dip_buy_schedule(prices: pd.Series, base: float = DIP_DAILY_BASE,
                     threshold: float = 0.03) -> pd.Series:
    """Per-trading-day contribution under the dip-double rule (0 / base / 2*base).
    Day 1 has no prior close (NaN return -> no trigger) and buys the base amount."""
    rets = prices.pct_change().to_numpy()
    amounts = np.empty(len(prices))
    credits = 0
    for i, r in enumerate(rets):
        if r <= -threshold:                # NaN on day 1 compares False
            amounts[i] = 2 * base
            credits += 1
        elif credits > 0:
            amounts[i] = 0.0
            credits -= 1
        else:
            amounts[i] = base
    return pd.Series(amounts, index=prices.index)


def _simulate_dip(window: pd.Series, threshold: float | None) -> tuple[DcaResult, int, int]:
    """One window under one variant (None = plain daily baseline). Returns the DcaResult
    plus the number of doubled and skipped days."""
    if threshold is None:
        sched = pd.Series(DIP_DAILY_BASE, index=window.index)
    else:
        sched = dip_buy_schedule(window, DIP_DAILY_BASE, threshold)
    live = sched[sched > 0]
    r = simulate_dca(window, live, "D", fx_fee=FX_FEE, buys=window[live.index])
    return r, int((sched == 2 * DIP_DAILY_BASE).sum()), int((sched == 0.0).sum())


def dip_double_study(prices: pd.DataFrame, thresholds=DIP_THRESHOLDS,
                     years: int = BABY_YEARS, n: int = RANDOM_N, seed: int = SEED,
                     outdir: str = "results") -> pd.DataFrame:
    """Full-history + N paired random windows, plain daily DCA vs dip-double variants.
    Persists results/dip_double.csv (scope = 'full' | 'window') for the dashboard."""
    variants = [("daily", None)] + [(f"dip{int(th * 100)}", th) for th in thresholds]
    rows = []
    for t in prices.columns:
        s = prices[t].dropna()
        for label, th in variants:
            r, nd, ns = _simulate_dip(s, th)
            rows.append({"scope": "full", "ticker": t, "variant": label,
                         "start": s.index[0].date(), "end": s.index[-1].date(),
                         "xirr": r.xirr, "multiple": r.multiple, "invested": r.invested,
                         "n_doubles": nd, "n_skips": ns})
        for st in sample_start_dates(s.index, years, n, seed):
            window = s.loc[st:st + pd.DateOffset(years=years)]
            if len(window) < 50:
                continue
            for label, th in variants:
                r, nd, ns = _simulate_dip(window, th)
                rows.append({"scope": "window", "ticker": t, "variant": label,
                             "start": st.date(), "end": window.index[-1].date(),
                             "xirr": r.xirr, "multiple": r.multiple,
                             "invested": r.invested, "n_doubles": nd, "n_skips": ns})
    df = pd.DataFrame(rows)
    df.to_csv(f"{outdir}/dip_double.csv", index=False, float_format="%.6g")
    print(f"[data] wrote {outdir}/dip_double.csv "
          f"({len(df)} rows: full history + {n} paired {years}-yr windows x "
          f"{len(variants)} variants)")
    return df


def print_dip_double(df: pd.DataFrame):
    print("\n=== Sprint 8b — daily DCA vs dip double-down (2x on a -X% day, skip next calm day) ===")
    full = df[df["scope"] == "full"]
    win = df[df["scope"] == "window"]
    for t in full["ticker"].unique():
        f = full[full["ticker"] == t].set_index("variant")
        yrs = (pd.Timestamp(f["end"].iloc[0]) - pd.Timestamp(f["start"].iloc[0])).days / 365.25
        print(f"\n  {t} full history ({f['start'].iloc[0]} → {f['end'].iloc[0]}): "
              f"plain daily XIRR {pct(f.at['daily', 'xirr'], 2)}")
        w = (win[win["ticker"] == t].drop_duplicates(["start", "variant"])
             .pivot(index="start", columns="variant", values="xirr"))
        for v in f.index.drop("daily"):
            d = (w[v] - w["daily"]) * 1e4          # paired delta in bp of XIRR
            print(f"    {v}: {f.at[v, 'n_doubles'] / yrs:5.1f} triggers/yr   "
                  f"full-history XIRR {pct(f.at[v, 'xirr'], 2)} "
                  f"({(f.at[v, 'xirr'] - f.at['daily', 'xirr']) * 1e4:+.1f}bp)   "
                  f"window delta median {d.median():+.1f}bp "
                  f"[p10 {d.quantile(.1):+.1f}, p90 {d.quantile(.9):+.1f}]   "
                  f"beats plain in {pct((d > 0).mean(), 0)} of windows")
    print("  (Deltas are PAIRED — same window, same dollars-per-year, only the timing tilt "
          "differs.)")


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
# Sprint 3 — after-tax layer + cadence sensitivity for the wife (SPY / NZ PIE) decision
#   1. After-tax overlay: PIE (28% PIR cap, no FIF/FX) vs a direct FIF hold under FDR.
#   2. Cadence: weekly vs monthly DCA — does buy frequency change the fee/return?
#   3. The wife's real downside: cash -> equities is a change in RISK LEVEL, not a yield swap.
# --------------------------------------------------------------------------------------
def apply_asset_drag(prices, annual_rate: float):
    """Deflate a total-return series (or frame) by a continuous asset-based charge of
    `annual_rate`/yr.

    NZ FDR tax is EXACTLY this: taxable income = 5% of opening balance, taxed at your rate,
    so the annual charge is rate x 5% of value — an asset-based fee, independent of the
    realized return. Deflating by exp(-rate * t) applies the drag over each contribution's
    actual holding period: the absolute deflation level cancels in every buy's growth ratio,
    so it is not applied retroactively. Feed the result straight into simulate_dca to read
    the net-of-tax XIRR."""
    years = np.asarray((prices.index - prices.index[0]).days / 365.25)
    return prices.mul(np.exp(-annual_rate * years), axis=0)


def print_after_tax(prices: pd.DataFrame):
    print("\n=== Sprint 3 · Task 1 — after-tax: wife's PIE (28% cap) vs a direct FIF hold (SPY) ===")
    print("  FDR: taxable income = 5% of opening balance/yr, taxed at your rate => a FIXED asset")
    print("  drag of rate x 5%/yr, independent of the actual return. Applied to the 10-yr windows:")
    variants = [("gross (pre-tax)",       0.0,             0.0),
                ("PIE  @28% (no FIF/FX)", PIE_PIR * FDR_RATE, 0.0)]
    variants += [(f"FIF  @{int(m*100)}% +0.5% FX", m * FDR_RATE, FX_FEE) for m in MARGINAL_RATES]
    for label, drag, fx in variants:
        adj = apply_asset_drag(prices, drag)
        df = simulate_random_windows(adj, "SPY", WIFE_YEARS, "MS", RANDOM_N, WIFE_MONTHLY,
                                     fx_fee=fx, lump=WIFE_LUMP, seed=SEED)
        q = df["xirr"].quantile([0.1, 0.5, 0.9])
        tag = "" if drag == 0 else f"   (tax drag {pct(drag, 2)}/yr)"
        print(f"  {label:22s} net XIRR  p10 {pct(q[0.1])}  p50 {pct(q[0.5])}  p90 {pct(q[0.9])}{tag}")
    print(f"  PIE saves the rate gap x 5%: {pct((0.33 - PIE_PIR) * FDR_RATE, 2)}/yr (vs 33%) to "
          f"{pct((0.39 - PIE_PIR) * FDR_RATE, 2)}/yr (vs 39%), PLUS the 0.5% FX and FIF $50k stacking.")
    print("  (FDR taxes a deemed 5%, not your gain — light in a strong market, still due in a flat")
    print("   year. A direct holder may elect the CV method to pay ~0 in a loss year; a PIE cannot.)")


def print_cadence(prices: pd.DataFrame):
    print("\n=== Sprint 3 · Task 2 — cadence: weekly vs monthly DCA (same $/yr) ===")
    print("  The Hatch FX fee is 0.5% PER DOLLAR converted, not per trade, so cadence does NOT")
    print("  change total FX cost. Only difference is timing (weekly deploys ~2wk sooner on avg).")
    annual = WEEKLY_CONTRIB * 52
    for t in prices.columns:
        s = prices[t].dropna()
        w = simulate_dca(s, WEEKLY_CONTRIB, "W", fx_fee=FX_FEE)
        m = simulate_dca(s, annual / 12, "MS", fx_fee=FX_FEE)
        print(f"  {t}: weekly XIRR {pct(w.xirr)} ({w.multiple:.2f}x)  |  "
              f"monthly XIRR {pct(m.xirr)} ({m.multiple:.2f}x)  |  "
              f"weekly edge {pct(w.xirr - m.xirr, 3)}/yr")
    print("  (Near-identical: pick the cadence that fits your cashflow — fees don't decide it.)")


def print_wife_downside(prices: pd.DataFrame):
    print("\n=== Sprint 3 · Task 3 — the wife's real downside (cash -> equities, not a yield swap) ===")
    spy = prices["SPY"].dropna()
    roll = spy / spy.shift(TRADING_DAYS) - 1        # rolling 12-mo total return
    worst, worst_end = roll.min(), roll.idxmin()
    dd = max_drawdown(spy)
    wdf = simulate_random_windows(prices, "SPY", WIFE_YEARS, "MS", RANDOM_N, WIFE_MONTHLY,
                                  fx_fee=0.0, lump=WIFE_LUMP, seed=SEED)
    mdd = wdf["max_dd"].quantile([0.5, 0.1])
    print(f"  Lump-sum sequence risk: worst 12-mo SPY total return {pct(worst)} (to {worst_end.date()}).")
    print(f"    A ${WIFE_LUMP:,.0f} lump entering just before that = ${WIFE_LUMP*(1+worst):,.0f} "
          f"a year on.")
    print(f"  Worst peak->trough (buy & hold): {pct(dd['max_dd'])} ({dd['peak']} -> {dd['trough']}), "
          f"{dd['recovery_years']:.1f}yr to recover.")
    print(f"  Over the 10-yr accumulation windows the BALANCE fell {pct(mdd[0.5])} (median window) "
          f"to {pct(mdd[0.1])} (worst decile) at its trough.")
    print("  A Term PIE cannot lose your capital; SPY can halve. The equity premium is the pay for")
    print("  that risk — real, but not free. This is a change in RISK LEVEL, state it plainly.")


def make_sprint3_plot(prices: pd.DataFrame):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as e:
        print(f"[plots] sprint3 plot skipped: {e}", file=sys.stderr)
        return
    fig, ax = plt.subplots(2, 1, figsize=(10, 9))
    for label, drag in [("gross (pre-tax)", 0.0), ("PIE @28%", PIE_PIR * FDR_RATE),
                        ("FIF @39%", 0.39 * FDR_RATE)]:
        adj = apply_asset_drag(prices, drag)
        x = simulate_random_windows(adj, "SPY", WIFE_YEARS, "MS", RANDOM_N, WIFE_MONTHLY,
                                    fx_fee=0.0, lump=WIFE_LUMP, seed=SEED)["xirr"].dropna() * 100
        ax[0].hist(x, bins=40, alpha=0.5, label=f"{label} (med {x.median():.1f}%)")
        ax[0].axvline(x.median(), linestyle="--", linewidth=1)
    ax[0].set_title("Wife SPY: net XIRR distribution shifts left with tax (10-yr windows)")
    ax[0].set_xlabel("annualized net XIRR (%)"); ax[0].set_ylabel("windows"); ax[0].legend()

    spy = prices["SPY"].dropna()
    roll = (spy / spy.shift(TRADING_DAYS) - 1) * 100
    roll.plot(ax=ax[1], color="#333", linewidth=0.8)
    ax[1].fill_between(roll.index, roll.values, 0, where=(roll.values < 0), alpha=0.3, color="red")
    ax[1].axhline(0, color="k", linewidth=0.6)
    ax[1].set_title(f"SPY rolling 12-mo total return — the cash->equities downside (worst {roll.min():.0f}%)")
    ax[1].set_ylabel("12-mo return (%)")
    fig.tight_layout()
    fig.savefig("results/sprint3_tax_cadence.png", dpi=120)
    print("[plots] saved results/sprint3_tax_cadence.png")


# --------------------------------------------------------------------------------------
# Sprint 7 — real-portfolio validation: what would the SAME NZD deposits, drip-fed weekly
# into SPY or QQQ, be worth today?
#
# Deposits ran REAL_DEPOSIT_START → REAL_DEPOSIT_END (NZ$90k total, modelled as an even
# weekly split); after the last deposit the sim just holds to the end of the data — the
# accumulate-then-hold shape simulate_dca cannot express. Each week's NZD converts to USD
# at that day's spot (NZDUSD=X, ffilled) with the user's real FX cost (~0 on IBKR), then
# buys at the week's first trading-day adjusted close — the engine's standard weekly
# convention. The REAL row reuses the same assumed cashflows with the actual terminal
# value, so its XIRR is APPROXIMATE (the real deposits were lumpy, not even).
# --------------------------------------------------------------------------------------
@dataclass
class NzdHoldResult:
    n_buys: int
    invested_nzd: float
    invested_usd: float
    final_usd: float
    final_nzd: float
    multiple_usd: float      # final_usd / invested_usd
    multiple_nzd: float      # final_nzd / invested_nzd
    xirr_usd: float
    curve: pd.DataFrame      # weekly: invested_nzd_cum, invested_usd_cum, value_usd
    cf_usd: list             # the USD contribution cashflows (no terminal) + dates,
    cf_dates: list           # reusable for the REAL row's approximate XIRR


def _weekly_first_days(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """First trading day of each week. Unlike _contribution_dates (whose index is the
    resample bin boundary, a Sunday), these are actual dates present in `index`, so they
    can price a buy via .loc."""
    return pd.DatetimeIndex(index.to_series().resample("W").first().dropna().values)


def even_nzd_schedule(index: pd.DatetimeIndex, contrib_start: str, contrib_end: str,
                      total_nzd: float) -> list:
    """Even weekly NZD split over the deposit window, dated on the engine's weekly grid
    (first trading day of each week). Swap for a real (date, nzd) deposit schedule from
    broker statements when available — everything downstream is schedule-shaped."""
    days = _weekly_first_days(index[(index >= contrib_start) & (index <= contrib_end)])
    return [(dt, total_nzd / len(days)) for dt in days]


def simulate_nzd_dca_hold(prices: pd.Series, fx: pd.Series, schedule: list,
                          fx_fee: float = 0.0) -> NzdHoldResult:
    """Contribute NZD per `schedule` (converted to USD at each date's spot, fx = USD per
    1 NZD), then hold with no further buys to the end of `prices`."""
    units = inv_nzd = inv_usd = 0.0
    cf_usd, cf_dates, buy_rows = [], [], []
    for dt, nzd in schedule:
        rate = fx.reindex([dt], method="ffill").iloc[0]
        usd = nzd * rate * (1 - fx_fee)
        units += usd / prices.loc[dt]
        inv_nzd += nzd
        inv_usd += usd
        cf_usd.append(-usd); cf_dates.append(dt)
        buy_rows.append((dt, inv_nzd, inv_usd, units))
    state = pd.DataFrame(buy_rows, columns=["date", "invested_nzd_cum", "invested_usd_cum",
                                            "units"]).set_index("date")

    # Weekly value curve from first buy to the end of the data (flat units after the last
    # buy), plus the exact final trading day so the curve ends on the valuation date.
    held_idx = _weekly_first_days(prices.index[prices.index >= schedule[0][0]])
    grid = prices.loc[held_idx]
    if grid.index[-1] != prices.index[-1]:
        grid = pd.concat([grid, prices.iloc[[-1]]])
    held = state.reindex(grid.index, method="ffill")
    curve = pd.DataFrame({
        "invested_nzd_cum": held["invested_nzd_cum"],
        "invested_usd_cum": held["invested_usd_cum"],
        "value_usd": held["units"] * grid,
    })

    final_usd = units * prices.iloc[-1]
    frate = fx.reindex([prices.index[-1]], method="ffill").iloc[0]
    final_nzd = final_usd / frate
    return NzdHoldResult(
        n_buys=len(schedule), invested_nzd=inv_nzd, invested_usd=inv_usd,
        final_usd=final_usd, final_nzd=final_nzd,
        multiple_usd=final_usd / inv_usd, multiple_nzd=final_nzd / inv_nzd,
        xirr_usd=xirr(cf_usd + [final_usd], cf_dates + [prices.index[-1]]),
        curve=curve, cf_usd=cf_usd, cf_dates=cf_dates,
    )


def _real_strategy_schedule(s: pd.Series, strategy: str, weekly_schedule: list) -> list:
    """NZD (date, amount) schedule for one ticker deploying REAL_DEPOSIT_TOTAL_NZD over the
    deposit window under `strategy`: 'weekly' = the shared even-weekly grid (Sprint 7);
    'daily' = even split over every trading day; 'dip' = the Sprint 8b 2x/skip rule at
    REAL_DIP_THRESHOLD (ticker-specific — SPY and QQQ dip on different days)."""
    if strategy == "weekly":
        return weekly_schedule
    w = s.loc[REAL_DEPOSIT_START:REAL_DEPOSIT_END]
    base = REAL_DEPOSIT_TOTAL_NZD / len(w)              # even daily NZD before any dip tilt
    amt = (pd.Series(base, index=w.index) if strategy == "daily"
           else dip_buy_schedule(w, base, REAL_DIP_THRESHOLD))
    return [(dt, a) for dt, a in amt.items() if a > 0]


def run_real_vs_dca(prices: pd.DataFrame, fx: pd.Series) -> dict:
    """Each ticker simulated under every REAL_STRATEGIES cadence (keys = (ticker, strategy)),
    all spending the same NZD over the same window — only the timing of deployment differs.
    Plus the REAL row: actual terminal value on the weekly schedule's assumed cashflows."""
    weekly_schedule = even_nzd_schedule(prices.index, REAL_DEPOSIT_START, REAL_DEPOSIT_END,
                                        REAL_DEPOSIT_TOTAL_NZD)
    res = {}
    for t in prices.columns:
        s = prices[t].dropna()
        for strat in REAL_STRATEGIES:
            sched = _real_strategy_schedule(s, strat, weekly_schedule)
            res[(t, strat)] = simulate_nzd_dca_hold(s, fx, sched, REAL_FX_FEE)

    any_r = res[(prices.columns[0], "weekly")]
    frate = fx.reindex([prices.index[-1]], method="ffill").iloc[0]
    real_final_nzd = REAL_PORTFOLIO_USD / frate
    res["REAL"] = NzdHoldResult(
        n_buys=any_r.n_buys, invested_nzd=any_r.invested_nzd,
        invested_usd=any_r.invested_usd,
        final_usd=REAL_PORTFOLIO_USD, final_nzd=real_final_nzd,
        multiple_usd=REAL_PORTFOLIO_USD / any_r.invested_usd,
        multiple_nzd=real_final_nzd / any_r.invested_nzd,
        xirr_usd=xirr(any_r.cf_usd + [REAL_PORTFOLIO_USD],
                      any_r.cf_dates + [prices.index[-1]]),
        curve=pd.DataFrame(), cf_usd=any_r.cf_usd, cf_dates=any_r.cf_dates,
    )
    if str(prices.index[-1].date()) != REAL_PORTFOLIO_ASOF:
        print(f"[warn] sim valued at {prices.index[-1].date()} but the real portfolio "
              f"value is as of {REAL_PORTFOLIO_ASOF} — dates should match", file=sys.stderr)
    return res


def persist_real_vs_dca(res: dict, outdir: str = "results"):
    tickers = list(dict.fromkeys(k[0] for k in res if isinstance(k, tuple)))
    ref = res[(tickers[0], "weekly")].curve            # shared weekly display grid
    ts = pd.DataFrame({"invested_nzd_cum": ref["invested_nzd_cum"],
                       "invested_usd_cum": ref["invested_usd_cum"]})
    for t in tickers:
        for strat in REAL_STRATEGIES:
            ts[f"value_{t}_{strat}_usd"] = (
                res[(t, strat)].curve["value_usd"].reindex(ref.index, method="ffill"))
    ts.insert(0, "date", [d.date() for d in ts.index])
    ts.to_csv(f"{outdir}/real_vs_dca_timeseries.csv", index=False)

    rows = [{"key": "REAL", "ticker": "REAL", "strategy": "actual"}]
    rows[0].update({k: getattr(res["REAL"], k) for k in
                    ("n_buys", "invested_nzd", "invested_usd", "final_usd",
                     "multiple_usd", "xirr_usd", "final_nzd", "multiple_nzd")})
    for t in tickers:
        for strat in REAL_STRATEGIES:
            r = res[(t, strat)]
            rows.append({"key": f"{t}_{strat}", "ticker": t, "strategy": strat,
                         "n_buys": r.n_buys, "invested_nzd": r.invested_nzd,
                         "invested_usd": r.invested_usd, "final_usd": r.final_usd,
                         "multiple_usd": r.multiple_usd, "xirr_usd": r.xirr_usd,
                         "final_nzd": r.final_nzd, "multiple_nzd": r.multiple_nzd})
    pd.DataFrame(rows).to_csv(f"{outdir}/real_vs_dca_summary.csv", index=False)
    print(f"[data] wrote {outdir}/real_vs_dca_timeseries.csv + real_vs_dca_summary.csv")


def print_real_vs_dca(res: dict):
    tickers = list(dict.fromkeys(k[0] for k in res if isinstance(k, tuple)))
    r0 = res[(tickers[0], "weekly")]
    print(f"\n=== Sprint 7/10 — real portfolio vs DCA (weekly/daily/dip) into SPY/QQQ ===")
    print(f"  NZ${r0.invested_nzd:,.0f} over the {REAL_DEPOSIT_START} → {REAL_DEPOSIT_END} "
          f"window, converted at spot ({pct(REAL_FX_FEE, 1)} FX fee), then held.")
    real = res["REAL"]
    print(f"    {'REAL':10s} ${real.final_usd:>10,.0f} USD  ({real.multiple_usd:.2f}x USD, "
          f"{real.multiple_nzd:.2f}x NZD)  XIRR {pct(real.xirr_usd)}  "
          f"(approx: assumes the even weekly schedule)")
    for t in tickers:
        for strat in REAL_STRATEGIES:
            r = res[(t, strat)]
            print(f"    {t + '/' + strat:10s} ${r.final_usd:>10,.0f} USD  "
                  f"({r.multiple_usd:.2f}x USD, {r.multiple_nzd:.2f}x NZD)  "
                  f"XIRR {pct(r.xirr_usd)}")
    print("  (Hindsight caveat: SPY/QQQ are benchmarks chosen after a decade they")
    print("   dominated; the real portfolio's risk profile may differ. Pre-tax, USD.)")


# --------------------------------------------------------------------------------------
# Sprint 9 — would "buy the dip" have helped on the REAL scenario?
#
# Same NZD total and same deposit window as Sprint 7, but deployed DAILY into each ticker
# under the Sprint 8b dip rule (2x on a <=-X% close, skip the next calm day) vs an
# even-daily baseline. Reuses dip_buy_schedule for the amount pattern and the Sprint 7
# simulate_nzd_dca_hold for FX conversion + accumulate-then-hold, so the only thing that
# varies across rows is WHEN within the window the fixed NZD gets deployed. The dip schedule
# is ticker-specific (SPY and QQQ dip on different days). Deployed daily so the dip has
# daily moves to react to; the even-daily baseline nets ~equal to Sprint 7's weekly DCA
# (cadence is a wash, Sprint 3), and is the honest like-for-like anchor for the dip delta.
# --------------------------------------------------------------------------------------
def real_dip_variants(prices: pd.DataFrame, fx: pd.Series, thresholds=DIP_THRESHOLDS,
                      outdir: str = "results") -> pd.DataFrame:
    variants = [("even_daily", None)] + [(f"dip{int(th * 100)}", th) for th in thresholds]
    rows = []
    for t in prices.columns:
        s = prices[t].dropna()
        w = s.loc[REAL_DEPOSIT_START:REAL_DEPOSIT_END]
        base = REAL_DEPOSIT_TOTAL_NZD / len(w)          # even daily NZD before the dip tilt
        for label, th in variants:
            amt = (pd.Series(base, index=w.index) if th is None
                   else dip_buy_schedule(w, base, th))
            schedule = [(dt, a) for dt, a in amt.items() if a > 0]
            r = simulate_nzd_dca_hold(s, fx, schedule, REAL_FX_FEE)
            rows.append({"ticker": t, "strategy": label,
                         "n_buys": len(schedule),
                         "n_doubles": int((amt == 2 * base).sum()),
                         "n_skips": int((amt == 0.0).sum()),
                         "invested_nzd": r.invested_nzd, "invested_usd": r.invested_usd,
                         "final_usd": r.final_usd, "multiple_usd": r.multiple_usd,
                         "xirr_usd": r.xirr_usd, "final_nzd": r.final_nzd,
                         "multiple_nzd": r.multiple_nzd})
    df = pd.DataFrame(rows)
    df.to_csv(f"{outdir}/real_dip.csv", index=False)
    print(f"[data] wrote {outdir}/real_dip.csv "
          f"({len(df)} rows: {len(prices.columns)} tickers x {len(variants)} strategies)")
    return df


def print_real_dip(df: pd.DataFrame):
    print("\n=== Sprint 9 — real scenario: even-daily DCA vs buy-the-dip (same NZD, same window) ===")
    for t in df["ticker"].unique():
        sub = df[df["ticker"] == t].set_index("strategy")
        base_x = sub.at["even_daily", "xirr_usd"]
        base_f = sub.at["even_daily", "final_usd"]
        print(f"\n  {t}: NZ${sub.at['even_daily', 'invested_nzd']:,.0f} deployed daily, "
              f"held to end")
        for strat in sub.index:
            r = sub.loc[strat]
            tag = ("" if strat == "even_daily"
                   else f"   Δ vs even ${r['final_usd'] - base_f:+,.0f}  "
                        f"({(r['xirr_usd'] - base_x) * 1e4:+.1f}bp XIRR)")
            dd = "" if strat == "even_daily" else f"{int(r['n_doubles']):>4d} doubles  "
            print(f"    {strat:11s} {dd}${r['final_usd']:>10,.0f}  "
                  f"({r['multiple_usd']:.2f}x)  XIRR {pct(r['xirr_usd'])}{tag}")
    print("  (Same money, same window — only the intra-window timing differs. Compare the")
    print("   dip delta to the Sprint 8b distribution: a few bp, swamped by everything else.)")


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
    persist_projection_factors(prices, n=args.n, seed=args.seed)

    print_twins(TWINS)
    print_nzd_overlay()
    print_fx_fee_drag()

    print_after_tax(prices)
    print_cadence(prices)
    print_wife_downside(prices)

    fx_series = load_series(FX_TICKER)
    real = run_real_vs_dca(prices, fx_series)
    print_real_vs_dca(real)
    persist_real_vs_dca(real)
    print_real_dip(real_dip_variants(prices, fx_series))

    print_weekday_anchor(weekday_anchor_study(prices, n=args.n, seed=args.seed))
    print_dip_double(dip_double_study(prices, n=args.n, seed=args.seed))

    if SAVE_PLOTS:
        make_plots(prices)
        make_random_plots(baby, wife)
        make_sprint2_plot()
        make_sprint3_plot(prices)
    print("\nDone. Edit the CONFIG block at the top to change amounts, tickers, or dates.")


if __name__ == "__main__":
    main()
