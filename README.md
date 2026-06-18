# Curve Bootstrapping — SOFR Risk-Free & Corporate Credit Curves

*A free, end-of-day pipeline that builds a USD SOFR risk-free curve and
rating-specific corporate discount curves, then expresses any point as a
deal-matched rate — built with QuantLib, no terminal or paid feed required.*

---

## What this is

This project produces the curves needed to **price fixed-rate term deals for the
Sky ecosystem**. USDS's deposit yield (the SSR) is anchored to SOFR, so a
bootstrapped SOFR curve gives the term structure of the risk-free rate; layering
market credit spreads on top gives the all-in cost of corporate credit. The
intended use is pricing a **fixed-rate loan** (risk-free base + credit spread +
margin), with the curves supplying the first two, market-anchored components.

It is organised in two stages, each a self-contained module with its own
methodology write-up:

```
                    ┌─────────────────────────────────────────────┐
   NY Fed  ──┐      │  SOFR/  — risk-free curve                    │
   Yahoo   ──┼────► │  bootstrap → discount factors → convention   │
   Pensford──┘      │  conversion (day-count / accrual)            │
                    └───────────────────┬─────────────────────────┘
                                        │  SOFR discount factors
                                        ▼
   FRED  ──────────►┌─────────────────────────────────────────────┐
   (ICE BofA OAS,   │  CORPORATE/  — credit curves                 │
    Treasury CMT)   │  SOFR + spread(rating, tenor) → AA/A/BBB     │
                    │  discount curves → quotable loan rates       │
                    └─────────────────────────────────────────────┘
```

---

## Repository structure

```
CURVE_BOOTSTRAPPING/
├── README.md                    ← this overview
├── .gitignore                   secrets (.env) + Python cruft
│
├── SOFR/                        risk-free curve
│   ├── README.md                methodology article (the SOFR curve)
│   ├── sofr_pipeline.py         fetch → sanity-check → bootstrap → validate → export
│   ├── rate_converter.py        restate a curve point across day-count/accrual conventions
│   ├── plot_curve.py            zero & forward curve
│   ├── plot_conversions.py      convention-basis plot
│   └── *.csv / *.png / *.json   outputs
│
└── CORPORATE/                   credit curves on the SOFR base
    ├── README.md                methodology article (corporate curves)
    ├── .env                     FRED API key (gitignored)
    ├── credit_curves.py         SOFR + rating spreads → AA/A/BBB discount curves
    ├── conversions.py           quotable loan rates in deal conventions
    └── *.csv / *.png            outputs
```

---

## The two stages

### 1. `SOFR/` — the risk-free curve  ·  [details →](SOFR/README.md)

A three-segment **bootstrap** that reprices every input instrument exactly:

- **Overnight + history** (NY Fed fixings) → anchors the front and lets the
  in-progress futures contract be valued.
- **Front end** (CME SR1/SR3 futures via Yahoo) → pins every sub-1Y point with
  real market quotes.
- **Long end** (Pensford SOFR OIS swaps) → 3Y–30Y.

Interpolation is log-linear on discount factors (robust, non-oscillating). The
curve reprices all inputs within ~0.18 bp. A companion **convention converter**
restates any point under different day-count/compounding conventions (the same
discount factor, different "dialect").

### 2. `CORPORATE/` — credit curves  ·  [details →](CORPORATE/README.md)

Layers a market credit spread on the SOFR base:

```
corporate curve(rating) = SOFR + OAS_level(rating) × IG_shape(tenor) + Treasury–SOFR basis
```

- **Rating level** — ICE BofA AA/A/BBB option-adjusted spreads (FRED).
- **Maturity shape** — IG-corporate OAS buckets give the credit term-structure slope.
- **Treasury–SOFR basis** — restates the spread from "over Treasuries" (how OAS
  is quoted) to "over SOFR" (the discounting base).

Output is AA/A/BBB discount curves and quotable loan rates, in any deal
convention (reusing the SOFR converter).

---

## Data sources (all free)

| Data | Source | Used by |
|---|---|---|
| Overnight SOFR + 60d fixings | NY Fed API | SOFR |
| SR1/SR3 SOFR futures | Yahoo (`yfinance`) | SOFR |
| SOFR OIS swap rates | Pensford `quotes.xml` | SOFR |
| Corporate OAS by rating + IG maturity buckets | FRED (ICE BofA) | CORPORATE |
| Treasury CMT par yields | FRED | CORPORATE |

CME's official endpoints are blocked (403), so futures come from Yahoo. FRED's
`fredgraph.csv` host is unreachable from some networks, but the **API** host
works with a free key — set `FRED_API_KEY` (env var or `CORPORATE/.env`). Both
modules **fall back gracefully** (and the corporate one to manual spreads) rather
than failing silently.

---

## Setup & quickstart

Dependencies: `QuantLib`, `pandas`, `numpy`, `requests`, `yfinance`,
`matplotlib` (Python 3.11). A FRED API key is needed only for the corporate
stage.

```bash
# 1. risk-free curve
cd SOFR
python3 sofr_pipeline.py        # build + validate + export the SOFR curve
python3 plot_curve.py           # plot it
python3 rate_converter.py       # convention conversion matrices
python3 plot_conversions.py     # convention-basis plot

# 2. corporate credit curves (needs FRED_API_KEY)
cd ../CORPORATE
python3 credit_curves.py        # AA/A/BBB curves + spread decomposition plot
python3 conversions.py          # quotable loan rates in deal conventions + plot
```

---

## Top-level caveats

The detailed caveats live in each module's README; the three that matter most
across the whole project:

1. **Research / analysis, not trading.** All feeds are free, **delayed,
   indicative, and not a synchronised snapshot**. Good for understanding and
   pricing exploration; not an executable, real-time mark.
2. **The corporate spreads are a reference scaffold, not a borrower's spread.**
   They are public investment-grade *bond* spreads — a market-anchored floor for
   "what IG credit costs," **not** the spread an unrated crypto-fund borrower
   would pay (which is wider and comes from underwriting + collateral).
3. **Several refinements are deliberately deferred** (futures convexity,
   turn-of-year jumps, separating credit vs Treasury-SOFR basis for loan
   pricing). Each is documented in the relevant README's "improvements" section.

---

## Where to read more

- **SOFR curve methodology** → [`SOFR/README.md`](SOFR/README.md)
- **Corporate credit methodology** → [`CORPORATE/README.md`](CORPORATE/README.md)
