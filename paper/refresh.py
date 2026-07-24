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

x = list(range(len(TEN))); labels = [t for t,_ in TEN]
COL={"SOFR":"#1f4e79","AAA":"#1b5e20","AA":"#2e7d32","A":"#66bb6a","BBB":"#c9a227","BB":"#ef6c00","B":"#e64a19","CCC":"#c62828"}
pct=FuncFormatter(lambda v,_:f"{v:.1f}%")
fig,ax=plt.subplots(figsize=(7,3.4),dpi=150)
ax.plot(x,data["sofr"],color=COL["SOFR"],lw=2,marker="o",ms=4)
ax.set_xticks(x); ax.set_xticklabels(labels); ax.yaxis.set_major_formatter(pct)
ax.set_title(f"SOFR risk-free zero curve — {asof}",fontsize=11); ax.grid(alpha=.25); ax.set_ylabel("continuous zero rate")
for xi in (0,4,8): ax.annotate(f"{data['sofr'][xi]:.2f}%",(xi,data['sofr'][xi]),textcoords="offset points",xytext=(0,7),ha="center",fontsize=8)
fig.tight_layout(); fig.savefig(HERE/"chart_sofr.png",bbox_inches="tight"); plt.close()

fig,ax=plt.subplots(figsize=(7,4.0),dpi=150)
ax.plot(x,data["sofr"],color=COL["SOFR"],lw=2,marker="o",ms=3,label="SOFR")
for r in cc.RATINGS: ax.plot(x,data["allin"][r],color=COL[r],lw=1.7,marker="o",ms=3,label=r)
ax.set_xticks(x); ax.set_xticklabels(labels); ax.yaxis.set_major_formatter(pct)
ax.set_title(f"All-in fixed loan rate by rating — {asof}",fontsize=11); ax.grid(alpha=.25)
ax.set_ylabel("continuous zero rate"); ax.legend(ncol=4,fontsize=8,loc="upper left")
fig.tight_layout(); fig.savefig(HERE/"chart_allin.png",bbox_inches="tight"); plt.close()
print("refreshed paper data + figures — asof", asof, "| O/N", data["on"])
