"""
credit_curves.py — rating-specific corporate discount curves (sloped spread).

    corporate curve(rating) = SOFR curve + spread(rating, tenor)
    spread(rating, T)       = OAS_level(rating) x IG_shape(T)  +  basis(T)

Where:
  * OAS_level(rating)  ICE BofA US Corporate OAS by rating (AA/A/BBB), FRED.
  * IG_shape(T)        IG-corporate OAS maturity buckets / master OAS -> the
                       credit term-structure slope, applied to each rating
                       (refinement (a): sloped, not flat).
  * basis(T)           Treasury(CMT) - SOFR, both on a like-for-like bond-
                       equivalent basis -> nets out the Treasury-vs-SOFR basis
                       so the curve is effectively Treasury + OAS, the true
                       corporate yield (refinement (b)).

Caveat unchanged: these are PUBLIC investment-grade bond spreads — a reference
scaffold, NOT an unrated crypto-fund borrower's spread (which is wider and comes
from underwriting). FRED key in CORPORATE/.env; manual fallback if unreachable.

Run:  python3 credit_curves.py
"""
from __future__ import annotations

import os
import pathlib
import sys

import numpy as np
import pandas as pd
import requests
import QuantLib as ql
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

SOFR_DIR = pathlib.Path(__file__).resolve().parent.parent / "SOFR"
sys.path.insert(0, str(SOFR_DIR))
import sofr_pipeline as sofr            # noqa: E402
import rate_converter as rc            # noqa: E402

FRED_OBS = "https://api.stlouisfed.org/fred/series/observations"
RATING_SERIES = {"AA": "BAMLC0A2CAA", "A": "BAMLC0A3CA", "BBB": "BAMLC0A4CBBB"}
RATINGS = ["AA", "A", "BBB"]
MANUAL_OAS = {"AA": 0.0050, "A": 0.0063, "BBB": 0.0093}
IG_MASTER = "BAMLC0A0CM"
IG_BUCKETS = [(2.0, "BAMLC1A0C13Y"), (4.0, "BAMLC2A0C35Y"), (6.0, "BAMLC3A0C57Y"),
              (8.5, "BAMLC4A0C710Y"), (12.5, "BAMLC7A0C1015Y"), (20.0, "BAMLC8A0C15PY")]
CMT = [(1/12, "DGS1MO"), (0.25, "DGS3MO"), (0.5, "DGS6MO"), (1.0, "DGS1"),
       (2.0, "DGS2"), (3.0, "DGS3"), (5.0, "DGS5"), (7.0, "DGS7"),
       (10.0, "DGS10"), (20.0, "DGS20"), (30.0, "DGS30")]
NODE_TENORS = [1/12, 0.25, 0.5, 1, 2, 3, 5, 7, 10, 15, 20, 30]


# --------------------------------------------------------------------------- #
def _fred_key():
    if os.environ.get("FRED_API_KEY"):
        return os.environ["FRED_API_KEY"].strip()
    envf = pathlib.Path(__file__).resolve().parent / ".env"
    if envf.exists():
        for line in envf.read_text().splitlines():
            if line.startswith("FRED_API_KEY="):
                return line.split("=", 1)[1].strip()
    return None


def _latest(sess, key, sid):
    r = sess.get(FRED_OBS, params={"series_id": sid, "api_key": key,
                 "file_type": "json", "sort_order": "desc", "limit": 1}, timeout=20)
    return float(r.json()["observations"][0]["value"])


def fetch_fred() -> dict:
    """Pull rating OAS, IG maturity-bucket shape, and CMT yields (decimals)."""
    key = _fred_key()
    if not key:
        print("  [warn] no FRED key; using manual flat spreads", file=sys.stderr)
        return {"oas": dict(MANUAL_OAS), "shape": None, "cmt": None, "src": "manual"}
    s = requests.Session(); s.headers.update({"User-Agent": "Mozilla/5.0"})
    try:
        oas = {r: _latest(s, key, sid) / 100 for r, sid in RATING_SERIES.items()}
        master = _latest(s, key, IG_MASTER) / 100
        shape = {t: (_latest(s, key, sid) / 100) / master for t, sid in IG_BUCKETS}
        cmt = {t: _latest(s, key, sid) / 100 for t, sid in CMT}
        return {"oas": oas, "shape": shape, "cmt": cmt, "src": "FRED"}
    except Exception as e:                                  # noqa: BLE001
        print(f"  [warn] FRED failed ({e}); manual flat spreads", file=sys.stderr)
        return {"oas": dict(MANUAL_OAS), "shape": None, "cmt": None, "src": "manual"}


# --------------------------------------------------------------------------- #
def _tenor_date(ref, t):
    return sofr.CALENDAR.advance(ref, ql.Period(int(round(t * 12)), ql.Months),
                                 ql.ModifiedFollowing)


def _sofr_bey(curve, ref, d):
    """SOFR rate restated to bond-equivalent (Act/Act, semiannual) to compare
    like-for-like with CMT par yields."""
    compound = 1.0 / curve.discount(d)
    return ql.InterestRate.impliedRate(compound, ql.ActualActual(ql.ActualActual.ISDA),
                                       ql.Compounded, ql.Semiannual, ref, d).rate()


def build_basis(curve, ref, cmt):
    """Treasury(CMT) - SOFR(bond-equiv) at each CMT tenor -> interpolator(t)."""
    if cmt is None:
        return (lambda t: 0.0), {}
    ts = sorted(cmt)
    vals = [cmt[t] - _sofr_bey(curve, ref, _tenor_date(ref, t)) for t in ts]
    return (lambda t: float(np.interp(t, ts, vals))), dict(zip(ts, vals))


def build_shape(shape):
    """IG term-structure slope factor(t); flat where unsupported (<2Y, >20Y)."""
    if shape is None:
        return lambda t: 1.0
    ts = sorted(shape)
    fs = [shape[t] for t in ts]
    return lambda t: float(np.interp(t, ts, fs))


def corporate_curve(sofr_handle, ref, level, shape_fn, basis_fn):
    dates, quotes = [], []
    for t in NODE_TENORS:
        spread = level * shape_fn(t) + basis_fn(t)        # over SOFR
        dates.append(_tenor_date(ref, t))
        quotes.append(ql.QuoteHandle(ql.SimpleQuote(spread)))
    curve = ql.SpreadedLinearZeroInterpolatedTermStructure(
        sofr_handle, quotes, dates, ql.Continuous, ql.NoFrequency, ql.Actual365Fixed())
    curve.enableExtrapolation()
    return curve


def deal_rates(curve, pay="Monthly", dc="Act/360"):
    df = rc.level2(curve)
    return df[(df.pay_freq == pay) & (df.daycount == dc)].set_index("tenor")["par_coupon_%"]


# --------------------------------------------------------------------------- #
def plot(sofr_curve, corp, basis_pts, asof):
    ref = sofr_curve.referenceDate()
    dc = sofr.CURVE_DAYCOUNT
    ts = np.linspace(0.1, 30, 600)
    pct = FuncFormatter(lambda v, _: f"{v:.1f}%")
    bp = FuncFormatter(lambda v, _: f"{v:.0f}")
    colors = {"AA": "#2e7d32", "A": "#ef6c00", "BBB": "#c62828"}
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 5.5))

    sz = [sofr_curve.zeroRate(t, ql.Continuous).rate() * 100 for t in ts]
    ax1.plot(ts, sz, color="#1f4e79", lw=2.2, label="SOFR (risk-free)")
    for r in RATINGS:
        z = [corp[r].zeroRate(t, ql.Continuous).rate() * 100 for t in ts]
        ax1.plot(ts, z, color=colors[r], lw=1.8, label=f"{r}")
    ax1.yaxis.set_major_formatter(pct); ax1.set_xlabel("years")
    ax1.set_title(f"SOFR + corporate discount curves — zero rates ({asof})")
    ax1.legend(loc="lower right", fontsize=9); ax1.grid(alpha=0.25)

    for r in RATINGS:
        spr = [(corp[r].zeroRate(t, ql.Continuous).rate()
                - sofr_curve.zeroRate(t, ql.Continuous).rate()) * 1e4 for t in ts]
        ax2.plot(ts, spr, color=colors[r], lw=1.8, label=f"{r} spread / SOFR")
    if basis_pts:
        bt = sorted(basis_pts)
        ax2.plot(bt, [basis_pts[t] * 1e4 for t in bt], color="grey", lw=1.2,
                 ls="--", marker="o", ms=3, label="Treasury–SOFR basis")
    ax2.yaxis.set_major_formatter(bp); ax2.set_xlabel("years")
    ax2.set_ylabel("basis points"); ax2.set_title("Credit spread over SOFR (sloped + basis)")
    ax2.legend(loc="lower right", fontsize=9); ax2.grid(alpha=0.25)

    fig.tight_layout(); fig.savefig("credit_curves.png", dpi=140, bbox_inches="tight")
    print("Saved credit_curves.png")


def main() -> None:
    print("Building SOFR base curve ...")
    snap = sofr.fetch_snapshot()
    sofr_curve, sofr_handle, _ = sofr.build_curve(snap)
    ref = sofr_curve.referenceDate()

    d = fetch_fred()
    print(f"\nSpread inputs ({d['src']}):  OAS levels "
          + ", ".join(f"{r} {d['oas'][r]*1e4:.0f}bp" for r in RATINGS))

    shape_fn = build_shape(d["shape"])
    basis_fn, basis_pts = build_basis(sofr_curve, ref, d["cmt"])

    corp = {r: corporate_curve(sofr_handle, ref, d["oas"][r], shape_fn, basis_fn)
            for r in RATINGS}

    # Spread term structure (bp over SOFR) at the node tenors.
    spr_tbl = pd.DataFrame(
        {r: {f"{t:g}Y" if t >= 1 else f"{round(t*12)}M":
             (corp[r].zeroRate(_tenor_date(ref, t), sofr.CURVE_DAYCOUNT, ql.Continuous).rate()
              - sofr_curve.zeroRate(_tenor_date(ref, t), sofr.CURVE_DAYCOUNT, ql.Continuous).rate()) * 1e4
             for t in NODE_TENORS} for r in RATINGS})
    print("\nCredit spread over SOFR (bp) — sloped (maturity shape + basis):")
    print(spr_tbl.to_string(float_format=lambda x: f"{x:.1f}"))

    # All-in deal-matched loan rates (short term-deal range).
    PAY, DC = "Monthly", "Act/360"
    rates = pd.DataFrame({"SOFR": deal_rates(sofr_curve, PAY, DC),
                          **{r: deal_rates(corp[r], PAY, DC) for r in RATINGS}})
    rates = rates.reindex([t for _, t in rc.TENORS])
    print(f"\nAll-in loan rate (%) — par coupon, paid {PAY.lower()}, {DC}:")
    print(rates.to_string(float_format=lambda x: f"{x:.4f}"))

    rates.to_csv("corporate_loan_rates.csv")
    spr_tbl.to_csv("credit_spread_termstructure.csv")
    plot(sofr_curve, corp, basis_pts, snap.quote_date.ISO())
    print("\nSaved: corporate_loan_rates.csv, credit_spread_termstructure.csv, credit_curves.png")
    print("\nNote: public IG-bond spreads — reference scaffold, not the crypto-fund's spread.")


if __name__ == "__main__":
    main()
