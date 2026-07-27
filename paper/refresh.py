"""Regenerate the paper's data (doc_data.json) and figures from live 10Y-capped
curves. Reads the model in ../SOFR and ../CORPORATE. Run:  python3 refresh.py"""
import sys, pathlib, json
HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "SOFR"))
sys.path.insert(0, str(ROOT / "CORPORATE"))
import QuantLib as ql
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import sofr_pipeline as sofr, credit_curves as cc, conversions as conv

TEN = [("1M",1),("3M",3),("6M",6),("1Y",12),("2Y",24),("3Y",36),("5Y",60),("7Y",84),("10Y",120)]
curves, asof, snap = conv.build_curves()
ref = curves["SOFR"].referenceDate()
def z(c, m):
    d = sofr.CALENDAR.advance(ref, ql.Period(m, ql.Months), ql.ModifiedFollowing)
    return c.zeroRate(d, sofr.CURVE_DAYCOUNT, ql.Continuous).rate() * 100
d = cc.fetch_fred()
data = {"asof": asof, "on": round(snap.overnight_sofr*100, 2), "labels": [t for t,_ in TEN],
        "sofr": [round(z(curves["SOFR"],m),2) for _,m in TEN],
        "oas": {r: round(d["oas"][r]*1e4) for r in cc.RATINGS},
        "allin": {r: [round(z(curves[r],m),2) for _,m in TEN] for r in cc.RATINGS},
        "spread": {r: [round((z(curves[r],m)-z(curves["SOFR"],m))*100) for _,m in TEN] for r in cc.RATINGS}}
(HERE/"doc_data.json").write_text(json.dumps(data, indent=1))

# Monochrome, academic (black & white) figures: grayscale + distinct markers.
x = list(range(len(TEN))); labels = [t for t,_ in TEN]
pct = FuncFormatter(lambda v,_: f"{v:.1f}%")
GRAY = {"AAA":"0.62","AA":"0.54","A":"0.46","BBB":"0.38","BB":"0.27","B":"0.15","CCC":"0.0"}
MK = {"SOFR":"o","AAA":"s","AA":"^","A":"D","BBB":"v","BB":"X","B":"P","CCC":"*"}
def _style(ax):
    ax.grid(True, color="0.85", lw=0.6); ax.set_axisbelow(True)
    for s in ax.spines.values(): s.set_color("0.4")
    ax.tick_params(colors="0.2")

fig,ax=plt.subplots(figsize=(7,3.3),dpi=150)
ax.plot(x,data["sofr"],color="black",lw=1.6,marker="o",ms=4,mfc="white",mec="black")
ax.set_xticks(x); ax.set_xticklabels(labels); ax.yaxis.set_major_formatter(pct)
ax.set_title("SOFR risk-free zero curve",fontsize=10,color="black"); ax.set_ylabel("continuous zero rate"); _style(ax)
for xi in (0,4,8): ax.annotate(f"{data['sofr'][xi]:.2f}%",(xi,data['sofr'][xi]),textcoords="offset points",xytext=(0,7),ha="center",fontsize=8)
fig.tight_layout(); fig.savefig(HERE/"chart_sofr.png",bbox_inches="tight"); plt.close()

fig,ax=plt.subplots(figsize=(7,4.0),dpi=150)
ax.plot(x,data["sofr"],color="black",lw=1.4,ls="--",marker=MK["SOFR"],ms=3.5,mfc="white",label="SOFR")
for r in cc.RATINGS: ax.plot(x,data["allin"][r],color=GRAY[r],lw=1.3,marker=MK[r],ms=3.5,label=r)
ax.set_xticks(x); ax.set_xticklabels(labels); ax.yaxis.set_major_formatter(pct)
ax.set_title("All-in fixed loan rate by rating",fontsize=10,color="black"); ax.set_ylabel("continuous zero rate"); _style(ax)
ax.legend(ncol=4,fontsize=8,loc="upper left",frameon=True,edgecolor="0.6")
fig.tight_layout(); fig.savefig(HERE/"chart_allin.png",bbox_inches="tight"); plt.close()
print("refreshed paper data + figures — asof", asof, "| O/N", data["on"])
