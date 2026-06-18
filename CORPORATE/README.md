# Rating-Specific Corporate Discount Curves on a SOFR Base

*Layering market credit spreads (AA / A / BBB) on top of the bootstrapped SOFR
risk-free curve to produce corporate discount curves and deal-matched loan
rates — free end-of-day data, no terminal.*

---

## Abstract

This module turns the SOFR risk-free curve (see [`../SOFR`](../SOFR)) into
**rating-specific corporate discount curves**. The construction is additive:

```
corporate curve(rating)  =  SOFR curve  +  spread(rating, tenor)
spread(rating, T)        =  OAS_level(rating) × IG_shape(T)  +  basis(T)
```

- **`OAS_level(rating)`** — the market credit spread for AA / A / BBB, from ICE
  BofA option-adjusted spreads (FRED).
- **`IG_shape(T)`** — the credit term-structure *slope*, taken from
  investment-grade OAS maturity buckets, so the spread is **sloped, not flat**.
- **`basis(T)`** — the **Treasury-vs-SOFR basis**, which restates the spread
  from "over Treasuries" (how OAS is quoted) to "over SOFR" (our discounting
  base).

The output is a per-rating discount curve and, via the SOFR convention
converter, a directly-quotable loan rate for any tenor and day-count/accrual
convention. As with the SOFR curve, the discount factor is the invariant and
every input is sourced from free public feeds.

---

## 1. Why build corporate curves?

The SOFR curve answers "what is the *risk-free* term cost of money." Pricing a
**fixed-rate term loan** (the Sky use case — lending USDS to a borrower at a
fixed rate, funded against the floating SSR ≈ SOFR) needs more: the lender must
be compensated for **credit risk** on top of the risk-free rate.

```
loan rate  =  SOFR (risk-free term cost)  +  credit spread  +  margin / buffers
```

These curves supply the **credit spread** layer, anchored to where
investment-grade credit actually trades in public markets. Critically, they are
a **market-anchored reference scaffold / floor** — not the spread an *unrated
crypto-fund borrower* would pay (that comes from underwriting and collateral,
and is materially wider). The curves answer "what does IG credit cost," which
bounds and sanity-checks the real deal spread.

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
| Rating OAS (AA / A / BBB) | `BAMLC0A2CAA`, `BAMLC0A3CA`, `BAMLC0A4CBBB` | FRED (ICE BofA) |
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

### 3.1 Rating level

Each rating's ICE BofA OAS is a **single blended spread** (averaged across the
rating's maturity distribution): e.g. as of 2026-06-16, AA ≈ 50 bp, A ≈ 63 bp,
BBB ≈ 93 bp — a clean, monotone credit ladder.

### 3.2 Maturity shape — refinement (a)

A single blended number is not a term structure. The IG-corporate OAS *maturity
buckets* (1-3Y ≈ 0.47%, … 15Y+ ≈ 0.92%, master ≈ 0.75%) describe the credit
**slope**. We form a shape factor `IG_shape(T) = bucket_OAS(T) / master_OAS` and
apply it to each rating:

```
spread_credit(rating, T) = OAS_level(rating) × IG_shape(T)
```

- **Assumption:** all ratings share the same spread *shape*, scaled to their own
  level (a multiplicative separability scaffold). The full rating × maturity
  grid is not freely available, so this borrows the IG slope.
- **Short end:** there is no bucket below 1-3Y, so the shape is **flat-
  extrapolated** below ~2Y (and above 20Y). This correctly pulls short-dated
  spreads *below* the blended level — short IG credit trades tight.

### 3.3 Treasury-vs-SOFR basis — refinement (b)

OAS is quoted as a spread over **Treasuries**, but we discount on **SOFR**. To
express the spread over SOFR we add the basis:

```
basis(T) = Treasury_CMT(T) − SOFR(T)     ⇒     corporate curve ≈ Treasury + OAS
```

Both legs are put on a **like-for-like bond-equivalent basis** (SOFR restated to
Actual/Actual, semiannual via the convention converter) so the basis is the true
economic gap, not a convention artefact. The measured basis is **negative at the
front** (Treasuries trade *rich* — the safe-asset convenience/scarcity premium;
≈ −21 bp near 1Y) and **positive at the long end** (Treasuries *cheap* vs swaps —
negative swap spreads; ≈ +75 bp at 30Y). This is the well-documented
Treasury-OIS term structure.

### 3.4 Curve construction

The per-rating spread is evaluated at node tenors (1M … 30Y) and layered on the
SOFR handle with QuantLib's `SpreadedLinearZeroInterpolatedTermStructure`,
giving a genuine `YieldTermStructure` that interoperates with the SOFR
convention converter. Loan rates are then produced as **par coupons** in the
deal's day-count/accrual convention (reusing `../SOFR/rate_converter.py`).

### 3.5 The 1Y "dip" — read this before trusting a number

The merged spread *dips* near 1Y (e.g. AA ≈ 9 bp). This is **entirely the basis
term**, not credit: the SOFR curve is high at 1Y (steep hikes priced) while 1Y
Treasuries are rich, so the basis bottoms at ≈ −21 bp and drags the merged
spread down. It is **arithmetically correct** for "a corporate bond's pickup
over SOFR," but **misleading for loan pricing** — credit risk did not fall at
1Y, only the risk-free benchmark moved. The basis is therefore plotted and (can
be) reported as a **separate component**: charge credit over SOFR directly; treat
the basis as an optional, explicit discounting choice. (See §6 and §7.)

---

## 4. Validation / sanity

- **Inherited:** the SOFR base reprices all its inputs within ~0.18 bp.
- **Credit ladder monotone:** AA < A < BBB at every tenor.
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
| `corporate_loan_rates.csv` | All-in loan rate per rating, par coupon, by tenor |
| `credit_spread_termstructure.csv` | Spread over SOFR (bp) per rating, by tenor |
| `credit_curves.png` | Zero curves (SOFR + AA/A/BBB) and the spread decomposition |
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

1. **These are public IG-bond spreads, not a crypto-fund's spread.** The single
   most important caveat: a rated AA/A/BBB *bond* universe is a different credit
   population from an unrated, crypto-collateralised borrower. Use as a
   **reference scaffold / floor**, never as the deal spread itself.
2. **Merging credit and basis can mislead (the 1Y dip).** Correct for valuing a
   bond's yield over SOFR; wrong for setting a loan's credit spread. Keep them
   separate when pricing (§7).
3. **Shape is total-IG applied to all ratings** (separability assumption). The
   real per-rating slope differs (lower ratings steepen more).
4. **Short-end shape is flat-extrapolated below ~2Y** — no bucket data exists
   there; the front credit slope is assumed flat.
5. **Basis magnitude carries convention noise** (CMT par yields vs SOFR zeros on
   a steep curve). Shape is reliable; exact bp is not.
6. **Spread added as a continuous zero spread** — a small convention
   simplification vs the bond-equivalent quoting of OAS (sub-bp here).
7. **No issuer-, liquidity-, optionality-, or recovery-level modelling.** A flat
   spread per rating is a market average, not a hazard-rate/survival curve.
8. **Unofficial / delayed / single-source feeds**, inherited from the SOFR base.

---

## 7. Potential improvements

In rough priority order for the loan-pricing use case:

- **Separate credit and basis as two reported components** (recommended) — so
  the credit spread you charge never dips, and the Treasury-SOFR basis is an
  explicit, optional discounting adjustment.
- **Issuer/deal underwriting spread** — the *actual* number for a crypto-fund
  loan, with the IG curves as a benchmark floor.
- **Per-rating term structure** from a rating × maturity grid (paid) or a
  bond-level (TRACE) / CDS bootstrap, replacing the borrowed IG shape.
- **Survival / hazard-rate modelling** (recovery + default intensity) instead of
  a flat spread, for longer or riskier deals.
- **Floor the credit spread** at its short-end level if the merged view is kept.
- **Convention-consistent spread addition** (add the spread in its quoted
  compounding rather than continuous).

---

## 8. References

- ICE BofA US Corporate Index family — methodology and option-adjusted spreads.
- Federal Reserve Bank of St. Louis — FRED (ICE BofA spreads; Treasury CMT yields).
- On the Treasury-OIS / swap-spread term structure and the convenience yield of
  Treasuries — standard fixed-income literature.
- The SOFR base curve: [`../SOFR/README.md`](../SOFR/README.md).

---

*Built with QuantLib on top of the SOFR curve. Credit and Treasury data from
FRED. These curves are a market-anchored reference for research and analysis;
they are not investment advice and are not the spread of any specific borrower.*
