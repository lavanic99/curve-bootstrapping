"""Discount-factor and instantaneous-forward curve figures for the paper,
in the same monochrome style. Run:  python3 plot_curves.py"""
import sys, pathlib
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "SOFR"))
import QuantLib as ql, sofr_pipeline as sofr

HERE = pathlib.Path(__file__).resolve().parent
snap = sofr.fetch_snapshot()
curve, *_ = sofr.build_curve(snap)
tmax = curve.maxTime()

def _style(ax):
    ax.grid(True, color="0.85", lw=0.6); ax.set_axisbelow(True)
    for s in ax.spines.values(): s.set_color("0.4")
    ax.tick_params(colors="0.2"); ax.set_xlabel("years", color="0.2")

# Discount curve: DF(0,T)
ts = np.linspace(0.0, tmax, 800)
df = [curve.discount(t) for t in ts]
fig, ax = plt.subplots(figsize=(7, 3.4), dpi=150)
ax.plot(ts, df, color="black", lw=1.7)
ax.set_ylabel("discount factor  DF(0, T)", color="0.2")
ax.set_title("SOFR discount curve", fontsize=10, color="black")
ax.set_ylim(min(df) * 0.995, 1.003); _style(ax)
fig.tight_layout(); fig.savefig(HERE / "chart_discount.png", bbox_inches="tight"); plt.close()

# Instantaneous forward curve (piecewise flat under log-linear on DF)
tf = np.linspace(0.01, tmax, 2000)
fwd = [curve.forwardRate(t, min(t + 1/365, tmax), ql.Continuous, ql.Annual, True).rate() * 100 for t in tf]
fig, ax = plt.subplots(figsize=(7, 3.4), dpi=150)
ax.plot(tf, fwd, color="black", lw=1.2)
ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.1f}%"))
ax.set_ylabel("instantaneous forward", color="0.2")
ax.set_title("SOFR instantaneous forward curve", fontsize=10, color="black")
_style(ax)
fig.tight_layout(); fig.savefig(HERE / "chart_forward.png", bbox_inches="tight"); plt.close()
print(f"wrote chart_discount.png, chart_forward.png  (asof {snap.quote_date.ISO()}, max {tmax:.1f}y)")
