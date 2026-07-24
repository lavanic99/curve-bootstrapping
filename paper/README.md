# Paper — *A Bootstrapped SOFR Curve with Rating-Based Corporate Spreads*

A working note documenting the curve-bootstrapping methodology in this
repository, built from free end-of-day data. The formatted deliverable is
[`Model_Documentation.docx`](Model_Documentation.docx) (import into Word or
Google Docs). This folder is self-contained and reproducible.

**Authors.** Nicolò Lavaroni (Analyst, BA Labs); Tommaso Donda (Analyst, BA
Labs); Jan Delegos, CFA (Head of Risk, Sky Frontier Foundation).

## Contents

| File | Role |
|---|---|
| `Model_Documentation.docx` | The paper (generated) |
| `refresh.py` | Rebuilds `doc_data.json` + the two figures from the live model in `../SOFR` and `../CORPORATE` |
| `build_doc.js` | Renders the `.docx` from `doc_data.json` + the figures |
| `doc_data.json`, `chart_*.png` | Generated data and figures |

## Regenerate

```bash
python3 refresh.py        # pull live data -> doc_data.json + figures
npm install docx          # one-time (Node dependency for the renderer)
node build_doc.js         # render Model_Documentation.docx
```

Figures and tables reflect the calibration date at the top of the paper; the
underlying model is documented in [`../SOFR`](../SOFR) and [`../CORPORATE`](../CORPORATE).

## Known limitations (summary)

The paper's Section 5 states these in full; in brief:

**Modelling / data**
- Curve capped at **10 years** — the public swap source publishes no longer tenors (no extrapolation).
- **Log-linear** interpolation → piecewise-flat forwards; a small futures reprice residual (≤0.15 bp, mean 0.02 bp). Verified to sit on the futures only — the swaps reprice exactly — so it is an interpolation effect, not a convention error; log-cubic does not converge here.
- **Futures convexity not corrected** (documented approximation: sub-bp early, a few bp by ~2.5Y; correcting it needs a volatility input not available for free).
- **Turn-of-year / quarter-end** jumps not modelled.
- Data is **free, delayed, indicative, multi-source, not synchronised**.
- Credit overlay borrows a **single (investment-grade) maturity shape** for all ratings; index-level, not a specific borrower's spread.

**Handled correctly (not limitations, noted for completeness)**
- Curve is checked **arbitrage-free** each build (discount factors strictly decreasing ⇒ non-negative forwards).
- Treasury–SOFR basis is computed **zero-against-zero** (Treasury zeros bootstrapped from CMT par yields), and the credit spread is added in **consistent semiannual compounding** — removing the par-vs-zero and continuous-vs-semiannual mismatches.

**Validation / reproducibility**
- Repricing checks **internal consistency only**; instrument conventions are set to the SOFR-OIS market standard (Act/360, T+2, 2-business-day payment lag, daily-compounded float) but **not independently reconciled** against a second source.
- **No independent cross-validation** against a second engine or analytic benchmark yet.
- Runs are **not bit-reproducible** — inputs are fetched live and the raw quotes are not persisted.
- **Single free providers**; a last-known fallback covers an outage but degrades quality.

The remaining validation roadmap (frozen-fixture test suite + golden-master
reprice; input snapshotting; independent cross-check) is noted in the paper as
the natural next step. None changes the methodology; each raises confidence in
the output.
