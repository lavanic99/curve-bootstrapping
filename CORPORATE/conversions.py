"""
conversions.py — express the corporate (AA/A/BBB) all-in loan rate in deal
day-count / accrual conventions, reusing the SOFR convention converter.

This is the quotable-rate layer: the number that goes in a term sheet. Every
value is anchored to the rating curve's discount factor (SOFR + credit spread),
so it is the same economics restated in the deal's dialect.

Note: the convention basis is largely *rating-independent* — it is a function of
the rate level and the conventions, not of credit — so each rating's matrix is
essentially the SOFR conversion shifted up by the credit spread.

Outputs: corp_rate_conversions.csv, corp_rate_conversions.png
Run:     python3 conversions.py
"""
import pathlib
import sys

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

SOFR_DIR = pathlib.Path(__file__).resolve().parent.parent / "SOFR"
sys.path.insert(0, str(SOFR_DIR))
import sofr_pipeline as sofr            # noqa: E402
import rate_converter as rc            # noqa: E402
import credit_curves as cc             # noqa: E402 (local)

FOCUS_TENOR = "6M"
CURVE_COLORS = {"SOFR": "#1f4e79", **cc.RATING_COLORS}
ORDER = ["SOFR"] + cc.RATINGS            # column / plotting order, full ladder


def build_curves():
    snap = sofr.fetch_snapshot()
    sofr_curve, handle, _ = sofr.build_curve(snap)
    ref = sofr_curve.referenceDate()
    d = cc.fetch_fred()
    shape_fn = cc.build_shape(d["shape"])
    basis_fn, _ = cc.build_basis(sofr_curve, ref, d["cmt"])
    curves = {"SOFR": sofr_curve}
    for r in cc.RATINGS:
        curves[r] = cc.corporate_curve(handle, ref, d["oas"][r], shape_fn, basis_fn)
    return curves, snap.quote_date.ISO()


def main() -> None:
    curves, asof = build_curves()

    # Full quotable matrix: par coupon per curve x tenor x pay-freq x day-count.
    frames = []
    for name, c in curves.items():
        f = rc.level2(c).copy()
        f.insert(0, "curve", name)
        frames.append(f)
    full = pd.concat(frames, ignore_index=True)
    full.to_csv("corp_rate_conversions.csv", index=False)

    # Focused 6M, monthly-paid view (the headline quotable rates).
    view = (full[(full.tenor == FOCUS_TENOR) & (full.pay_freq == "Monthly")]
            .pivot(index="daycount", columns="curve", values="par_coupon_%")
            .reindex(columns=ORDER))
    print(f"All-in loan rate (%) — {FOCUS_TENOR}, par coupon, paid monthly:")
    print(view.to_string(float_format=lambda x: f"{x:.4f}"))

    pct = FuncFormatter(lambda v, _: f"{v:.2f}%")
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 5.5))

    # --- Panel A: quotable 6M loan rate by day count and rating ---
    dcs = list(view.index)
    xs = np.arange(len(dcs))
    for name in ORDER:
        ax1.scatter(xs, view[name].values, s=55, color=CURVE_COLORS[name],
                    label=name, zorder=3)
    ax1.set_xticks(xs); ax1.set_xticklabels(dcs, rotation=20, ha="right")
    ax1.yaxis.set_major_formatter(pct)
    ax1.set_title(f"Quotable {FOCUS_TENOR} loan rate — par coupon, paid monthly ({asof})")
    ax1.legend(fontsize=9, title="curve"); ax1.grid(alpha=0.25, axis="y")

    # --- Panel B: convention basis is ~rating-independent ---
    comps = [c for c, *_ in rc.COMPOUNDINGS]
    spreads = {}
    for name, c in curves.items():
        l1 = rc.level1(c)
        a = l1[l1.tenor == FOCUS_TENOR][comps].values
        spreads[name] = (a.max() - a.min()) * 100          # bp
    names = ORDER
    ax2.bar(names, [spreads[n] for n in names],
            color=[CURVE_COLORS[n] for n in names], width=0.6)
    for i, n in enumerate(names):
        ax2.text(i, spreads[n] + 0.05, f"{spreads[n]:.1f}", ha="center", fontsize=9)
    ax2.set_ylabel("total convention spread at 6M (bp)")
    ax2.set_title("Convention basis is ~rating-independent\n(a rate-level effect, not credit)")
    ax2.grid(alpha=0.25, axis="y")

    fig.tight_layout()
    fig.savefig("corp_rate_conversions.png", dpi=140, bbox_inches="tight")
    print("\nSaved: corp_rate_conversions.csv, corp_rate_conversions.png")


if __name__ == "__main__":
    main()
