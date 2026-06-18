"""Plot the bootstrapped SOFR curve: zero & instantaneous-forward rates,
with input nodes and the futures->swaps segments marked."""
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import QuantLib as ql

from sofr_pipeline import (fetch_snapshot, build_curve, CURVE_DAYCOUNT, CALENDAR)

snap = fetch_snapshot()
curve, handle, labeled = build_curve(snap, interpolation="loglinear")
ref = curve.referenceDate()

# Dense sampling. Start just above 0 (zero rate is a 0/0 limit at t=0) and then
# anchor t=0 explicitly at the instantaneous short rate so the line reaches the
# left axis / overnight point instead of leaving a small void.
tmax = curve.maxTime()
ts = np.linspace(1.0 / 365, tmax, 4000)
zero = [curve.zeroRate(t, ql.Continuous).rate() * 100 for t in ts]
fwd = [curve.forwardRate(t, t + 1e-4, ql.Continuous).rate() * 100 for t in ts]
short_rate = curve.forwardRate(0.0, 0.0, ql.Continuous).rate() * 100   # instantaneous fwd at 0
ts = np.insert(ts, 0, 0.0)
zero = [short_rate] + zero
fwd = [short_rate] + fwd

# Node points (date -> time/rate)
node_t, node_z = [], []
for d, df in curve.nodes():
    t = CURVE_DAYCOUNT.yearFraction(ref, d)
    if t > 0:
        node_t.append(t)
        node_z.append(curve.zeroRate(d, CURVE_DAYCOUNT, ql.Continuous).rate() * 100)

# Last futures time (segment boundary)
fut_times = [CURVE_DAYCOUNT.yearFraction(ref, l.helper.latestDate())
             for l in labeled if l.kind == "future"]
fut_end = max(fut_times)

pct = FuncFormatter(lambda v, _: f"{v:.2f}%")
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 5.5))

# --- Full curve ---
ax1.axvspan(0, fut_end, color="#4C9BE8", alpha=0.08, label="futures (SR1/SR3)")
ax1.axvspan(fut_end, tmax, color="#E8954C", alpha=0.08, label="OIS swaps")
ax1.plot(ts, zero, color="#1f4e79", lw=2, label="zero rate (cont.)")
ax1.plot(ts, fwd, color="#c0392b", lw=1.2, alpha=0.8, label="inst. forward")
ax1.scatter(node_t, node_z, s=22, color="#1f4e79", zorder=5, label="curve nodes")
ax1.yaxis.set_major_formatter(pct)
ax1.set_xlabel("years"); ax1.set_title(f"SOFR curve — {snap.quote_date.ISO()}")
ax1.legend(loc="lower right", fontsize=9); ax1.grid(alpha=0.25)

# --- Short end zoom (0-3y) ---
mask = ts <= 3.0
ax2.plot(ts[mask], np.array(zero)[mask], color="#1f4e79", lw=2, label="zero rate")
ax2.plot(ts[mask], np.array(fwd)[mask], color="#c0392b", lw=1.2, alpha=0.8, label="inst. forward")
sn = [(t, z) for t, z in zip(node_t, node_z) if t <= 3.0]
ax2.scatter([t for t, _ in sn], [z for _, z in sn], s=28, color="#1f4e79", zorder=5)
ax2.axvline(fut_end, color="#E8954C", ls="--", lw=1, alpha=0.7)
ax2.yaxis.set_major_formatter(pct)
ax2.set_xlabel("years"); ax2.set_title("Short end (0–3y) — futures-pinned, monthly")
ax2.legend(loc="lower right", fontsize=9); ax2.grid(alpha=0.25)

fig.tight_layout()
fig.savefig("sofr_curve.png", dpi=140, bbox_inches="tight")
print("Saved sofr_curve.png  | futures end ~%.2fy, max %.1fy" % (fut_end, tmax))
