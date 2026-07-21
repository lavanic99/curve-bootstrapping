"""
generate_dashboard.py — self-contained HTML dashboard of the curve outputs.

Builds the SOFR + corporate curves (today's data), computes the full-ladder
term structure, and writes a single theme-aware `dashboard.html` with inline
SVG charts and tables. No external resources (works offline / CSP-safe).

Run:  python3 generate_dashboard.py
"""
import pathlib
import sys

import QuantLib as ql

sys.path.insert(0, str((pathlib.Path(__file__).resolve().parent / "SOFR")))
sys.path.insert(0, str((pathlib.Path(__file__).resolve().parent / "CORPORATE")))
import sofr_pipeline as sofr            # noqa: E402
import credit_curves as cc             # noqa: E402
import conversions as conv             # noqa: E402

TENORS = [("1M", 1/12), ("3M", 0.25), ("6M", 0.5), ("1Y", 1), ("2Y", 2), ("3Y", 3),
          ("5Y", 5), ("7Y", 7), ("10Y", 10)]   # capped at 10Y (Pensford swaps end at 10Y)
SERIES = ["SOFR"] + cc.RATINGS
COLORS = {"SOFR": "#1f4e79", **cc.RATING_COLORS}


def zero(curve, ref, years):
    d = sofr.CALENDAR.advance(ref, ql.Period(int(round(years * 12)), ql.Months),
                              ql.ModifiedFollowing)
    return curve.zeroRate(d, sofr.CURVE_DAYCOUNT, ql.Continuous).rate() * 100


# --------------------------------------------------------------------------- #
def svg_chart(series, ylabel, single=False, height=360):
    """series: {name: [values per tenor]}. Even x-spacing by tenor slot."""
    W, H = 720, height
    ml, mr, mt, mb = 52, 74 if not single else 22, 18, 40
    pw, ph = W - ml - mr, H - mt - mb
    n = len(TENORS)
    xs = [ml + (pw * i / (n - 1)) for i in range(n)]
    allv = [v for s in series.values() for v in s]
    lo, hi = min(allv), max(allv)
    pad = (hi - lo) * 0.08 or 0.5
    lo, hi = lo - pad, hi + pad

    def y(v):
        return mt + ph * (1 - (v - lo) / (hi - lo))

    out = [f'<svg viewBox="0 0 {W} {H}" class="chart" role="img">']
    # y gridlines + labels
    steps = 5
    for k in range(steps + 1):
        val = lo + (hi - lo) * k / steps
        yy = y(val)
        out.append(f'<line class="grid" x1="{ml}" y1="{yy:.1f}" x2="{ml+pw}" y2="{yy:.1f}"/>')
        out.append(f'<text class="tick" x="{ml-8}" y="{yy+3:.1f}" text-anchor="end">{val:.1f}%</text>')
    # x labels
    for i, (lab, _) in enumerate(TENORS):
        out.append(f'<text class="tick" x="{xs[i]:.1f}" y="{H-mb+18}" text-anchor="middle">{lab}</text>')
    out.append(f'<text class="axis-title" x="14" y="{mt+ph/2}" transform="rotate(-90 14 {mt+ph/2})" text-anchor="middle">{ylabel}</text>')
    # series polylines
    labels = []
    for name, vals in series.items():
        pts = " ".join(f"{xs[i]:.1f},{y(vals[i]):.1f}" for i in range(n))
        c = COLORS[name]
        out.append(f'<polyline points="{pts}" fill="none" stroke="{c}" stroke-width="2" stroke-linejoin="round"/>')
        for i in range(n):
            out.append(f'<circle cx="{xs[i]:.1f}" cy="{y(vals[i]):.1f}" r="2.6" fill="{c}"/>')
        if not single:
            labels.append([name, y(vals[-1]), c])
    # right-edge direct labels, decluttered to a minimum vertical gap
    labels.sort(key=lambda l: l[1])
    for i in range(1, len(labels)):
        if labels[i][1] - labels[i-1][1] < 12:
            labels[i][1] = labels[i-1][1] + 12
    for name, yy, c in labels:
        out.append(f'<text class="slab" x="{ml+pw+6}" y="{yy+3:.1f}" fill="{c}">{name}</text>')
    out.append("</svg>")
    return "".join(out)


def rate_table(rows, headers, fmt):
    th = "".join(f"<th>{h}</th>" for h in headers)
    body = []
    for r in rows:
        cells = f'<td class="tenor">{r[0]}</td>' + "".join(
            f"<td>{fmt(v)}</td>" for v in r[1:])
        body.append(f"<tr>{cells}</tr>")
    swatches = '<th></th>' + "".join(
        f'<th><span class="dot" style="background:{COLORS[h]}"></span>{h}</th>'
        for h in headers[1:])
    return (f'<table><thead><tr>{swatches}</tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table>')


def main():
    curves, asof, snap = conv.build_curves()
    ref = curves["SOFR"].referenceDate()

    # data matrices
    allin = {s: [zero(curves[s], ref, yr) for _, yr in TENORS] for s in SERIES}
    spreads = {r: [(allin[r][i] - allin["SOFR"][i]) * 100 for i in range(len(TENORS))]
               for r in cc.RATINGS}
    on = snap.overnight_sofr * 100                     # published overnight SOFR fixing

    allin_rows = [[TENORS[i][0]] + [allin[s][i] for s in SERIES] for i in range(len(TENORS))]
    spread_rows = [[TENORS[i][0]] + [spreads[r][i] for r in cc.RATINGS]
                   for i in range(len(TENORS))]

    chart_allin = svg_chart(allin, "all-in zero rate")
    chart_sofr = svg_chart({"SOFR": allin["SOFR"]}, "SOFR zero rate", single=True, height=280)
    chart_spread = svg_chart(spreads, "spread over SOFR (%)")

    legend = "".join(
        f'<span class="leg"><span class="dot" style="background:{COLORS[s]}"></span>{s}</span>'
        for s in SERIES)

    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SOFR &amp; Corporate Curve Dashboard — {asof}</title>
<style>
  html,body {{ margin:0; background:#f9f9f7; }}
  @media (prefers-color-scheme:dark) {{ html,body {{ background:#0d0d0d; }} }}
</style>
</head>
<body>
<div class="viz-root">
<style>
  .viz-root {{ --surface:#fcfcfb; --plane:#f9f9f7; --ink:#0b0b0b; --ink2:#52514e;
    --muted:#898781; --grid:#e1e0d9; --border:rgba(11,11,11,.10);
    font-family:system-ui,-apple-system,"Segoe UI",sans-serif; color:var(--ink);
    background:var(--plane); padding:28px; max-width:1080px; margin:0 auto; }}
  @media (prefers-color-scheme:dark) {{ .viz-root {{ --surface:#1a1a19; --plane:#0d0d0d;
    --ink:#fff; --ink2:#c3c2b7; --muted:#898781; --grid:#2c2c2a; --border:rgba(255,255,255,.10); }} }}
  :root[data-theme=dark] .viz-root {{ --surface:#1a1a19; --plane:#0d0d0d; --ink:#fff;
    --ink2:#c3c2b7; --grid:#2c2c2a; --border:rgba(255,255,255,.10); }}
  :root[data-theme=light] .viz-root {{ --surface:#fcfcfb; --plane:#f9f9f7; --ink:#0b0b0b;
    --ink2:#52514e; --grid:#e1e0d9; --border:rgba(11,11,11,.10); }}
  .viz-root h1 {{ font-size:22px; margin:0 0 2px; }}
  .viz-root .sub {{ color:var(--ink2); font-size:13px; margin-bottom:20px; }}
  .tiles {{ display:flex; gap:12px; flex-wrap:wrap; margin-bottom:24px; }}
  .tile {{ background:var(--surface); border:1px solid var(--border); border-radius:10px;
    padding:14px 18px; min-width:150px; }}
  .tile .k {{ color:var(--muted); font-size:11px; text-transform:uppercase; letter-spacing:.04em; }}
  .tile .v {{ font-size:24px; font-weight:600; margin-top:4px; }}
  .card {{ background:var(--surface); border:1px solid var(--border); border-radius:12px;
    padding:18px 20px; margin-bottom:20px; overflow-x:auto; }}
  .card h2 {{ font-size:15px; margin:0 0 12px; }}
  .chart {{ width:100%; height:auto; }}
  .grid {{ stroke:var(--grid); stroke-width:1; }}
  .tick {{ fill:var(--muted); font-size:11px; }}
  .axis-title {{ fill:var(--muted); font-size:11px; }}
  .slab {{ font-size:11px; font-weight:600; }}
  .legend {{ display:flex; flex-wrap:wrap; gap:14px; margin-bottom:8px; font-size:12px; color:var(--ink2); }}
  .leg,.card h2 span {{ display:inline-flex; align-items:center; gap:6px; }}
  .dot {{ width:10px; height:10px; border-radius:3px; display:inline-block; }}
  table {{ border-collapse:collapse; width:100%; font-size:12.5px; font-variant-numeric:tabular-nums; }}
  th,td {{ padding:6px 10px; text-align:right; border-bottom:1px solid var(--border); white-space:nowrap; }}
  th {{ color:var(--ink2); font-weight:600; font-size:11.5px; }}
  th .dot {{ margin-right:5px; }}
  td.tenor,th:first-child {{ text-align:left; color:var(--ink2); font-weight:600; }}
  .note {{ color:var(--muted); font-size:12px; line-height:1.55; }}
</style>

<h1>SOFR &amp; Corporate Curve Dashboard</h1>
<div class="sub">Bootstrapped SOFR risk-free curve + rating credit spreads · as at {asof}</div>

<div class="tiles">
  <div class="tile"><div class="k">Overnight SOFR</div><div class="v">{on:.2f}%</div></div>
  <div class="tile"><div class="k">BBB · 6M all-in</div><div class="v">{allin['BBB'][2]:.2f}%</div></div>
  <div class="tile"><div class="k">B · 6M all-in</div><div class="v">{allin['B'][2]:.2f}%</div></div>
  <div class="tile"><div class="k">Ratings</div><div class="v">AAA–CCC</div></div>
</div>

<div class="card">
  <h2>All-in fixed loan rate by rating</h2>
  <div class="legend">{legend}</div>
  {chart_allin}
</div>

<div class="card">
  <h2>SOFR risk-free term structure</h2>
  {chart_sofr}
</div>

<div class="card">
  <h2>Credit spread over SOFR</h2>
  {chart_spread}
</div>

<div class="card">
  <h2>All-in fixed loan rate (%) — continuous zero, SOFR + credit spread</h2>
  {rate_table(allin_rows, ["Tenor"] + SERIES, lambda v: f"{v:.2f}%")}
</div>

<div class="card">
  <h2>Credit spread over SOFR (bp)</h2>
  {rate_table(spread_rows, ["Tenor"] + cc.RATINGS, lambda v: f"{v:.0f}")}
</div>

<div class="card note">
  <b>Method:</b> SOFR curve bootstrapped from NY Fed fixings + CME SR1/SR3 futures + SOFR OIS swaps
  (reprices inputs within ~0.2&nbsp;bp). Credit spread = rating OAS × IG maturity-shape + Treasury–SOFR basis.
  <br><b>Caveat:</b> spreads are public rated-bond references (a floor), not a specific unrated borrower's
  spread. The long-end high-yield corner (BB/B/CCC) applies the IG maturity slope and is the roughest
  approximation. Research/analysis only — not investment advice or an executable quote.
</div>
</div>
</body>
</html>"""

    out = pathlib.Path(__file__).resolve().parent / "dashboard.html"
    out.write_text(html)
    print(f"Saved {out.name}  (as at {asof}; O/N {on:.2f}%)")


if __name__ == "__main__":
    main()
