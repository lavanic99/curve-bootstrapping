# Model Proposal — SOFR Risk-Free & Corporate Credit Curve Framework

| | |
|---|---|
| **Prepared for** | Management Board |
| **Purpose** | Approval of a curve-construction model to support fixed-rate term-deal pricing |
| **Model name** | Curve-Bootstrapping Framework (SOFR + Corporate Credit) |
| **Version / date** | v1.0 — results as at **20 July 2026** |
| **Model owner** | *[Risk / Treasury — to be assigned]* |
| **Classification** | Decision-support / reference model (not a sole basis for execution) |
| **Repository** | `github.com/lavanic99/curve-bootstrapping` |

---

## 1. Executive summary

We propose adoption of a transparent, reproducible framework that constructs, **daily and from free public data**, two linked term structures:

1. a **USD SOFR risk-free curve** (the risk-free term cost of money), and
2. **rating-based corporate credit-spread curves** (AAA → CCC) expressed as spreads **over SOFR**,

and converts any point into a **deal-matched fixed rate** in the borrower's day-count/accrual convention.

**Business rationale.** USDS's savings rate (SSR) is anchored to SOFR. To price a **fixed-rate USDS term loan**, the desk needs (i) the risk-free term cost over the deal's maturity and (ii) a market-anchored view of the credit premium. This framework supplies both, plus the convention conversion required to quote a contractual rate.

**Status.** Implemented and validated. The SOFR curve reprices every calibrating instrument to within **0.11 bp** (2 July 2026 run; tolerance 0.5 bp). The framework runs end-to-end on free feeds with documented fallbacks.

**Recommendation.** Approve for use as a **pricing-support and reference tool** — providing the risk-free base and a credit-spread *benchmark* — subject to the usage restrictions (§3, §9) and governance (§10). The framework’s credit output is a **market reference floor**, not an approved deal spread; the deal spread remains an underwriting decision.

**Single most important caveat (see §9).** The credit spreads are derived from **public rated-bond indices**. They are a reference scaffold. They are **not** the spread a specific, unrated, crypto-collateralised borrower should be charged — for such a borrower the relevant reference band is **high yield (BB/B/CCC)**, and the executable spread must come from credit underwriting.

---

## 2. Purpose and business context

- **Sky / USDS / SSR.** USDS holders earn the SSR, a variable rate governance-anchored to SOFR. Offering **fixed-rate, fixed-maturity** products (loans) requires a term structure of rates rather than a single overnight rate.
- **Direction of the exposure.** In the reference use case the protocol **lends fixed and funds floating** (SSR ≈ SOFR). It is therefore **short interest-rate risk** (rising rates compress the margin). Correct term-structure pricing is the first control on that exposure.
- **What the model produces.**
  1. SOFR discount factors / zero rates for any date to 10Y.
  2. Corporate credit spreads over SOFR by rating and tenor.
  3. All-in fixed loan rate in any market day-count/accrual convention.

---

## 3. Scope and intended use

**In scope.** Estimation of (a) the SOFR risk-free term cost, (b) a market-anchored credit-spread *reference* by rating and tenor, and (c) convention-consistent restatement of a rate for a term sheet.

**Explicitly out of scope / not represented.**
- It is **not** an approval of, or substitute for, a **counterparty-specific credit spread** (underwriting decision).
- It is **not** a default-probability, recovery, or expected-loss model.
- It is **not** a hedging, execution, or real-time trading system (data is end-of-day, delayed, indicative).
- It does **not** price optionality (prepayment, early withdrawal) or size margin/capital buffers.

---

## 4. Methodology

### 4.1 SOFR risk-free curve — bootstrap

A **three-segment bootstrap** (shortest to longest), with the defining property that the finished curve **reprices every input instrument exactly** (an inversion of market quotes, not a statistical fit):

| Segment | Instrument | Role |
|---|---|---|
| Overnight + realised history | Official daily SOFR fixings (60 days) | Anchor; value the in-progress front contract |
| Front (~0–2.5Y) | CME SR1 (1M) & SR3 (3M) SOFR futures | Pin every sub-1Y point with market quotes |
| Long end (3Y–10Y) | SOFR OIS par swap rates | Term structure to 10Y (public swap data ends at 10Y) |

- **Interpolation:** log-linear on discount factors (equivalently, piecewise-flat instantaneous forwards) — chosen for robustness and no oscillation across sparse long-end nodes.
- **Segment handoff:** quarterly futures are used only beyond the last monthly future; swaps only beyond the last future — no instrument is double-counted.

### 4.2 Corporate credit-spread overlay

The credit curves are built by **layering a spread on the SOFR base** (discount factors held fixed). Because the market publishes only one **blended** spread per rating (no term structure), the tenor dimension is constructed from three components:

```
spread_over_SOFR(rating, T) = OAS_level(rating) × IG_shape(T) + basis(T)
```

| Component | Source | Nature |
|---|---|---|
| `OAS_level(rating)` | ICE BofA option-adjusted spread per rating | **Observed**, per rating (maturity-blended) |
| `IG_shape(T)` | IG-corporate OAS maturity buckets ÷ IG master | **Assumed common slope** (see §8) |
| `basis(T)` | Treasury(CMT) − SOFR, like-for-like | **Observed**, per tenor |

This restates spreads from "over Treasuries" (how OAS is quoted) to "over SOFR" (the discounting base).

### 4.3 Rate-convention conversion

The discount factor is convention-invariant; a "rate" is one representation of it. Given a curve, the framework computes the **par coupon** for a deal on its actual schedule under any day-count (Act/360, Act/365F, Act/Act ISDA/ICMA/AFB, 30/360) and payment frequency — i.e. the contractually quotable rate.

---

## 5. Data sources and provenance

All inputs are free and public. Each run writes a provenance record (timestamps, source, instrument counts, achieved reprice error).

| Data | Source | Frequency |
|---|---|---|
| Overnight SOFR + 60-day history | NY Fed API (official) | Daily |
| SR1 / SR3 SOFR futures | CME via Yahoo Finance | Daily (delayed) |
| SOFR OIS swap rates | Pensford live-rates API (indicative) | Daily EOD |
| Corporate OAS by rating + IG maturity buckets | FRED (ICE BofA) | Daily |
| Treasury CMT par yields | FRED (US Treasury) | Daily |

**Resilience.** Input **sanity checks** run before every build (hard-fail on out-of-range prices/rates; warn on stale/implausible moves). If a credit feed is unreachable the model **falls back to last-known manual spreads** rather than failing silently. Data is EOD/indicative and drawn from multiple providers at slightly different times (see §9).

---

## 6. Model validation

| Control | Result (2 July 2026) |
|---|---|
| SOFR reprice check — curve reproduces every calibrating instrument | **PASS — max error 0.15 bp** (tolerance 0.5 bp) |
| Arbitrage-free — discount factors strictly decreasing (forwards ≥ 0) | **PASS** |
| Overnight anchor vs official NY Fed fixing | **0.00 bp** difference |
| Credit ladder monotonicity (AAA < AA < … < CCC) | **PASS** at every tenor |
| Basis sign/shape vs known Treasury-OIS structure | **PASS** (negative front, positive long) |
| Input sanity gates | Active; no exceptions triggered |

The residual futures reprice error (~0.1 bp) is a known consequence of averaging-vs-flat-forward interpolation and is immaterial.

---

## 7. Results as at 20 July 2026

**7.1 SOFR risk-free curve** (continuous-compounded zero rates). Overnight SOFR = **3.59%**.

| Tenor | 1M | 3M | 6M | 1Y | 2Y | 3Y | 5Y | 7Y | 10Y |
|---|---|---|---|---|---|---|---|---|---|
| Zero | 3.67 | 3.73 | 3.83 | 3.95 | 3.98 | 3.96 | 3.96 | 4.00 | 4.11 |

*Shape:* mildly humped — the belly (~3–5Y, 3.96%) sits close to the 1–2Y area, reflecting expectations of modest medium-term easing, before rising to ~4.11% at 10Y. The curve is pinned by market swaps only to 10Y (see §9).

**7.2 Corporate credit spreads over SOFR** (basis points):

| Tenor | AAA | AA | A | BBB | BB | B | CCC |
|---|---|---|---|---|---|---|---|
| 6M | 29 | 38 | 45 | 64 | 105 | 184 | 608 |
| 1Y | 22 | 31 | 37 | 57 | 98 | 177 | 601 |
| 2Y | 35 | 45 | 51 | 70 | 111 | 190 | 615 |
| 5Y | 61 | 75 | 84 | 113 | 174 | 293 | 930 |
| 10Y | 83 | 101 | 113 | 150 | 229 | 383 | 1202 |

**7.3 All-in fixed loan rate — 6M, par coupon, interest paid monthly, Act/360** (%):

| SOFR | AAA | AA | A | BBB | BB | B | CCC |
|---|---|---|---|---|---|---|---|
| 3.83 | 4.12 | 4.22 | 4.28 | 4.47 | 4.88 | 5.67 | 9.92 |

*Interpretation:* investment-grade references land at 4.2–4.5%; the high-yield band (the relevant zone for an unrated crypto-fund borrower) at ~4.9% (BB) to ~5.8% (B), with CCC (~9.9%) reflecting a distressed-heavy bucket.

---

## 8. Key assumptions

1. **Credit term-structure separability.** All ratings are assumed to share a **single slope**, borrowed from the investment-grade maturity buckets and scaled to each rating's observed level. No per-rating credit *curve* is independently observed.
2. **Flat short-end credit slope.** Below ~2Y (no market bucket exists), the slope is held flat.
3. **SOFR as the risk-free discounting base**, with the Treasury-vs-SOFR basis added to translate OAS onto it.
4. **Log-linear interpolation** (piecewise-flat forwards).
5. **End-of-day, indicative pricing** is representative for term-deal reference purposes.

---

## 9. Limitations and model risk

| # | Limitation | Materiality | Mitigant |
|---|---|---|---|
| 1 | **Credit spreads are public rated-bond references, not a specific borrower's spread.** | **High** for deal pricing | Use as reference floor only; deal spread set by underwriting (§3). |
| 2 | **IG slope applied to high-yield** ratings (real HY curves are flatter). | Medium at long tenors; low at short | Documented; short-tenor deals least affected. HY-specific slope is a proposed enhancement. |
| 3 | **CCC is a distressed-heavy blended bucket** (~9.9% all-in). | Medium | Use B/BB as the analog for a functioning fund. |
| 4 | **Treasury-SOFR basis can make the merged short-tenor spread dip** (a benchmark effect, not credit). | Medium | Basis reported as a separate component; do not let it reduce the charged credit spread. |
| 5 | **Data is free, delayed, indicative, multi-source, not synchronised.** | Medium | EOD reference use only; provenance logged; sanity gates. |
| 6 | **Deferred refinements:** futures convexity, year-end jumps, per-rating HY curves, optionality. | Low–Medium | Documented roadmap; immaterial for short IG/reference use. |
| 7 | **Single-provider feeds** (futures, swaps) — availability and change risk (the swap provider moved its endpoint in 2026). | Low–Medium | Manual/last-known fallback so a feed change fails soft; loud failure on bad data. |
| 8 | **Curve capped at 10Y** — the public swap source publishes no tenors beyond 10Y, so the model produces no rates past that point. | Low for term-deal use (loans are short) | Documented; a longer source could be added if needed. |

**Overall model-risk rating: Moderate**, appropriate for a **decision-support / reference** classification, **not** for sole-basis execution.

---

## 10. Controls and governance

- **Ownership & review.** Model owner (Risk/Treasury) to own; independent review recommended before any use beyond reference. Periodic revalidation (suggested: quarterly, and on any methodology change).
- **Change control.** Versioned in git; methodology decisions documented in per-module READMEs; every run emits a provenance file.
- **Usage policy.** Outputs are **reference/pricing-support**. Any executed term deal must (i) take the credit spread from underwriting, not the model, and (ii) reflect margin, buffers, and the interest-rate exposure of a fixed-lend/floating-fund book.
- **Access to secrets.** Data API keys are held outside the repository; none are published.

---

## 11. Recommendation and decision requested

We request the Board to:

1. **Approve** the framework as a **decision-support / reference model** for fixed-rate term-deal pricing, at the stated classification and usage restrictions.
2. **Note** the limitations in §9, in particular that credit output is a market reference, not an approved counterparty spread.
3. **Endorse** the governance in §10 (owner assignment, independent review before any escalation of use, quarterly revalidation).
4. **Note the roadmap** (§9 #6) for enhancements should usage expand toward execution.

---

## Appendix A — Reproducibility

The framework is fully reproducible from public data:

```bash
# SOFR risk-free curve
cd SOFR && python3 sofr_pipeline.py && python3 plot_curve.py
# Corporate credit curves (requires a free FRED API key)
cd ../CORPORATE && python3 credit_curves.py && python3 conversions.py
```

Detailed methodology: `SOFR/README.md`, `CORPORATE/README.md`. Every run writes `sofr_provenance.json` (SOFR inputs, timestamps, reprice error).

## Appendix B — Definitions

- **SOFR** — Secured Overnight Financing Rate; USD risk-free benchmark.
- **OAS** — Option-Adjusted Spread; a bond's spread over the Treasury curve.
- **Bootstrap** — iterative curve construction that reprices calibrating instruments exactly.
- **Discount factor** — present value today of one unit paid on a future date (convention-invariant).
- **Par coupon** — the fixed rate that prices a deal at par on its own schedule/convention.

---

*This document describes a model for internal research and pricing-support. It is not investment advice and does not constitute an executable quote for any counterparty.*
