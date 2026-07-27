// Build the paper (Model_Documentation.docx) from doc_data.json + charts in this dir.
// Requires the `docx` npm package:  npm install docx   (then:  node build_doc.js)
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType,
  Table, TableRow, TableCell, WidthType, BorderStyle, ImageRun, LevelFormat,
} = require("docx");

const DIR = __dirname;
const OUT = path.join(DIR, "Model_Documentation.docx");
const CONTENT_W = 9360;
const D = JSON.parse(fs.readFileSync(path.join(DIR, "doc_data.json"), "utf8"));
const ASOF = D.asof, TEN = D.labels, RAT = ["AAA","AA","A","BBB","BB","B","CCC"];

const RULE_THICK = { style: BorderStyle.SINGLE, size: 8, color: "000000" };
const RULE_THIN = { style: BorderStyle.SINGLE, size: 4, color: "000000" };
const NOB = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };
function cell(text, w, { header = false, first = false, last = false } = {}) {
  const borders = header ? { top: RULE_THICK, bottom: RULE_THIN, left: NOB, right: NOB }
    : last ? { top: NOB, bottom: RULE_THICK, left: NOB, right: NOB }
    : { top: NOB, bottom: NOB, left: NOB, right: NOB };
  return new TableCell({ width: { size: w, type: WidthType.DXA }, borders,
    margins: { top: 34, bottom: 34, left: 80, right: 80 },
    children: [new Paragraph({ alignment: first ? AlignmentType.LEFT : AlignmentType.RIGHT, spacing: { after: 0 },
      children: [new TextRun({ text: String(text), bold: header, size: 16, color: "000000" })] })] });
}
function table(headers, rows, widths) {
  const head = new TableRow({ tableHeader: true, children: headers.map((h, i) => cell(h, widths[i], { header: true, first: i === 0 })) });
  const body = rows.map((r, ri) => new TableRow({ children: r.map((c, i) => cell(c, widths[i], { first: i === 0, last: ri === rows.length - 1 })) }));
  return new Table({ columnWidths: widths, width: { size: widths.reduce((a, b) => a + b, 0), type: WidthType.DXA }, rows: [head, ...body] });
}
function img(file, w) {
  const data = fs.readFileSync(path.join(DIR, file));
  const ratio = file.includes("allin") ? 570 / 1050 : 470 / 1050;
  return new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 120, after: 60 },
    children: [new ImageRun({ type: "png", data, transformation: { width: w, height: Math.round(w * ratio) } })] });
}
const H1 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_1, spacing: { before: 280, after: 100 }, children: [new TextRun({ text: t, bold: true })] });
const H2 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_2, spacing: { before: 160, after: 60 }, children: [new TextRun({ text: t, bold: true, size: 22 })] });
const P = (t) => new Paragraph({ alignment: AlignmentType.JUSTIFIED, spacing: { after: 120, line: 276 }, children: [new TextRun({ text: t, size: 21 })] });
const EQ = (t) => new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 40, after: 120 }, children: [new TextRun({ text: t, italics: true, size: 21 })] });
const CAP = (t) => new Paragraph({ spacing: { after: 160 }, alignment: AlignmentType.CENTER, children: [new TextRun({ text: t, size: 17, color: "333333" })] });
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
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 }, border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: "000000" } },
    children: [new TextRun({ text: `Working note. Illustrative calibration as at ${ASOF}`, size: 18, italics: true, color: "555555" })] }),

  new Paragraph({ spacing: { after: 60 }, indent: { left: 540, right: 540 }, children: [new TextRun({ text: "Abstract", bold: true, size: 20 })] }),
  new Paragraph({ alignment: AlignmentType.JUSTIFIED, spacing: { after: 100, line: 264 }, indent: { left: 540, right: 540 },
    children: [new TextRun({ size: 19, text:
      "This note builds a US dollar risk-free discount curve from free, end-of-day data, then adds a credit-spread layer by rating. The risk-free curve is bootstrapped from SOFR instruments (overnight fixings, futures, and overnight-indexed swaps) and reprices each of them exactly. We give the mathematics of the construction, then spend most of the note on the parts that are easy to get wrong when the only data you have is free and public: matching quoting conventions, keeping the Treasury basis internally consistent, and confirming the curve admits no arbitrage. An illustrative calibration and a full account of the limitations follow." })] }),
  new Paragraph({ spacing: { after: 160 }, indent: { left: 540, right: 540 },
    children: [new TextRun({ text: "Keywords: ", bold: true, size: 18 }), new TextRun({ text: "SOFR; yield-curve bootstrapping; discount factors; overnight-indexed swaps; credit spreads; option-adjusted spread; term structure.", size: 18, italics: true })] }),

  H1("1. Introduction and purpose"),
  P("The model has two layers. A risk-free curve comes from SOFR [6], and a set of credit spreads by rating sits on top of it. Together they give discount factors and forward rates out to ten years. Most of what follows concerns the risk-free curve and how to build it from data anyone can pull for free. The credit layer is there to show how a spread is added, not to study any particular borrower."),
  P("We kept the construction auditable. The risk-free part is pinned to traded instruments and reprices them exactly, and each assumption is written down rather than folded into a single output number."),

  H1("2. The SOFR risk-free curve"),
  P("Bootstrapping solves for the discount factors that reprice a set of market instruments exactly, one maturity at a time from the short end out [1, 2]. It does not fit a smooth curve through the quotes; it inverts them. The method is standard [3] and the implementation uses QuantLib [1, 4]."),
  P("Three kinds of instrument each cover their own stretch of the curve. The overnight SOFR fixing [6], together with the realised fixings of the current month, anchors the front. One- and three-month SOFR futures reach to about two and a half years. Overnight-indexed swaps carry the curve from three to ten years through their par rates. The free swap feed stops at ten years, so the curve stops there. We do not extrapolate past the last real quote."),

  H1("3. Mathematical formulation"),
  P("The curve is a set of discount factors DF(0,T), the value today of one unit paid at T. From them we read the continuously-compounded zero rate z(T) and the instantaneous forward rate f(t):"),
  EQ("DF(0,T) = exp( −z(T)·T ),        f(t) = −d ln DF(0,t) / dt ."),
  P("Bootstrapping picks the discount factors so that each calibrating instrument prices to its quote. An instrument maturing at Tₙ depends only on the factors up to Tₙ, so they are solved in order from the short end. Each instrument adds one unknown, DF(0,Tₙ), found by a single root solve with the earlier factors held fixed. That ordering is why the fit is exact rather than a least-squares approximation."),
  P("Each instrument enters through its pricing identity. A SOFR overnight-indexed swap is worth zero at par, which pins its fixed rate:"),
  EQ("R = ( DF(0,T₀) − DF(0,Tₙ) ) / Σᵢ τᵢ DF(0,Tᵢ) ."),
  P("The denominator is the annuity, τᵢ the accrual of period i, and the numerator the value of the daily-compounded floating leg. Futures pin the forward over their window: one-month contracts settle on the arithmetic average of the daily fixings, three-month contracts on their daily compounding."),
  P("Between nodes we interpolate log-linearly on discount factors, so ln DF(0,t) is linear in t and the forward f(t) is constant on each interval. That gives a clean no-arbitrage test. The curve admits no arbitrage exactly when the discount factors strictly decrease,"),
  EQ("DF(0,Tᵢ₊₁) < DF(0,Tᵢ)   ⇔   f(t) ≥ 0 ,"),
  P("which the build checks after every calibration."),

  H1("4. The credit overlay (illustration)"),
  P("Credit risk goes on as a spread over SOFR, split by rating. The market gives one option-adjusted spread (OAS) per rating, blended across maturities [7]. Turning that single number into a term structure takes three pieces. The level is the rating's OAS, quoted over Treasuries. The slope comes from the investment-grade index's maturity buckets, which we reuse for every rating. The third piece is the Treasury-to-SOFR basis, which moves the spread from a pickup over Treasuries to a pickup over SOFR. Getting those pieces to combine consistently is the work of Section 5."),
  table(["Rating", "OAS over Treasuries (bp)"], oasRows, wB),
  CAP("Table 2. Blended index OAS by rating."),

  H1("5. Working with free data"),
  P("Free data breaks in ways a paid terminal does not. Here is what we ran into and what each fix was. None of it changes the formulation in Section 3."),
  P("The swap feed is not a contract. Partway through this work the provider rebuilt its site and moved the data to a new endpoint, and the old one began returning 404s. We re-pointed the loader and added a last-known fallback, so the next time an endpoint moves the curve degrades instead of failing outright. That same feed only publishes swaps to ten years, which is why the curve ends at ten years rather than extrapolating a number and presenting it as market data."),
  P("Compounding is easy to get wrong here. OAS and the Treasury-SOFR basis are quoted semiannually, but the discount curve holds rates continuously. A spread s quoted semiannually equals 2·ln(1 + s/2) continuously, and the gap grows with the spread: under a basis point at investment grade, about 24 bp at a ten-per-cent (CCC) level. Added as a continuous spread it would overstate the wide ones, so we add it in the semiannual terms it is quoted in."),
  P("The basis needs the same care. The Treasury inputs are constant-maturity par yields, and once the curve slopes a par yield and a zero rate are not the same number. We bootstrap a Treasury zero curve from the par yields first (for a par bond priced at 100, 1 = (y/2)·Σⱼ DF(0,Tⱼ) + DF(0,Tₙ)), then take the basis zero against zero."),
  P("The futures do not reprice to the last decimal, and two effects sit behind that. They are easy to conflate, so keep them apart. One is convexity: a margined future prices a touch above the equivalent forward. We handle that separately, by setting the convexity adjustment to zero, and return to it below. The other is a small numerical residual. A piecewise-flat forward cannot reproduce a rate that settles on an average or a daily compounding, so up to about 0.15 bp is left on the futures. That is not an arbitrage violation: the discount factors strictly decrease, so the curve admits no arbitrage by construction, and the swaps reprice exactly. The residual shows up on a few monthly contracts and does not grow with maturity, which points to interpolation rather than a funding effect. We keep log-linear because a log-cubic scheme will not converge on this set."),
  P("We left the futures convexity adjustment at zero. Doing it properly needs a volatility input we cannot get for free, and the bias is small (under a basis point in the first year, a few by two and a half years) [5], so we flag it rather than guess. One thing we do not leave to chance is no-arbitrage: log-linear interpolation stays arbitrage-free only while the discount factors keep falling, so the build tests that on every run and stops if a forward turns negative."),

  H1("6. Results and validation"),
  P(`The calibration as at ${ASOF} is below. The SOFR curve is mildly humped: up through the first year, roughly flat from two to five years, then rising toward ten. Investment-grade all-in rates land within about a point of the risk-free curve, and the high-yield rungs spread out quickly.`),
  img("chart_sofr.png", 540),
  CAP("Figure 1. SOFR risk-free zero curve, continuous compounding."),
  table(["Tenor", "SOFR zero rate"], sofrRows, wA),
  CAP("Table 1. SOFR continuous-compounded zero rates."),
  table(["Tenor", ...RAT], spreadRows, wC),
  CAP("Table 3. Credit spread over SOFR by rating and tenor (basis points)."),
  img("chart_allin.png", 560),
  CAP("Figure 2. All-in fixed rate by rating; SOFR shown for reference."),
  table(["Tenor", "SOFR", ...RAT], allinRows, wD),
  CAP("Table 4. All-in fixed rate by rating and tenor (per cent, continuous compounding)."),
  P("The data is all free. The overnight rate and its history come from the New York Fed [6], the futures from the CME through a delayed public feed, the swap rates from Pensford, and the corporate spreads and Treasury yields from FRED [7]. Inputs are range-checked before each build, and the finished curve is checked to reprice its inputs and to admit no arbitrage."),

  H1("7. Known limitations"),
  P("Weigh these before using the curve. On free data, knowing the boundary is much of the exercise."),
  H2("7.1 Modelling and data"),
  BUL("The curve stops at ten years (Section 5) and is not extrapolated past the last node."),
  BUL("Log-linear interpolation gives piecewise-flat forwards and a sub-basis-point futures residual, which we checked is an interpolation effect (Section 5)."),
  BUL("The futures convexity adjustment is left at zero, a documented approximation."),
  BUL("Turn-of-year and quarter-end spikes in the overnight rate are not modelled."),
  BUL("The data is free, delayed, indicative, and pulled from several providers at slightly different times."),
  BUL("The credit overlay reuses one investment-grade maturity shape for every rating; the high-yield long end is the weakest part, and the spreads are index averages, not any single borrower's."),
  H2("7.2 Validation and reproducibility"),
  BUL("Repricing shows internal consistency. The instrument conventions match the SOFR-OIS standard but are not reconciled against a second source."),
  BUL("Nothing has been cross-checked against a second pricing engine or an analytic benchmark."),
  BUL("Runs are not bit-reproducible: the inputs are fetched live and the raw quotes are not saved."),
  BUL("The data rests on single free providers; the fallback keeps a run alive through an outage, but the result is worse."),
  P("Three things would raise confidence without touching the method: a test suite on a frozen input fixture with a golden-master reprice, a saved snapshot of the raw inputs so a run reproduces exactly, and a cross-check against a second pricing engine."),

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
