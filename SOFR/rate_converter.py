"""
rate_converter.py — restate a curve point under different day-count / accrual
conventions, all anchored to the SAME discount factor (the invariant).

The curve produces discount factors. A "rate" is just a way of quoting a DF
under a chosen (day-count, compounding). Converting conventions therefore holds
the DF fixed and re-expresses the rate — so every difference between cells below
is *pure convention basis*, not a change in economics.

Two views:
  Level 1  single-payment equivalent rate: interest either SIMPLE (paid, no
           compounding) or COMPOUNDED at a frequency. day-count x compounding.
  Level 2  par fixed coupon for an actual term deal with interest PAID each
           period, on a business-day-adjusted schedule. tenor x pay-freq x
           day-count (incl. Act/Act ICMA, which only makes sense on a schedule).

Run:  python3 rate_converter.py
"""
import pandas as pd
import QuantLib as ql

from sofr_pipeline import fetch_snapshot, build_curve, CALENDAR

# Day counts well-defined for a single period (Level 1).
DAYCOUNTS = {
    "Act/360": ql.Actual360(),
    "Act/365F": ql.Actual365Fixed(),
    "Act/Act ISDA": ql.ActualActual(ql.ActualActual.ISDA),
    "Act/Act AFB": ql.ActualActual(ql.ActualActual.AFB),
    "30/360 Bond": ql.Thirty360(ql.Thirty360.BondBasis),
    "30E/360": ql.Thirty360(ql.Thirty360.European),
}

# (label, compounding, frequency). Simple == "interest paid, no compounding".
COMPOUNDINGS = [
    ("Simple (paid)", ql.Simple, ql.Annual),
    ("Comp Monthly", ql.Compounded, ql.Monthly),
    ("Comp Quarterly", ql.Compounded, ql.Quarterly),
    ("Comp Semiann", ql.Compounded, ql.Semiannual),
    ("Comp Annual", ql.Compounded, ql.Annual),
    ("Continuous", ql.Continuous, ql.Annual),
]

TENORS = [(1, "1M"), (3, "3M"), (6, "6M"), (12, "12M"), (24, "24M")]
BDC = ql.ModifiedFollowing


def _maturity(ref, months):
    return CALENDAR.advance(ref, ql.Period(months, ql.Months), BDC)


def level1(curve) -> pd.DataFrame:
    """Single-payment equivalent rate, all from the same DF."""
    ref = curve.referenceDate()
    rows = []
    for m, label in TENORS:
        d = _maturity(ref, m)
        df = curve.discount(d)
        compound = 1.0 / df                       # the invariant: 1/DF
        for dcname, dc in DAYCOUNTS.items():
            rec = {"tenor": label, "daycount": dcname, "DF": df}
            for cname, comp, freq in COMPOUNDINGS:
                r = ql.InterestRate.impliedRate(compound, dc, comp, freq, ref, d).rate()
                rec[cname] = r * 100
            rows.append(rec)
    return pd.DataFrame(rows)


def level2(curve) -> pd.DataFrame:
    """Par fixed coupon for a real term deal: interest PAID each period on a
    business-day-adjusted schedule, priced to par off the curve."""
    ref = curve.referenceDate()
    settle = CALENDAR.advance(ref, 2, ql.Days)     # T+2
    dcs = dict(DAYCOUNTS)
    dcs["Act/Act ICMA"] = ql.ActualActual(ql.ActualActual.Bond)   # ICMA = "Bond"
    pay_freqs = [(1, "Monthly", ql.Monthly), (3, "Quarterly", ql.Quarterly),
                 (6, "Semiann", ql.Semiannual), (12, "Annual", ql.Annual)]
    rows = []
    for m, label in TENORS:
        end = CALENDAR.advance(settle, ql.Period(m, ql.Months), BDC)
        df0, dfn = curve.discount(settle), curve.discount(end)
        for pm, pfname, pfreq in pay_freqs:
            if pm > m:                              # can't pay quarterly on a 1M deal
                continue
            sched = list(ql.Schedule(settle, end, ql.Period(pfreq), CALENDAR,
                                     BDC, BDC, ql.DateGeneration.Forward, False))
            for dcname, dc in dcs.items():
                annuity = 0.0
                for d1, d2 in zip(sched, sched[1:]):
                    tau = (dc.yearFraction(d1, d2, d1, d2)
                           if dcname == "Act/Act ICMA" else dc.yearFraction(d1, d2))
                    annuity += tau * curve.discount(d2)
                par = (df0 - dfn) / annuity         # par coupon
                rows.append({"tenor": label, "pay_freq": pfname,
                             "daycount": dcname, "par_coupon_%": par * 100})
    return pd.DataFrame(rows)


def main() -> None:
    snap = fetch_snapshot()
    curve, *_ = build_curve(snap)
    ref = curve.referenceDate()
    print(f"Curve as of {snap.quote_date.ISO()}\n")

    l1 = level1(curve)
    l2 = level2(curve)
    l1.to_csv("rate_conversions_level1.csv", index=False)
    l2.to_csv("rate_conversions_level2.csv", index=False)

    # --- Focused 6M view ---
    d6 = _maturity(ref, 6)
    print(f"6M point:  DF = {curve.discount(d6):.6f}   "
          f"(matures {d6.ISO()})\n")

    cols = [c for c, *_ in COMPOUNDINGS]
    a = l1[l1.tenor == "6M"].set_index("daycount")[cols]
    print("LEVEL 1 — single-payment equivalent rate (%), 6M, same DF:")
    print(a.to_string(float_format=lambda x: f"{x:.4f}"))
    span = a.values.max() - a.values.min()
    print(f"\n  spread across all 6M conventions: {span*100:.2f} bp\n")

    b = (l2[l2.tenor == "6M"]
         .pivot(index="daycount", columns="pay_freq", values="par_coupon_%")
         .reindex(columns=["Monthly", "Quarterly", "Semiann"]))
    print("LEVEL 2 — par coupon (%), 6M deal, interest PAID each period:")
    print(b.to_string(float_format=lambda x: f"{x:.4f}"))

    print("\nFull matrices (all tenors): "
          "rate_conversions_level1.csv, rate_conversions_level2.csv")


if __name__ == "__main__":
    main()
