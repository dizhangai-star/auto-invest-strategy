# Baseline reference run — Sprint 0

Reproducible reference output of `backtest.py`. Total-return (adjusted) prices, USD, pre-tax.

- **Window:** 1999-03-10 → 2026-07-08 (6874 trading days, QQQ common history, no NaNs)
- **Data:** yfinance live; offline fallback `data/SPY.csv`, `data/QQQ.csv` reproduces these numbers exactly (verified with network forced off).
- **Config:** `START=1999-03-10`, `FX_FEE=0.5%`, weekly $100 (baby), lump $20,000 + monthly $500 (wife).

## Per-ticker metrics (full common history)

| Ticker | CAGR | Vol | Sharpe(rf=0) | MaxDD | DD peak | DD trough | Recover (yrs) | Best yr | Worst yr | %pos yrs |
|--------|------|-----|--------------|-------|---------|-----------|---------------|---------|----------|----------|
| SPY | 8.5% | 19.3% | 0.44 | −55.2% | 2007-10-09 | 2009-03-09 | 3.4 | 32.3% | −36.8% | 77.8% |
| QQQ | 10.8% | 26.9% | 0.40 | **−83.0%** | 2000-03-27 | 2002-10-09 | **12.4** | 54.9% | −41.7% | 77.8% |

**Sanity check (engine is not hiding risk):** QQQ's dot-com fall of −83.0% and its 12.4-year
recovery are present. Note QQQ's higher CAGR comes with a *lower* Sharpe than SPY — the extra
return did not compensate for the extra volatility over this full window.

## Period bias — CAGR by start date

| From | SPY | QQQ |
|------|-----|-----|
| 1999-03 | 8.5% | 10.8% |
| 2000-03 | 8.5% | 8.1% |
| 2010-01 | 14.1% | 19.0% |
| 2015-01 | 13.7% | 19.2% |
| 2020-01 | 15.2% | 20.8% |

QQQ's edge is entirely window-dependent: start at the 2000 peak and it *trails* SPY (8.1% vs
8.5%); start post-GFC and it dominates. This is exactly why Sprint 1 replaces single start dates
with a randomized-window distribution.

## DCA scenarios

**Baby — weekly $100 DCA, 0.5% FX fee per contribution**

| Ticker | Invested | Final | Multiple | XIRR |
|--------|----------|-------|----------|------|
| SPY | $142,700 | $862,450 | 6.04x | 11.3% |
| QQQ | $142,700 | $1,716,055 | 12.03x | 15.2% |

**Wife — lump $20,000 + monthly $500 DCA, PIE (FX fee = 0)**

| Ticker | Invested | Final | Multiple | XIRR |
|--------|----------|-------|----------|------|
| SPY | $184,500 | $1,184,119 | 6.42x | 10.5% |
| QQQ | $184,500 | $2,318,223 | 12.56x | 14.0% |

XIRR (money-weighted) sits well below the naive multiple because most capital was contributed in
later years — the honest DCA number. SPY is a stand-in for the NZ S&P 500 PIE underlying index.

## Caveats (unchanged from CLAUDE.md)

- USD, pre-tax. No NZD/USD overlay (Sprint 2), no PIE/FIF tax layer (Sprint 3).
- Single full-history line only — distribution of outcomes is Sprint 1.
- ETF TER is inside NAV (not double-counted); only extra modelled cost is platform FX.
