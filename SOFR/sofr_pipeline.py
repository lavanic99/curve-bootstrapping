"""
Production SOFR OIS curve — free end-of-day, three-segment bootstrap.

Segments (shortest -> longest, the textbook construction):
  1. Overnight anchor   : official O/N SOFR (NY Fed)         -> 1-day deposit
  2. Front end          : CME SR1 (1M) + SR3 (3M) futures    -> futures helpers
  3. Long end           : par SOFR OIS swaps (Pensford)       -> OIS helpers

Futures pin the sub-1Y points with real market quotes (so 2M/4M/9M are
market-driven, not interpolated). The curve is bootstrapped with QuantLib so
it reprices every input instrument exactly.

Data sources (no terminal / no paid feed):
  * yfinance (Yahoo)    -> SR1/SR3 SOFR futures settlement-ish prices (delayed/EOD)
  * Pensford quotes.xml -> par SOFR OIS swap rates 1Y..30Y
  * NY Fed API          -> official overnight SOFR

Honest limitations:
  * yfinance is delayed/EOD and unofficial (can break or rate-limit).
  * SR3 convexity adjustment is set to 0 (small in the front year; see CONVEXITY).
  * Deep contracts can be thin; a coverage check fails loudly if so.

Run:  python3 sofr_pipeline.py
"""
from __future__ import annotations

import contextlib
import io
import json
import sys
import warnings
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timezone

import requests
import pandas as pd
import QuantLib as ql

warnings.filterwarnings("ignore")

# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #
PENSFORD_QUOTES = "https://19621209.fs1.hubspotusercontent-na1.net/hubfs/19621209/quotes.xml"
NYFED_SOFR = "https://markets.newyorkfed.org/api/rates/secured/sofr/last/1.json"
NYFED_SOFR_HIST = "https://markets.newyorkfed.org/api/rates/secured/sofr/last/{n}.json"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 Chrome/124.0 Safari/537.36"}

SETTLEMENT_DAYS = 2
CURVE_DAYCOUNT = ql.Actual360()
CALENDAR = ql.UnitedStates(ql.UnitedStates.GovernmentBond)

# How many futures to attempt, and where to hand off to swaps.
SR1_COUNT = 9     # monthly contracts -> pins ~first 9 months (covers 1/2/4/6/9M)
SR3_COUNT = 10    # quarterly contracts -> extends the front to ~2.5Y
CONVEXITY = 0.0   # SR3 futures-vs-OIS convexity adjustment (rate units). 0 = off.
FIXINGS_DAYS = 60  # calendar days of historical SOFR to load (recovers front contract)
# Once historical fixings + the in-progress front future are in, a standalone
# overnight deposit is redundant and conflicts with the front future (they
# overlap and disagree by ~1bp), creating a small artificial dip. Let the
# futures own the front end. The published O/N rate is still kept for the
# sanity cross-check and provenance.
USE_ON_DEPOSIT = False

# --- Standard USD SOFR OIS conventions (issue #3: set explicitly, don't default) ---
OIS_PAYMENT_LAG = 2                      # business days
OIS_PAYMENT_FREQ = ql.Annual
OIS_PAYMENT_CONV = ql.ModifiedFollowing
# (day count ACT/360 and daily compounding come from the Sofr index itself.)

# --- Input sanity bounds (issue #7) ---
RATE_MIN, RATE_MAX = 0.0, 0.20           # plausible decimal rate band
PRICE_MIN, PRICE_MAX = 80.0, 100.0       # SOFR futures price = 100 - rate
ON_XCHECK_TOL = 0.0010                   # warn if Pensford O/N vs NY Fed > 10 bp
STRIP_JUMP_WARN = 0.015                  # warn if adjacent futures imply >150 bp jump

# CME month codes
SR1_CODE = {1: "F", 2: "G", 3: "H", 4: "J", 5: "K", 6: "M",
            7: "N", 8: "Q", 9: "U", 10: "V", 11: "X", 12: "Z"}
SR3_CODE = {3: "H", 6: "M", 9: "U", 12: "Z"}   # quarterly IMM months


# --------------------------------------------------------------------------- #
# Data layer
# --------------------------------------------------------------------------- #
@dataclass
class MarketSnapshot:
    quote_date: ql.Date
    overnight_sofr: float
    swaps: dict[int, float] = field(default_factory=dict)      # {years: par rate}
    sr1: dict[tuple[int, int], float] = field(default_factory=dict)  # {(m,y): price}
    sr3: dict[tuple[int, int], float] = field(default_factory=dict)
    fixings: list[tuple[ql.Date, float]] = field(default_factory=list)  # historical SOFR
    nyfed_sofr: float | None = None
    nyfed_date: str = ""
    raw_timestamp: str = ""
    provenance: dict = field(default_factory=dict)


def _parse_pensford_date(s: str) -> ql.Date:
    m, d, y = (int(x) for x in s.split("/"))
    return ql.Date(d, m, y)


def fetch_pensford(snap_into: dict) -> None:
    """Overnight SOFR + par OIS swap rates from Pensford."""
    r = requests.get(PENSFORD_QUOTES, headers=UA, timeout=30)
    r.raise_for_status()
    root = ET.fromstring(r.text)
    overnight = quote_date = None
    swaps: dict[int, float] = {}
    for rec in root.findall("record"):
        sym = (rec.findtext("symbol") or "").strip()
        quote = rec.findtext("quote")
        qdate = rec.findtext("quoteDate")
        if quote is None:
            continue
        if quote_date is None and qdate:
            quote_date = _parse_pensford_date(qdate.strip())
        if sym == "SOFR":
            overnight = float(quote)
        elif sym.startswith("SOFRSWAP Y"):
            swaps[int(sym.replace("SOFRSWAP Y", "").strip())] = float(quote)
    if overnight is None or quote_date is None or not swaps:
        raise RuntimeError("Pensford feed missing O/N / quote-date / swaps")
    snap_into.update(quote_date=quote_date, overnight=overnight,
                     swaps=dict(sorted(swaps.items())),
                     ts=root.attrib.get("timeStamp", ""))


def _gen_sr1(y: int, m: int, n: int) -> list[tuple[int, int]]:
    out = []
    for _ in range(n):
        out.append((m, y))
        m += 1
        if m > 12:
            m, y = 1, y + 1
    return out


def _gen_sr3(y: int, m: int, n: int) -> list[tuple[int, int]]:
    quarters = [(mm, yy) for yy in range(y, y + n // 4 + 3) for mm in (3, 6, 9, 12)]
    quarters = [q for q in quarters if (q[1], q[0]) >= (y, m)]
    return quarters[:n]


def _yf_last_price(ticker: str):
    import yfinance as yf
    buf = io.StringIO()
    with contextlib.redirect_stderr(buf):
        df = yf.download(ticker, period="7d", progress=False, auto_adjust=True)
    if df is None or not len(df):
        return None
    s = df["Close"].dropna()
    return None if not len(s) else float(s.iloc[-1])


def fetch_futures(quote_date: ql.Date) -> tuple[dict, dict]:
    """Pull SR1 monthly and SR3 quarterly SOFR futures prices from Yahoo."""
    y, m = quote_date.year(), quote_date.month()
    sr1_out, sr3_out = {}, {}
    for (mm, yy) in _gen_sr1(y, m, SR1_COUNT):
        p = _yf_last_price(f"SR1{SR1_CODE[mm]}{yy % 100:02d}.CME")
        if p is not None:
            sr1_out[(mm, yy)] = p
    for (mm, yy) in _gen_sr3(y, m, SR3_COUNT):
        p = _yf_last_price(f"SR3{SR3_CODE[mm]}{yy % 100:02d}.CME")
        if p is not None:
            sr3_out[(mm, yy)] = p
    if len(sr1_out) < 4 or len(sr3_out) < 4:
        raise RuntimeError(
            f"Insufficient futures coverage from Yahoo "
            f"(SR1={len(sr1_out)}, SR3={len(sr3_out)}); refusing to build a thin curve.")
    return sr1_out, sr3_out


def fetch_nyfed_history(n_days: int = FIXINGS_DAYS) -> list[tuple[ql.Date, float]]:
    """Historical daily SOFR fixings from the NY Fed (issue #6).

    Used to value the in-progress front futures contract, whose accrual period
    has already partly realized. Returns [(ql.Date, decimal_rate), ...].
    """
    out = []
    d = requests.get(NYFED_SOFR_HIST.format(n=n_days), headers=UA, timeout=20).json()
    for rec in d.get("refRates", []):
        eff = rec.get("effectiveDate")          # 'YYYY-MM-DD'
        rate = rec.get("percentRate")
        if eff and rate is not None:
            y, m, day = (int(x) for x in eff.split("-"))
            out.append((ql.Date(day, m, y), float(rate) / 100.0))
    return out


def sanity_check(snap: MarketSnapshot) -> None:
    """Validate the raw inputs *before* building (issue #7).

    Hard failures raise (a bad value would otherwise be baked in silently and
    still pass the reprice check). Soft anomalies warn.
    """
    hard, soft = [], []

    if not (RATE_MIN < snap.overnight_sofr < RATE_MAX):
        hard.append(f"O/N SOFR {snap.overnight_sofr} outside ({RATE_MIN},{RATE_MAX})")
    if snap.nyfed_sofr is not None and abs(snap.overnight_sofr - snap.nyfed_sofr) > ON_XCHECK_TOL:
        soft.append(f"Pensford O/N {snap.overnight_sofr:.4%} vs NY Fed "
                    f"{snap.nyfed_sofr:.4%} differ > {ON_XCHECK_TOL*1e4:.0f} bp")

    for (mm, yy), p in {**snap.sr1, **snap.sr3}.items():
        if not (PRICE_MIN <= p <= PRICE_MAX):
            hard.append(f"futures {mm:02d}/{yy} price {p} outside [{PRICE_MIN},{PRICE_MAX}]")

    for y, r in snap.swaps.items():
        if not (RATE_MIN < r < RATE_MAX):
            hard.append(f"swap {y}Y rate {r} outside ({RATE_MIN},{RATE_MAX})")

    # Strips must actually vary (a flat/duplicated strip signals a stale pull).
    if len(set(snap.sr1.values())) <= 1:
        soft.append("SR1 strip has no variation (possibly stale)")
    if len(set(snap.sr3.values())) <= 1:
        soft.append("SR3 strip has no variation (possibly stale)")

    # Implausibly large month-to-month jumps in implied rate.
    for name, strip in (("SR1", snap.sr1), ("SR3", snap.sr3)):
        items = sorted(strip.items(), key=lambda kv: (kv[0][1], kv[0][0]))
        for (a, pa), (b, pb) in zip(items, items[1:]):
            if abs((100 - pb) - (100 - pa)) / 100.0 > STRIP_JUMP_WARN:
                soft.append(f"{name} {a}->{b} implies >{STRIP_JUMP_WARN*1e4:.0f} bp jump")

    for w in soft:
        print(f"  [warn] {w}", file=sys.stderr)
    if hard:
        raise RuntimeError("Input sanity check FAILED:\n  - " + "\n  - ".join(hard))


def fetch_snapshot() -> MarketSnapshot:
    run_utc = datetime.now(timezone.utc).isoformat(timespec="seconds")
    box: dict = {}
    fetch_pensford(box)
    sr1, sr3 = fetch_futures(box["quote_date"])
    snap = MarketSnapshot(
        quote_date=box["quote_date"], overnight_sofr=box["overnight"],
        swaps=box["swaps"], sr1=sr1, sr3=sr3, raw_timestamp=box["ts"],
    )
    # Official O/N cross-check + historical fixings (same source).
    try:
        d = requests.get(NYFED_SOFR, headers=UA, timeout=15).json()
        snap.nyfed_sofr = float(d["refRates"][0]["percentRate"]) / 100.0
        snap.nyfed_date = d["refRates"][0].get("effectiveDate", "")
    except Exception as e:                       # noqa: BLE001
        print(f"  [warn] NY Fed cross-check unavailable: {e}", file=sys.stderr)
    try:
        snap.fixings = fetch_nyfed_history()
    except Exception as e:                       # noqa: BLE001
        print(f"  [warn] NY Fed history unavailable ({e}); front contract will be skipped",
              file=sys.stderr)

    sanity_check(snap)

    snap.provenance = {
        "run_utc": run_utc,
        "quote_date": snap.quote_date.ISO(),
        "overnight_sofr_source": "Pensford quotes.xml (SOFR)",
        "pensford_timestamp": snap.raw_timestamp,
        "nyfed_overnight": snap.nyfed_sofr,
        "nyfed_latest_date": snap.nyfed_date,
        "futures_source": "Yahoo/yfinance (delayed, unofficial last-close)",
        "swaps_source": "Pensford quotes.xml (SOFRSWAP Yn, indicative)",
        "n_sr1": len(snap.sr1), "n_sr3": len(snap.sr3),
        "n_swaps": len(snap.swaps), "n_fixings": len(snap.fixings),
    }
    return snap


# --------------------------------------------------------------------------- #
# Curve construction
# --------------------------------------------------------------------------- #
@dataclass
class Labeled:
    label: str
    kind: str            # 'deposit' | 'future' | 'ois'
    market: float        # market quote (rate for deposit/ois, price for future)
    helper: object


def build_curve(snap: MarketSnapshot, interpolation: str = "loglinear"):
    ql.Settings.instance().evaluationDate = snap.quote_date
    ref = snap.quote_date
    index = ql.Sofr()
    labeled: list[Labeled] = []

    # Load historical SOFR fixings so contracts with a realized accrual portion
    # (the in-progress front month) can be valued (issue #6). Fixings live in a
    # process-wide store keyed by index name, so clear first for a clean rebuild.
    fix_cal = index.fixingCalendar()
    with contextlib.suppress(Exception):
        ql.IndexManager.instance().clearHistory(index.name())
    loaded = []
    for d, r in snap.fixings:
        if d < ref and fix_cal.isBusinessDay(d):
            index.addFixing(d, r, True)
            loaded.append(d)
    prev_bd = fix_cal.advance(ref, ql.Period(-1, ql.Days))
    front_ok = bool(loaded) and max(loaded) >= prev_bd     # realized days covered?
    min_fix = min(loaded) if loaded else ref

    def include_future(h) -> bool:
        if h.earliestDate() > ref:
            return True                                    # fully forward-starting
        return front_ok and h.earliestDate() >= min_fix    # in-progress, realized covered

    # 1) Overnight anchor (optional). With fixings + the in-progress front
    #    future, this is redundant and introduces a ~1bp front-end dip, so it
    #    is off by default; the futures define the front end.
    if USE_ON_DEPOSIT:
        q = ql.SimpleQuote(snap.overnight_sofr)
        labeled.append(Labeled("O/N", "deposit", snap.overnight_sofr,
            ql.DepositRateHelper(ql.QuoteHandle(q), ql.Period(1, ql.Days), 0,
                                 CALENDAR, ql.Following, False, index.dayCounter())))

    # 2) Futures. Skip any contract whose accrual period has already started
    #    (would need historical fixings); keep only forward-starting ones.
    def fut_helper(price, month, year, freq):
        qq = ql.SimpleQuote(price)
        h = ql.SofrFutureRateHelper(ql.QuoteHandle(qq), month, year, freq,
                                    ql.QuoteHandle(ql.SimpleQuote(CONVEXITY)))
        return qq, h

    sr1_h: list[Labeled] = []
    for (mm, yy), price in sorted(snap.sr1.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        _, h = fut_helper(price, mm, yy, ql.Monthly)
        if include_future(h):
            sr1_h.append(Labeled(f"SR1 {mm:02d}/{yy}", "future", price, h))

    sr3_h: list[Labeled] = []
    for (mm, yy), price in sorted(snap.sr3.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        _, h = fut_helper(price, mm, yy, ql.Quarterly)
        if include_future(h):
            sr3_h.append(Labeled(f"SR3 {mm:02d}/{yy}", "future", price, h))

    # Clean handoff: SR1 monthly for the front, SR3 quarterly only AFTER the
    # last SR1 matures (no overlapping fixing periods).
    last_sr1 = sr1_h[-1].helper.latestDate() if sr1_h else ref
    sr3_kept = [l for l in sr3_h if l.helper.earliestDate() > last_sr1]
    futures = sr1_h + sr3_kept
    labeled += futures

    # 3) OIS swaps beyond the last future (+ 1M buffer).
    fut_cutoff = (futures[-1].helper.latestDate() if futures else ref) + ql.Period(1, ql.Months)
    for years, rate in snap.swaps.items():
        qq = ql.SimpleQuote(rate)
        h = ql.OISRateHelper(
            SETTLEMENT_DAYS, ql.Period(years, ql.Years), ql.QuoteHandle(qq), index,
            discountingCurve=ql.YieldTermStructureHandle(),
            telescopicValueDates=False,
            paymentLag=OIS_PAYMENT_LAG,
            paymentConvention=OIS_PAYMENT_CONV,
            paymentFrequency=OIS_PAYMENT_FREQ,
            paymentCalendar=CALENDAR,
        )
        if h.latestDate() > fut_cutoff:
            labeled.append(Labeled(f"{years}Y OIS", "ois", rate, h))

    helpers = [l.helper for l in labeled]
    if interpolation == "logcubic":
        curve = ql.PiecewiseLogCubicDiscount(0, CALENDAR, helpers, CURVE_DAYCOUNT)
    else:
        curve = ql.PiecewiseLogLinearDiscount(0, CALENDAR, helpers, CURVE_DAYCOUNT)
    curve.enableExtrapolation()
    return curve, ql.YieldTermStructureHandle(curve), labeled


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #
def validate(curve, labeled: list[Labeled], tol_bp: float = 0.5) -> pd.DataFrame:
    """Uniform check: curve-implied quote vs market quote for every instrument."""
    curve.discount(curve.referenceDate())   # force bootstrap
    rows, max_err = [], 0.0
    for l in labeled:
        implied = l.helper.impliedQuote()
        if l.kind == "future":               # price units -> bp = price diff * 100
            err_bp = (implied - l.market) * 100.0
            mk, im = l.market, implied
        else:                                 # rate units -> bp = rate diff * 1e4
            err_bp = (implied - l.market) * 1e4
            mk, im = l.market * 100, implied * 100
        max_err = max(max_err, abs(err_bp))
        rows.append({"instrument": l.label, "kind": l.kind,
                     "market": mk, "implied": im, "error_bp": err_bp})
    df = pd.DataFrame(rows)
    ok = max_err <= tol_bp
    print(f"\nReprice check: max error {max_err:.4f} bp -> {'PASS' if ok else 'FAIL'} (tol {tol_bp} bp)")
    if not ok:
        raise RuntimeError("Curve does not reprice inputs within tolerance")
    return df


# --------------------------------------------------------------------------- #
# Output
# --------------------------------------------------------------------------- #
def nodes_table(curve) -> pd.DataFrame:
    return pd.DataFrame([(d.ISO(), df) for d, df in curve.nodes()],
                        columns=["date", "discount_factor"])


def short_end_curve(curve, months=(1, 2, 3, 4, 6, 9, 12)) -> pd.DataFrame:
    ref = curve.referenceDate()
    rows = []
    for m in months:
        d = CALENDAR.advance(ref, ql.Period(m, ql.Months))
        rows.append({"tenor": f"{m}M", "date": d.ISO(),
                     "zero_cont_%": curve.zeroRate(d, CURVE_DAYCOUNT, ql.Continuous).rate() * 100,
                     "simple_fwd_%": curve.forwardRate(ref, d, CURVE_DAYCOUNT, ql.Simple).rate() * 100,
                     "discount_factor": curve.discount(d)})
    return pd.DataFrame(rows)


def zero_curve(curve, years=range(1, 31)) -> pd.DataFrame:
    ref = curve.referenceDate()
    rows = []
    for y in years:
        d = CALENDAR.advance(ref, ql.Period(y, ql.Years))
        rows.append({"years": y, "date": d.ISO(),
                     "zero_cont_%": curve.zeroRate(d, CURVE_DAYCOUNT, ql.Continuous).rate() * 100,
                     "fwd_cont_%": curve.forwardRate(ref, d, CURVE_DAYCOUNT, ql.Continuous).rate() * 100,
                     "discount_factor": curve.discount(d)})
    return pd.DataFrame(rows)


def main() -> None:
    print("Fetching SOFR snapshot (Pensford swaps + Yahoo futures + NY Fed) ...")
    snap = fetch_snapshot()
    print(f"  quote date : {snap.quote_date.ISO()}  (Pensford ts: {snap.raw_timestamp})")
    print(f"  O/N SOFR   : {snap.overnight_sofr:.4%}", end="")
    if snap.nyfed_sofr is not None:
        print(f"   | NY Fed {snap.nyfed_sofr:.4%}  (Δ {(snap.overnight_sofr-snap.nyfed_sofr)*1e4:+.2f} bp)")
    else:
        print()
    print(f"  SR1 futures: {len(snap.sr1)}   SR3 futures: {len(snap.sr3)}   OIS swaps: {len(snap.swaps)}")
    print(f"  fixings    : {len(snap.fixings)} historical SOFR obs"
          f"{' (latest ' + snap.nyfed_date + ')' if snap.nyfed_date else ''}")

    print("\nBootstrapping three-segment curve (log-linear on discount factors) ...")
    curve, handle, labeled = build_curve(snap, interpolation="loglinear")
    used = {"deposit": 0, "future": 0, "ois": 0}
    for l in labeled:
        used[l.kind] += 1
    print(f"  instruments used: {used['deposit']} deposit + {used['future']} futures + {used['ois']} OIS")

    nodes = nodes_table(curve)
    print(f"\nCurve nodes ({len(nodes)}):")
    print(nodes.to_string(index=False))

    check = validate(curve, labeled)
    print(check.to_string(index=False, formatters={
        "market": "{:.4f}".format, "implied": "{:.4f}".format, "error_bp": "{:+.4f}".format}))

    se = short_end_curve(curve)
    print("\nShort end (all sub-1Y points now futures-pinned):")
    print(se.to_string(index=False, formatters={
        "zero_cont_%": "{:.4f}".format, "simple_fwd_%": "{:.4f}".format,
        "discount_factor": "{:.6f}".format}))

    zc = zero_curve(curve)
    nodes.to_csv("sofr_nodes.csv", index=False)
    se.to_csv("sofr_short_end.csv", index=False)
    zc.to_csv("sofr_zero_curve.csv", index=False)
    snap.provenance["instruments_used"] = {
        "deposit": used["deposit"], "futures": used["future"], "ois": used["ois"]}
    snap.provenance["max_reprice_error_bp"] = float(check["error_bp"].abs().max())
    with open("sofr_provenance.json", "w") as f:
        json.dump(snap.provenance, f, indent=2)
    print("\nSaved: sofr_nodes.csv, sofr_short_end.csv, sofr_zero_curve.csv, sofr_provenance.json")


if __name__ == "__main__":
    main()
