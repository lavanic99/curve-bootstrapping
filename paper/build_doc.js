// Build the paper (Model_Documentation.docx) from doc_data.json + charts in this dir.
// Requires the `docx` npm package:  npm install docx   (then:  node build_doc.js)
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType,
  Table, TableRow, TableCell, WidthType, BorderStyle, ShadingType, ImageRun, LevelFormat,
} = require("docx");

const DIR = __dirname;
const OUT = path.join(DIR, "Model_Documentation.docx");
const CONTENT_W = 9360;
const D = JSON.parse(fs.readFileSync(path.join(DIR, "doc_data.json"), "utf8"));
const ASOF = D.asof, TEN = D.labels, RAT = ["AAA","AA","A","BBB","BB","B","CCC"];

const HAIR = { style: BorderStyle.SINGLE, size: 2, color: "D9D9D9" };
const CELLB = { top: HAIR, bottom: HAIR, left: HAIR, right: HAIR };
function cell(text, w, { header = false, first = false, ri = 0 } = {}) {
  return new TableCell({ width: { size: w, type: WidthType.DXA }, borders: CELLB,
    margins: { top: 30, bottom: 30, left: 70, right: 70 },
    shading: header ? { type: ShadingType.CLEAR, fill: "1F3864", color: "auto" }
      : (ri % 2 ? { type: ShadingType.CLEAR, fill: "F3F5F8", color: "auto" } : undefined),
    children: [new Paragraph({ alignment: first ? AlignmentType.LEFT : AlignmentType.RIGHT, spacing: { after: 0 },
      children: [new TextRun({ text: String(text), bold: header || first, color: header ? "FFFFFF" : "000000", size: header ? 17 : 16 })] })] });
}
function table(headers, rows, widths) {
  const head = new TableRow({ tableHeader: true, children: headers.map((h, i) => cell(h, widths[i], { header: true, first: i === 0 })) });
  const body = rows.map((r, ri) => new TableRow({ children: r.map((c, i) => cell(c, widths[i], { first: i === 0, ri })) }));
  return new Table({ columnWidths: widths, width: { size: widths.reduce((a, b) => a + b, 0), type: WidthType.DXA }, rows: [head, ...body] });
}
function img(file, w) {
  const data = fs.readFileSync(path.join(DIR, file));
  const ratio = file.includes("allin") ? 600 / 1050 : 510 / 1050;
  return new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 120, after: 60 },
    children: [new ImageRun({ type: "png", data, transformation: { width: w, height: Math.round(w * ratio) } })] });
}
const H1 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_1, spacing: { before: 280, after: 100 }, children: [new TextRun({ text: t, bold: true })] });
const H2 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_2, spacing: { before: 160, after: 60 }, children: [new TextRun({ text: t, bold: true, size: 22 })] });
const P = (t) => new Paragraph({ alignment: AlignmentType.JUSTIFIED, spacing: { after: 120, line: 276 }, children: [new TextRun({ text: t, size: 21 })] });
const CAP = (t) => new Paragraph({ spacing: { after: 160 }, alignment: AlignmentType.CENTER, children: [new TextRun({ text: t, italics: true, size: 17, color: "666666" })] });
const BUL = (t) => new Paragraph({ numbering: { reference: "b", level: 0 }, alignment: AlignmentType.JUSTIFIED, spacing: { after: 60, line: 270 }, children: [new TextRun({ text: t, size: 21 })] });
const CTR = (runs, opts = {}) => new Paragraph({ alignment: AlignmentType.CENTER, spacing: opts.spacing || { after: 40 }, children: runs });
const sup = (t) => new TextRun({ text: t, superScript: true, size: 20 });
const REF = (n, runs) => new Paragraph({ spacing: { after: 80, line: 264 }, indent: { left: 460, hanging: 460 }, children: [new TextRun({ text: `[${n}]  `, size: 19 }), ...runs] });
const txt = (t, o = {}) => new TextRun({ text: t, size: 19, ...o });

const wA = [3400, 3400], wB = [3400, 3400];
const wC = (() => { const t = 940, d = Math.floor((CONTENT_W - t) / 7); return [t, d,d,d,d,d,d,d]; })();
const wD = (() => { const t = 900, d = Math.floor((CONTENT_W - t) / 8); return [t, d,d,d,d,d,d,d,d]; })();
const sofrRows = TEN.map((t, i) => [t, D.sofr[i].toFixed(2) + "%"]);
const oasRows = RAT.map((r) => [r, String(D.oas[r])]);
const spreadRows = TEN.map((t, i) => [t, ...RAT.map((r) => String(D.spread[r][i]))]);
const allinRows = TEN.map((t, i) => [t, D.sofr[i].toFixed(2), ...RAT.map((r) => D.allin[r][i].toFixed(2))]);

const children = [
  CTR([new TextRun({ text: "A Bootstrapped SOFR Curve with Rating-Based Corporate Spreads", bold: true, size: 32 })], { spacing: { after: 60 } }),
  CTR([new TextRun({ text: "A reproducible term-structure model built from free end-of-day data", italics: true, size: 21, color: "444444" })], { spacing: { after: 160 } }),
  CTR([new TextRun({ text: "Nicolò Lavaroni", size: 21 }), sup("1"),
       new TextRun({ text: "      Tommaso Donda", size: 21 }), sup("1"),
       new TextRun({ text: "      Jan Delegos, CFA", size: 21 }), sup("2")], { spacing: { after: 40 } }),
  CTR([sup("1"), new TextRun({ text: " Analyst, BA Labs        ", italics: true, size: 18, color: "555555" }),
       sup("2"), new TextRun({ text: " Head of Risk, Sky Frontier Foundation", italics: true, size: 18, color: "555555" })], { spacing: { after: 40 } }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 }, border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: "1F3864" } },
    children: [new TextRun({ text: `Working note — illustrative calibration as at ${ASOF}`, size: 18, italics: true, color: "555555" })] }),

  new Paragraph({ spacing: { after: 60 }, indent: { left: 540, right: 540 }, children: [new TextRun({ text: "Abstract", bold: true, size: 20 })] }),
  new Paragraph({ alignment: AlignmentType.JUSTIFIED, spacing: { after: 100, line: 264 }, indent: { left: 540, right: 540 },
    children: [new TextRun({ size: 19, text:
      "We document a reproducible procedure for bootstrapping a US dollar risk-free discount curve from free, end-of-day market data, and a transparent overlay that adds credit spreads by rating. The risk-free curve is built from Secured Overnight Financing Rate (SOFR) instruments — overnight fixings, SOFR futures, and overnight-indexed swaps — so that it reprices its calibrating instruments exactly. The credit overlay is constructed from index option-adjusted spreads, an investment-grade maturity shape, and the Treasury–SOFR basis. We set out the construction, report an illustrative calibration, and give particular attention to the model's known limitations — the assumptions, data constraints, and validation gaps a user must weigh before relying on the output." })] }),
  new Paragraph({ spacing: { after: 160 }, indent: { left: 540, right: 540 },
    children: [new TextRun({ text: "Keywords: ", bold: true, size: 18 }),
      new TextRun({ text: "SOFR; yield-curve bootstrapping; discount factors; overnight-indexed swaps; credit spreads; option-adjusted spread; term structure.", size: 18, italics: true })] }),

  H1("1. Introduction and purpose"),
  P("The model produces a term structure of US dollar interest rates in two layers. The first is a risk-free curve derived from the Secured Overnight Financing Rate (SOFR) [6]; the second is a set of credit spreads by rating that sit on top of it. Together they yield a discount curve and a forward-rate view out to ten years. The emphasis of this note is the risk-free bootstrap and its construction from freely available data; the credit overlay is included as a worked illustration of how a spread layer is added, not as a study of any particular borrower."),
  P("The construction is deliberately kept auditable: the risk-free part is pinned to observable market instruments and reprices them exactly, and every modelling assumption is stated rather than buried in a single output number."),

  H1("2. The SOFR risk-free curve"),
  P("The curve is built by bootstrapping — an iterative procedure that, rather than fitting a smooth functional form, solves for the discount factors that reprice a chosen set of market instruments exactly, one maturity at a time from the short end outward [1, 2]. Each instrument adds a single node and is priced using only the nodes already fixed, so the calibration reduces to a sequence of one-dimensional root solves. The construction follows standard single- and multi-curve practice [3] and is implemented with QuantLib [1, 4]."),
  P("Three families of instruments are used, each liquid over its own part of the curve. The published overnight SOFR fixing [6], together with the realised fixings of the current month, anchors the front. One- and three-month SOFR futures cover the range to roughly two and a half years, fixing the expected compounded overnight rate over each contract period. SOFR overnight-indexed swaps carry the term structure from three to ten years through their par rates. The public swap source publishes tenors only to ten years, so the curve is capped there; longer maturities are not produced rather than extrapolated."),
  P("Between nodes the curve interpolates log-linearly on discount factors, which holds the instantaneous forward rate constant across each interval. This keeps forward rates well behaved where instruments are sparse, at the cost of a forward curve that is piecewise flat rather than smooth. The finished curve reprices every input to within about two tenths of a basis point."),
  img("chart_sofr.png", 560),
  CAP("Figure 1. SOFR risk-free zero curve, continuous compounding."),
  P(`The calibration as at ${ASOF} is mildly humped: the curve rises through the first year to about 3.95 per cent, is broadly flat across the two-to-five-year segment near 3.96 per cent, and rises to about 4.11 per cent at ten years.`),
  table(["Tenor", "SOFR zero rate"], sofrRows, wA),
  CAP("Table 1. SOFR continuous-compounded zero rates."),

  H1("3. The credit overlay (illustration)"),
  P("To show how a spread layer is added, credit risk is expressed as a spread over the SOFR curve, differentiated by rating. The market quotes, for each rating, a single option-adjusted spread (OAS) blended across maturities [7]; the model turns that into a term structure from three inputs: the level (the rating's OAS, a spread over Treasuries [7]); a maturity shape borrowed from the investment-grade index's maturity buckets; and the Treasury–SOFR basis, which restates the spread from a pickup over Treasuries to a pickup over SOFR."),
  P("Two conventions are handled explicitly so the arithmetic is consistent. The basis is computed zero-against-zero — a Treasury zero curve is bootstrapped from the constant-maturity par yields, rather than comparing a par yield to a zero rate — and the resulting spread, which is quoted in semiannual bond-equivalent terms like the OAS, is added to the SOFR curve in the same semiannual compounding rather than as a continuous spread. Both matter only at wide (high-yield) spreads but are corrected regardless."),
  table(["Rating", "OAS over Treasuries (bp)"], oasRows, wB),
  CAP("Table 2. Blended index OAS by rating."),
  table(["Tenor", ...RAT], spreadRows, wC),
  CAP("Table 3. Credit spread over SOFR by rating and tenor (basis points)."),
  img("chart_allin.png", 580),
  CAP("Figure 2. All-in fixed rate by rating; SOFR shown for reference."),
  table(["Tenor", "SOFR", ...RAT], allinRows, wD),
  CAP("Table 4. All-in fixed rate by rating and tenor (per cent, continuous compounding)."),

  H1("4. Data and validation"),
  P("The overnight rate and its history come from the Federal Reserve Bank of New York [6]; the futures from the CME, through a delayed public source; the SOFR swap rates from Pensford's public rates feed; and the corporate spreads and Treasury yields from the St. Louis Fed's FRED [7]. All are free and end-of-day. Before each build the inputs pass range and consistency checks; after the build the curve is confirmed to reprice its inputs and to be arbitrage-free (discount factors strictly decreasing, so instantaneous forwards are non-negative); and if the swap feed is unreachable the build falls back to last-known values rather than failing."),

  H1("5. Known limitations"),
  P("The following are the constraints a reader should weigh before relying on the output. They are stated in full because, for a bootstrapping exercise on free data, the honest boundary of what the curve can and cannot support is the point."),
  H2("5.1 Modelling and data"),
  BUL("Curve capped at ten years. The public swap source publishes SOFR swaps only to ten years, so the model produces no rates beyond that point (it does not extrapolate)."),
  BUL("Interpolation choice. Log-linear on discount factors gives piecewise-flat instantaneous forwards; a small futures reprice residual (at most about 0.15 bp, mean 0.02 bp) follows from the mismatch between the averaging convention of the futures and a flat forward. We confirmed its nature: the overnight-indexed swaps reprice exactly and the residual sits only on the futures, so it is an interpolation effect, not a convention error. A smoother (log-cubic) scheme does not converge on this instrument set, so log-linear is retained."),
  BUL("Futures convexity is not corrected. Daily-margined futures imply a rate slightly above the equivalent forward; the omission is below a basis point in the first year and a few basis points by two and a half years [5]."),
  BUL("Turn-of-year and quarter-end effects in overnight rates are not modelled; instruments whose accrual spans a turn are therefore slightly mispriced."),
  BUL("Data is free, delayed, indicative, and drawn from several providers at slightly different times, which suits a reference calculation rather than execution."),
  BUL("Credit overlay. A single maturity shape (from the investment-grade index) is applied to every rating; the high-yield long end is the least reliable region. The spreads are index-level references, not any specific borrower's spread."),
  H2("5.2 Validation and reproducibility"),
  BUL("Repricing verifies internal consistency only. The curve reproduces its own inputs by construction; this does not by itself confirm that the instrument conventions (day count, payment lag, futures dates) match those of the quoting source. Those conventions are set to the market standard but are assumed, not independently reconciled."),
  BUL("No independent cross-validation. Results have not yet been checked against a second pricing engine or an analytic benchmark, which is the check that would catch a systematic set-up error the self-repricing cannot."),
  BUL("Runs are not yet bit-reproducible. Because the inputs are fetched live, a given calibration is a snapshot; the raw quotes are not persisted, so an exact re-run after the fact is not currently possible."),
  BUL("Single free providers. A provider changing or withdrawing an endpoint is a real risk (the swap provider moved its endpoint in 2026); a last-known fallback keeps the build running but degrades quality."),
  P("A natural validation roadmap follows directly from the above: a test suite with a frozen input fixture and a golden-master repricing test; persistence of the raw input snapshot for reproducibility; and an independent cross-check against a second engine. None changes the methodology; each raises the confidence with which its output can be used."),

  H1("References"),
  REF(1, [txt("Ballabio, L. "), txt("Curve bootstrapping.", { italics: true }), txt(" The QuantLib Guide. https://www.quantlibguide.com/Curve%20bootstrapping.html")]),
  REF(2, [txt("Keogh, K. "), txt("Bootstrapping a SOFR curve.", { italics: true }), txt(" https://kevindkeogh.com/posts/bootstrapping-a-sofr-curve/")]),
  REF(3, [txt("Ametrano, F. M., and Bianchetti, M. (2013). "), txt("Everything You Always Wanted to Know About Multiple Interest Rate Curve Bootstrapping but Were Afraid to Ask.", { italics: true }), txt(" Working paper.")]),
  REF(4, [txt("Ballabio, L. "), txt("Implementing QuantLib.", { italics: true }), txt(" Leanpub.")]),
  REF(5, [txt("Hull, J. C. "), txt("Options, Futures, and Other Derivatives.", { italics: true }), txt(" Pearson.")]),
  REF(6, [txt("Federal Reserve Bank of New York. "), txt("Secured Overnight Financing Rate (SOFR).", { italics: true }), txt(" https://www.newyorkfed.org/markets/reference-rates/sofr")]),
  REF(7, [txt("Federal Reserve Bank of St. Louis. "), txt("FRED: ICE BofA US Corporate and High Yield Option-Adjusted Spreads.", { italics: true }), txt(" https://fred.stlouisfed.org")]),
];

const doc = new Document({
  numbering: { config: [{ reference: "b", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 360, hanging: 200 } } } }] }] },
  styles: { default: { document: { run: { font: "Calibri", size: 21 } } } },
  sections: [{ properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 1440, bottom: 1440, left: 1440, right: 1440 } } }, children }],
});
Packer.toBuffer(doc).then((buf) => { fs.writeFileSync(OUT, buf); console.log("wrote", OUT, buf.length, "bytes, asof", ASOF); });
