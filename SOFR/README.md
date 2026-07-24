# Bootstrapping a SOFR Risk-Free Curve from Free End-of-Day Data

*A reproducible, validated USD SOFR OIS discount curve built with QuantLib from
publicly available market data — no terminal, no paid feed.*

---

## Abstract

This project builds a daily **SOFR (Secured Overnight Financing Rate) risk-free
curve** — the function that maps any future date to a discount factor and an
implied forward rate. The curve is constructed by **bootstrapping**: an
iterative procedure that produces a zero-coupon discount curve which reprices a
set of liquid market instruments *exactly*. We use a three-segment
construction — overnight fixings, SOFR futures, and Overnight Index Swaps (OIS)
— sourced entirely from free, public feeds, and calibrated with
[QuantLib](https://www.quantlib.org/). The result is suitable for discounting,
forward projection, valuation, and risk analysis of SOFR-linked instruments.

This document explains *why* we build such a curve, *how* each segment is
constructed and *why* each modelling choice was made, *how* the result is
validated, and — just as importantly — the **caveats** that bound its accuracy
and the **improvements** that would take it from a robust research curve to a
production trading curve.

---

## 1. Why build a SOFR curve?

A discount curve answers two linked questions for any future date *T*:

1. **Discounting** — what is one dollar paid at *T* worth today? → the discount
   factor `DF(0, T)`.
2. **Forecasting** — what overnight SOFR rate does the market currently imply
   between two dates? → the forward rate.

Since the discontinuation of LIBOR, **SOFR — compounded daily — is the USD
risk-free benchmark.** A single SOFR curve therefore underpins:

- **Pricing** of any SOFR-linked instrument (OIS, futures, floating-rate notes,
  loans): discount the cash flows and project the floating coupons off this one
  curve.
- **Valuation / mark-to-market** of an existing book.
- **Risk** — DV01, bucketed key-rate sensitivities, hedging.
- A **benchmark** against which basis and credit spreads are quoted.

### Bootstrapping vs. fitting

The market does not quote discount factors directly; it quotes the *prices and
rates of instruments*. Bootstrapping inverts those quotes into a discount curve.
Its defining property is **exact repricing**: fed back into the instruments used
to build it, the finished curve reproduces every input quote to numerical
precision. This is distinct from a statistical *fit* (e.g. Nelson–Siegel), which
only approximates the quotes.

The procedure is iterative and ordered by maturity because each instrument's
value depends only on the curve up to its own maturity. Once the short end is
fixed, each successive instrument introduces exactly one new unknown (one new
node), which is solved before moving on — turning a large simultaneous problem
into a sequence of one-dimensional root-finds.

---

## 2. Data sources

A SOFR curve needs three kinds of instrument. The hard part of a *free* build is
that the long-end OIS rates are OTC, and exchange futures data is normally
licensed. Our final source map:

| Curve region | Instrument | Source | Notes |
|---|---|---|---|
| Overnight anchor & history | O/N SOFR + 60d of fixings | **NY Fed** public API | Official, authoritative |
| Front (~0–2.5Y) | SR1 (1M) & SR3 (3M) SOFR futures | **Yahoo / `yfinance`** | Delayed, unofficial last-close |
| Long end (3Y–10Y) | Par SOFR OIS swap rates | **Pensford** live-rates API | Indicative; swaps published only to 10Y |

### What we tried and rejected

- **CME settlement endpoints** (`cmegroup.com/CmeWS/...`) return **HTTP 403** to
  plain requests — the official source is locked behind bot protection and
  licensing. Not usable for a free pipeline.
- **`yfinance` ticker `SOFR=F`** (a commonly suggested symbol) **does not
  exist** (returns no rows). The working symbols are the *per-contract* tickers:
  `SR3{H,M,U,Z}{YY}.CME` (quarterly) and `SR1{month-code}{YY}.CME` (monthly).
  Yahoo serves the full strip per contract, which is what makes the futures
  segment possible for free.
- **Term SOFR (1M/3M/6M)** from Pensford was used in an early prototype to shape
  the short end, then *replaced* by futures (the textbook front-end instrument),
  which pin the sub-1Y points with proper market quotes rather than a
  forward-looking term-rate proxy that carries a small basis.

### Provenance and timing

The feeds are **not a synchronised snapshot**: Pensford is stamped end-of-day
(~6 PM ET), the futures are intraday-delayed, and the NY Fed overnight fixing is
the *prior* business day (today's fixing publishes next morning). Every run
therefore writes a `sofr_provenance.json` recording the run time, each source's
as-of stamp, instrument counts, and the achieved reprice error — an audit trail
that makes the timing assumptions explicit rather than hidden.

---

## 3. Methodology

The curve is a `PiecewiseLogLinearDiscount` term structure:

- **Reference date:** the quote date (zero settlement days on the curve itself;
  individual instruments carry their own settlement).
- **Day count:** Actual/360.
- **Calendar:** `UnitedStates(GovernmentBond)` — the SIFMA / US government
  securities calendar that governs SOFR fixings.
- **Interpolation:** log-linear on discount factors (see §3.5).

Instruments are assembled shortest-to-longest, with each segment handing off
cleanly to the next.

### 3.1 Overnight anchor and historical fixings

We load ~60 calendar days of **official daily SOFR fixings** from the NY Fed and
register them on the QuantLib `Sofr` index. These realised fixings serve two
purposes:

1. They let us value the **in-progress front futures contract**, whose accrual
   period has already partially elapsed (the realised days come from fixings,
   the remaining days from the curve).
2. They provide the official **cross-check** that the overnight level used
   elsewhere is correct.

> **Design note — no standalone overnight deposit.** An earlier version pinned
> day 1 with a 1-day deposit at the published O/N SOFR. Once historical fixings
> and the in-progress front future were added, that deposit became *redundant
> and slightly conflicting*: the deposit (e.g. 3.630%) and the front future
> (e.g. 3.620%) overlap the same days and disagree by ~1bp, and the bootstrap
> reconciled them with a small, artificial **dip** in the front forward. The
> deposit is therefore **off by default** (`USE_ON_DEPOSIT = False`); the
> futures strip owns the front end and the curve starts at the
> market-consistent level. The published overnight rate is retained for the
> sanity cross-check and provenance.

### 3.2 Front end — SOFR futures

The front is built from CME SOFR futures via QuantLib's `SofrFutureRateHelper`,
which knows the contract date conventions and that:

- **SR1 (1-month)** futures settle on the **arithmetic average** of daily SOFR
  over the contract month;
- **SR3 (3-month)** futures settle on the **daily-compounded** SOFR over the
  contract quarter.

**Forward-starting filter.** A futures contract whose accrual has not yet begun
is included directly. The single *in-progress* contract is included only if the
realised portion of its period is fully covered by the loaded fixings;
otherwise it is skipped (it would need a fixing we do not have).

**Clean SR1 → SR3 handoff.** SR1 monthly contracts pin the first several months;
SR3 quarterly contracts are kept **only if they start after the last SR1
contract matures**. This avoids two instruments fighting over the same fixing
period, which would over-determine the system and destabilise the bootstrap.

### 3.3 Long end — OIS swaps

Beyond the last future, par **SOFR OIS swaps** define the curve. A swap exchanges
a fixed rate against daily-compounded SOFR; its par rate is the fixed rate that
makes the swap worth zero today. A root-find adjusts the discount factor at each
swap's maturity until `NPV_fixed = NPV_float`.

**Conventions are set explicitly** (not left to library defaults) to match the
USD SOFR OIS market standard:

- Settlement **T+2**, payment lag **2 business days**, **annual** payments,
  **Modified Following**, Actual/360, daily compounding.

Setting these explicitly removed a silent miscalibration: relying on defaults
reprices the instrument *you defined*, which may not be the instrument the
market quoted. The effect is small (sub-basis-point shifts in long-end nodes)
but real, and — critically — invisible to the reprice check, since that check
validates against your own instrument definition.

**Swap selection.** Only swaps maturing **beyond the last future + 1-month
buffer** are used. With futures covering ~2.5Y, the 1Y and 2Y swaps are dropped
automatically (the futures already pin that range), leaving 3Y–10Y.

### 3.4 Granularity

The construction yields **monthly** nodes through the front year (SR1),
**quarterly** nodes to ~2.5Y (SR3), then the OIS tenors. Sub-1Y points (1M, 2M,
3M, 4M, 6M, 9M, 12M) are therefore **pinned by real market instruments**, not
interpolated — the futures strip brackets every one of them.

### 3.5 Interpolation choice — log-linear on discount factors

We interpolate **log-linearly on discount factors**, which is equivalent to
**piecewise-constant instantaneous forwards**. Rationale:

- **Robust and arbitrage-free** — discount factors stay positive and monotone;
  forwards never oscillate.
- **No spurious wiggles** between sparse nodes — important given only a handful
  of long-end swap tenors.

The trade-off is that the instantaneous forward curve is a **step function**
(visible as a staircase in the plot). The *zero* and *discount* curves remain
smooth; only the derivative is blocky. A `logcubic` option is available for
smoother forwards at the cost of possible overshoot between sparse nodes.

---

## 4. Validation

Two independent layers guard correctness.

### 4.1 Input sanity checks (before building)

A bootstrap reproduces its inputs faithfully — *including* bad ones. A single
fat-fingered or stale quote would be baked in and still pass a reprice check
("wrong, but green"). Before building, we therefore validate the raw inputs:

- **Hard failures (abort):** futures price outside [80, 100]; any rate outside
  (0%, 20%).
- **Soft warnings:** a flat/duplicated strip (signals a stale pull); an
  implausible >150bp month-to-month jump; Pensford's overnight vs the NY Fed
  official fixing diverging by more than 10bp.

### 4.2 Reprice check (after building)

For **every** instrument, we compare the curve-implied quote against the market
quote (`impliedQuote()` vs the input). The full strip reprices within a **0.5bp
tolerance**; in practice the maximum error is ~0.18bp.

> **Why not exactly zero?** OIS swaps reprice to ~0.00bp. SR1/SR3 futures reprice
> to ~0.1–0.2bp because they settle on an *average / compounded* fixing over
> their period, while log-linear discounting assumes a *flat* forward across it —
> a single node per contract cannot reproduce the intra-period averaging
> perfectly. The residual sits *only* on the futures (swaps are exact), which
> confirms it as an interpolation effect rather than a convention error.

### 4.3 Arbitrage-free check (after building)

We assert the curve is arbitrage-free: log-linear-on-discount-factors is
arbitrage-free **iff** the discount factors are strictly decreasing (⟺
non-negative instantaneous forwards). The build checks both the node discount
factors and a dense grid of instantaneous forwards, and fails loudly otherwise.

---

## 5. Outputs

Each run produces:

| File | Contents |
|---|---|
| `sofr_nodes.csv` | Bootstrapped node dates and discount factors |
| `sofr_short_end.csv` | Sub-1Y points (1M–12M): zero, forward, DF |
| `sofr_zero_curve.csv` | 1Y–10Y zero rates, forwards, discount factors |
| `sofr_provenance.json` | Run metadata, source timestamps, reprice error |
| `sofr_curve.png` | Zero & instantaneous-forward plot (full + short-end zoom) |
| `rate_conversions_level1.csv` / `_level2.csv` | Equivalent rates / par coupons across conventions, all tenors |
| `sofr_rate_conversions.png` | Convention-basis plot (fan of dialects + basis vs tenor) |

Run with:

```bash
python3 sofr_pipeline.py      # fetch -> sanity-check -> build -> validate -> export
python3 plot_curve.py         # render the curve
python3 rate_converter.py     # convention conversion matrices (CSV)
python3 plot_conversions.py   # render the convention-basis plot
```

---

## 6. Caveats and known limitations

These bound the curve's accuracy. None makes it unusable for research and
analysis, but they matter before anyone *trades* off it.

1. **Futures convexity adjustment is off (`CONVEXITY = 0`).** Daily-margined
   futures carry a convexity bias: the futures-implied rate sits *above* the
   true forward rate. Ignoring it makes front-end forwards slightly too high and
   discount factors slightly too low — a known, one-directional error growing
   with maturity² × rate-volatility (sub-bp early, a few bp by ~2.5Y).
2. **Data is unofficial, indicative, and unsynchronised.** Yahoo futures are
   delayed scraped last-trades (not official settlements, no bid/ask); Pensford
   swaps are indicative advisory quotes (not executable mids); the three feeds
   are observed at different times. Good enough to understand the market; not a
   single crisp institutional snapshot.
3. **Sparse long-end nodes → blocky forwards.** With only 3/5/7/10Y swaps
   under log-linear interpolation, the instantaneous forward makes rectangular
   steps between nodes. Zero rates and discount factors are unaffected; only
   forward-rate analytics in that region are.
4. **No turn-of-year / quarter-end jumps.** SOFR reliably spikes at period-ends
   (balance-sheet effects). The smooth curve averages these away, mispricing
   instruments whose accrual spans a turn.
5. **Curve capped at 10Y.** Pensford publishes SOFR swaps only to 10Y, so the
   curve is not built beyond that point (rather than extrapolated). Fine for the
   short-tenor term-deal use case; a longer source would be needed otherwise.
6. **Feed-change / availability risk.** Data comes from single free providers
   (Pensford moved its endpoint in 2026, which this build now targets). A manual
   last-known fallback keeps the build running if the swap feed is unreachable,
   rather than failing hard.
7. **Convention-matching risk.** OIS conventions are set to the market standard,
   but if they differ from the exact conventions underlying the *quoted* rates,
   a small residual miscalibration remains that the reprice check cannot detect.

---

## 7. Potential improvements

In rough priority order:

- **Convexity adjustment** for SR3 futures (analytic or Hull-White-based) to
  remove the known front-end bias.
- **Turn-of-year jumps** — add dated jumps at year-/quarter-ends (QuantLib
  supports this directly via additional discount factors).
- **DV01 / key-rate risk** — bump each instrument and reprice to produce
  bucketed sensitivities (the most common downstream need).
- **Smoother long end** — a monotone-convex or log-cubic interpolator, and/or
  additional swap tenors (12/20/25/40/50Y) from a richer source.
- **Robustness** — caching dated raw snapshots, retries, and fallback data
  sources; staleness gating on the quote date.
- **Official / synchronised data** — a paid feed (Bloomberg, Refinitiv) for an
  executable, single-timestamp snapshot if the curve is ever used for trading.

---

## 8. References

- Ametrano, F. & Bianchetti, M., *Everything You Always Wanted to Know About
  Multiple Interest Rate Curve Bootstrapping but Were Afraid to Ask* (2013).
- Ballabio, L., *Implementing QuantLib*; QuantLib cookbook, “Curve bootstrapping”.
- QuantLib documentation — interest-rate term structures and piecewise yield
  curves.
- Federal Reserve Bank of New York — SOFR data and methodology.

---

*Built with QuantLib. Data from the NY Fed, CME (via Yahoo Finance), and
Pensford. This curve is for research and analysis; it is not investment advice
and is not sourced from executable, real-time market data.*
