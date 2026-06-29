# Rating-Specific Corporate Discount Curves on a SOFR Base

*Layering market credit spreads across the full rating ladder (AAA → CCC,
investment-grade and high-yield) on top of the bootstrapped SOFR risk-free curve
to produce corporate discount curves and deal-matched loan rates — free
end-of-day data, no terminal.*

---

## Abstract

This module turns the SOFR risk-free curve (see [`../SOFR`](../SOFR)) into
**rating-specific corporate discount curves** for the full ladder — **AAA, AA,
A, BBB** (investment grade) and **BB, B, CCC** (high yield). The construction is
additive:

```
corporate curve(rating)  =  SOFR curve  +  spread(rating, tenor)
spread(rating, T)        =  OAS_level(rating) × IG_shape(T)  +  basis(T)
```

- **`OAS_level(rating)`** — the market credit spread per rating, from ICE BofA
  option-adjusted spreads (FRED).
- **`IG_shape(T)`** — the credit term-structure *slope*, taken from
  investment-grade OAS maturity buckets, so the spread is **sloped, not flat**.
- **`basis(T)`** — the **Treasury-vs-SOFR basis**, which restates the spread
  from "over Treasuries" (how OAS is quoted) to "over SOFR" (our discounting
  base).

Every output is quoted as a **spread over SOFR**, and the discount factor is the
invariant. The result is a per-rating discount curve and, via the SOFR
convention converter, a directly-quotable loan rate for any tenor and
day-count/accrual convention. All inputs come from free public feeds.

---

## 1. Why build corporate curves?

The SOFR curve answers "what is the *risk-free* term cost of money." Pricing a
**fixed-rate term loan** (the Sky use case — lending USDS to a borrower at a
fixed rate, funded against the floating SSR ≈ SOFR) needs more: the lender must
be compensated for **credit risk** on top of the risk-free rate.

```
loan rate  =  SOFR (risk-free term cost)  +  credit spread  +  margin / buffers
```

These curves supply the **credit spread** layer, anchored to where rated credit
actually trades in public markets. The investment-grade rungs (AAA–BBB) are a
**floor / reference**; for an unrated crypto-fund borrower the relevant zone is
**high yield (BB/B/CCC)**, which is much wider. In all cases the curves are a
market-anchored *reference scaffold*, not the exact spread for a specific deal —
that comes from underwriting and collateral. They bound and sanity-check it.

### Spread, not bootstrap

Unlike the SOFR curve (bootstrapped from instruments), the corporate curves are
built by **layering a spread term structure on the SOFR base**. The SOFR
discount factors are held fixed; the credit spread shifts the zero rate. So
every number here inherits a fully-validated risk-free curve and adds a
transparent, separable credit component.

---

## 2. Data sources

All credit and Treasury data come from **FRED** (free API; key in
`CORPORATE/.env`, gitignored). The SOFR base inherits its own feeds (NY Fed,
Yahoo, Pensford — see the SOFR README).

| Component | Series | Source |
|---|---|---|
| IG rating OAS (AAA/AA/A/BBB) | `BAMLC0A1CAAA`, `BAMLC0A2CAA`, `BAMLC0A3CA`, `BAMLC0A4CBBB` | FRED (ICE BofA, "C" series) |
| HY rating OAS (BB/B/CCC) | `BAMLH0A1HYBB`, `BAMLH0A2HYB`, `BAMLH0A3HYC` | FRED (ICE BofA, "H" series) |
| IG maturity-bucket OAS (shape) | `BAMLC1A0C13Y` … `BAMLC8A0C15PY` + master `BAMLC0A0CM` | FRED (ICE BofA) |
| Treasury CMT par yields (basis) | `DGS1MO` … `DGS30` | FRED (US Treasury) |

### Access note

The FRED **graph** host (`fred.stlouisfed.org/graph/fredgraph.csv`) is
unreachable from some environments, but the **API** host
(`api.stlouisfed.org`) works with a free key. The module reads the key from
`FRED_API_KEY` (env var or `.env`) and **falls back to manual flat spreads** if
FRED is unreachable — decoupling the modelling from the feed, exactly as the
SOFR module decouples its build from its data.

---

## 3. Methodology

**The core problem:** FRED gives only a **single blended spread per rating**
(e.g. BBB ≈ 95 bp), averaged across all maturities — it has no term structure.
So the tenor dimension is *manufactured* from three ingredients (§3.1–3.3) and
combined (§3.4).

### 3.1 Rating level

Each rating's ICE BofA OAS is one blended number (over Treasuries). Example
levels (as of 2026-06-26):

| AAA | AA | A | BBB | BB | B | CCC |
|---|---|---|---|---|---|---|
| 38 | 52 | 63 | 95 | 167 | 297 | 968 bp |

IG ratings use the ICE BofA "C" series; HY ratings (BB/B/CCC) the "H" series.
This sets *where each rating sits*, but carries no slope.

### 3.2 Maturity shape — the slope

A blended number is not a term structure. FRED's IG-corporate OAS **maturity
buckets** describe the slope. Dividing each bucket by the IG master OAS gives a
dimensionless **shape factor** by tenor:

| Bucket (rep. tenor) | OAS | ÷ master (≈0.75) = factor |
|---|---|---|
| 1-3Y (2Y) | 0.47% | 0.63 |
| 3-5Y (4Y) | 0.64% | 0.85 |
| 5-7Y (6Y) | 0.76% | 1.01 |
| 7-10Y (8.5Y) | 0.91% | 1.21 |
| 15Y+ (20Y) | 0.92% | 1.23 |

The factor is interpolated across tenors and **flat-extrapolated** below ~2Y
(no bucket exists there) and beyond 20Y. Then
`credit(rating, T) = OAS_level(rating) × factor(T)`.

- **Assumption:** all ratings share the *same* shape, scaled to their level
  (multiplicative separability). The full rating × maturity grid is not freely
  available, so the IG slope is borrowed for every rating — including HY, whose
  real slope is flatter/different (see caveats). The flat short-end correctly
  pulls sub-2Y spreads *below* the blended level (short credit trades tight).

### 3.3 Treasury-vs-SOFR basis

OAS is quoted over **Treasuries**, but we discount on **SOFR**. To express the
spread over SOFR we add the basis:

```
basis(T) = Treasury_CMT(T) − SOFR(T)     ⇒     corporate curve ≈ Treasury + OAS
```

Both legs are put on a **like-for-like bond-equivalent basis** (SOFR restated to
Actual/Actual, semiannual via the convention converter) so the basis is the true
economic gap, not a convention artefact. It is **negative at the front**
(Treasuries trade *rich* — the safe-asset convenience premium; ≈ −10 to −20 bp
near 1Y) and **positive at the long end** (Treasuries *cheap* vs swaps; ≈ +40 to
+75 bp at 30Y). This is the well-documented Treasury-OIS term structure.

### 3.4 Putting it together — worked example

```
spread_over_SOFR(rating, T)  =  level(rating) × shape(T)  +  basis(T)
```

**BBB at 6M:** level 95 × shape(0.63, flat-extrapolated) ≈ 60 bp credit, + basis
(≈ +5 bp) ≈ **65 bp**.
**BBB at 10Y:** level 95 × shape(1.21) ≈ 115 bp credit, + basis (≈ +42 bp) ≈
**157 bp**.

**What is real vs. assumed:**
- *Real, per rating* — the **level** (one number per rating).
- *Real, per tenor* — the **basis** (Treasury vs SOFR at each maturity).
- *Borrowed / assumed* — the **slope** (the IG shape, applied uniformly to all
  ratings; flat below 2Y).

So rating-to-rating differences are genuine (levels), the front-to-long slope is
the IG shape applied uniformly, and the Treasury→SOFR conversion is genuine per
tenor. No per-rating credit *curve* was ever observed.

### 3.5 Curve construction

The per-rating spread is evaluated at node tenors (1M … 30Y) and layered on the
SOFR handle with QuantLib's `SpreadedLinearZeroInterpolatedTermStructure`,
giving a genuine `YieldTermStructure` that interoperates with the SOFR
convention converter. Loan rates are then produced as **par coupons** in the
deal's day-count/accrual convention (reusing `../SOFR/rate_converter.py`).

### 3.6 The 1Y "dip" — read this before trusting a number

The merged spread can *dip* near 1Y. This is **entirely the basis term**, not
credit: the SOFR curve is high at 1Y (near-term hikes priced) while 1Y
Treasuries are rich, so the basis bottoms out and drags the merged spread down.
It is **arithmetically correct** for "a corporate bond's pickup over SOFR," but
**misleading for loan pricing** — credit risk did not fall at 1Y, only the
risk-free benchmark moved. The basis is therefore plotted (and can be reported)
as a **separate component**: charge credit over SOFR directly; treat the basis
as an optional, explicit discounting choice. (See §6 and §7.)

---

## 4. Validation / sanity

- **Inherited:** the SOFR base reprices all its inputs within ~0.18 bp.
- **Credit ladder monotone:** AAA < AA < A < BBB < BB < B < CCC at every tenor.
- **Shape sane:** credit component rises with maturity (IG slope), tight at the
  front.
- **Basis sign/shape sane:** negative front, positive long — matches the known
  Treasury-OIS structure. Magnitude carries par-vs-zero / convention noise, so
  trust the *shape*, not the last basis point.
- **Manual fallback** keeps the build running (with flat spreads) if FRED is
  down, rather than failing silently.

---

## 5. Outputs

| File | Contents |
|---|---|
| `corporate_loan_rates.csv` | All-in loan rate per rating (AAA–CCC), par coupon, by tenor |
| `credit_spread_termstructure.csv` | Spread over SOFR (bp) per rating, by tenor |
| `credit_curves.png` | Zero curves (SOFR + all 7 ratings) and the spread decomposition |
| `corp_rate_conversions.csv` | Quotable loan rate, rating × tenor × pay-freq × day-count |
| `corp_rate_conversions.png` | Quotable rates by convention + the rating-independence of the basis |

Run with:

```bash
python3 credit_curves.py     # SOFR base + FRED spreads -> curves, tables, plot
python3 conversions.py       # quotable loan rates in deal conventions + plot
```

The convention conversion reuses `../SOFR/rate_converter.py` directly on the
rating curves — the all-in loan rate is the rating curve's discount factor
restated in the deal's day-count/accrual convention. The convention basis is
~rating-independent (a rate-level effect, not credit), so each rating's matrix is
essentially the SOFR conversion shifted up by the credit spread.

---

## 6. Caveats and known limitations

1. **These are public rated-bond spreads, not a specific borrower's spread.**
   A rated bond universe is a different credit population from an unrated,
   crypto-collateralised borrower. Use as a **reference scaffold / floor** — and
   note the realistic zone for a crypto fund is **high yield (BB/B/CCC)**, not
   the IG rungs.
2. **The IG shape is applied to *all* ratings**, including HY. Real HY credit
   curves are flatter (and can invert for distressed names), so the **HY
   long-end spreads are the roughest approximation** here. Least so at short
   tenors, where the shape is flat anyway.
3. **CCC is a blended, distressed-heavy bucket** (≈ 968 bp). For a *functioning*
   crypto fund, **B or BB is usually the better analog** than CCC.
4. **Merging credit and basis can mislead (the 1Y dip).** Correct for valuing a
   bond's yield over SOFR; wrong for setting a loan's credit spread. Keep them
   separate when pricing (§7).
5. **Short-end shape is flat-extrapolated below ~2Y** — no bucket data exists
   there; the front credit slope is assumed flat.
6. **Basis magnitude carries convention noise** (CMT par yields vs SOFR zeros on
   a steep curve). Shape is reliable; exact bp is not.
7. **Spread added as a continuous zero spread** — a small convention
   simplification vs the bond-equivalent quoting of OAS (sub-bp here).
8. **No issuer-, liquidity-, optionality-, or recovery-level modelling.** A flat
   spread per rating is a market average, not a hazard-rate/survival curve.
9. **Unofficial / delayed / single-source feeds**, inherited from the SOFR base.

---

## 7. Potential improvements

In rough priority order for the loan-pricing use case:

- **Separate credit and basis as two reported components** (recommended) — so
  the credit spread you charge never dips, and the Treasury-SOFR basis is an
  explicit, optional discounting adjustment.
- **Issuer/deal underwriting spread** — the *actual* number for a crypto-fund
  loan, with these curves as a benchmark floor.
- **HY-specific maturity shape** — use HY maturity buckets for BB/B/CCC instead
  of borrowing the IG slope.
- **Per-rating term structure** from a rating × maturity grid (paid) or a
  bond-level (TRACE) / CDS bootstrap, replacing the borrowed shape entirely.
- **Survival / hazard-rate modelling** (recovery + default intensity) instead of
  a flat spread, for longer or riskier deals.
- **Convention-consistent spread addition** (add the spread in its quoted
  compounding rather than continuous).

---

## 8. References

- ICE BofA US Corporate & High Yield Index families — methodology and
  option-adjusted spreads.
- Federal Reserve Bank of St. Louis — FRED (ICE BofA spreads; Treasury CMT yields).
- On the Treasury-OIS / swap-spread term structure and the convenience yield of
  Treasuries — standard fixed-income literature.
- The SOFR base curve: [`../SOFR/README.md`](../SOFR/README.md).

---

*Built with QuantLib on top of the SOFR curve. Credit and Treasury data from
FRED. These curves are a market-anchored reference for research and analysis;
they are not investment advice and are not the spread of any specific borrower.*
