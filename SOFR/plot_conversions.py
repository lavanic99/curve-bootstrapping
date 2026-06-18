"""Visualize the rate-convention basis: the same discount factor restated under
different day-count / compounding conventions.

Left  — the "fan of dialects" at a fixed tenor (every point is the SAME DF).
Right — how the basis vs the SOFR-native convention grows with tenor.
"""
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

import sofr_pipeline as sofr
import rate_converter as rc

# SOFR OIS native convention = Act/360, annually compounded.
NATIVE_DC, NATIVE_COMP = "Act/360", "Comp Annual"
FOCUS_TENOR = "6M"
COMP_COLORS = {c: col for (c, *_), col in zip(
    rc.COMPOUNDINGS, ["#1f4e79", "#2e7d32", "#00897b", "#ef6c00", "#c62828", "#6a1b9a"])}


def main() -> None:
    snap = sofr.fetch_snapshot()
    curve, *_ = sofr.build_curve(snap)
    l1 = rc.level1(curve)
    comps = [c for c, *_ in rc.COMPOUNDINGS]
    daycounts = list(rc.DAYCOUNTS)

    pct = FuncFormatter(lambda v, _: f"{v:.3f}%")
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 5.5))

    # --- Panel A: fan of dialects at FOCUS_TENOR (same DF) ---
    a = l1[l1.tenor == FOCUS_TENOR].set_index("daycount")
    df = a["DF"].iloc[0]
    xs = np.arange(len(daycounts))
    for j, comp in enumerate(comps):
        off = (j - (len(comps) - 1) / 2) * 0.11
        ax1.scatter(xs + off, [a.loc[dc, comp] for dc in daycounts],
                    color=COMP_COLORS[comp], s=45, label=comp, zorder=3)
    native = a.loc[NATIVE_DC, NATIVE_COMP]
    ax1.axhline(native, color="grey", ls="--", lw=1,
                label=f"SOFR-native ({NATIVE_DC}, {NATIVE_COMP})")
    allv = a[comps].values
    ax1.set_xticks(xs); ax1.set_xticklabels(daycounts, rotation=20, ha="right")
    ax1.yaxis.set_major_formatter(pct)
    ax1.set_title(f"Same DF ({df:.5f}), every dialect — {FOCUS_TENOR}\n"
                  f"total spread {(allv.max()-allv.min())*100:.1f} bp")
    ax1.legend(fontsize=8, loc="upper left", ncol=2); ax1.grid(alpha=0.25, axis="y")

    # --- Panel B: basis vs SOFR-native, growing with tenor ---
    tenor_m = {lab: m for m, lab in rc.TENORS}
    order = [lab for _, lab in rc.TENORS]
    lines = [("30/360 Bond", "Comp Annual", "30/360 vs Act/360 (day count)", "#c62828"),
             ("Act/365F", "Comp Annual", "Act/365F vs Act/360 (day count)", "#ef6c00"),
             ("Act/360", "Simple (paid)", "Simple vs Annual comp", "#2e7d32"),
             ("Act/360", "Continuous", "Continuous vs Annual comp", "#6a1b9a")]
    xs2 = [tenor_m[t] for t in order]
    for dc, comp, lbl, col in lines:
        ser = l1[l1.daycount == dc].set_index("tenor")
        nat = l1[l1.daycount == NATIVE_DC].set_index("tenor")[NATIVE_COMP]
        bp = [(ser.loc[t, comp] - nat.loc[t]) * 100 for t in order]
        ax2.plot(xs2, bp, marker="o", ms=4, color=col, label=lbl)
    ax2.axhline(0, color="grey", ls="--", lw=1, label=f"SOFR-native ({NATIVE_DC}, {NATIVE_COMP})")
    ax2.set_xticks(xs2); ax2.set_xticklabels(order)
    ax2.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0f}"))
    ax2.set_ylabel("basis vs native (bp)"); ax2.set_xlabel("tenor")
    ax2.set_title("Convention basis vs SOFR-native — grows with tenor")
    ax2.legend(fontsize=8, loc="best"); ax2.grid(alpha=0.25)

    fig.tight_layout()
    fig.savefig("sofr_rate_conversions.png", dpi=140, bbox_inches="tight")
    print(f"Saved sofr_rate_conversions.png  ({FOCUS_TENOR} DF={df:.6f})")


if __name__ == "__main__":
    main()
