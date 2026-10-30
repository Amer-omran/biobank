// Builds the graduation report (.docx) from the chapter content files.
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, ImageRun, Table, TableRow, TableCell, AlignmentType, HeadingLevel,
  WidthType, ShadingType, BorderStyle, PageBreak, Footer, PageNumber, TableOfContents, SequentialIdentifier,
  LevelFormat, TabStopType, VerticalAlign, StyleLevel, LineRuleType,
} = require("docx");

const IMG = path.join(__dirname, "img");
const FONT = "Times New Roman";
const PAGE_W = 12240, MARGIN = 1440, CONTENT_W = PAGE_W - 2 * MARGIN; // US Letter, 1" margins
const HL = "yellow";

// ---- inline markup: **bold**, *italic*, [[to fill in]] (highlighted), `code`
// Invisible left-to-right marks around «quoted Arabic» keep the quotes from being mirrored or reordered
const LRM = "\u200E";
// Straight quotes look the same in both directions, unlike « » which get mirrored next to Arabic
const isolateArabicQuotes = (t) => t.replace(/«([^»]*[\u0600-\u06FF][^»]*)»/g, `${LRM}"$1"${LRM}`);
function runs(text, base = {}) {
  text = isolateArabicQuotes(text);
  const out = [];
  const re = /(\*\*[^*]+\*\*|\*[^*]+\*|\[\[[^\]]+\]\]|`[^`]+`)/g;
  let last = 0, m;
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(new TextRun({ text: text.slice(last, m.index), ...base }));
    const t = m[0];
    if (t.startsWith("**")) out.push(new TextRun({ text: t.slice(2, -2), bold: true, ...base }));
    else if (t.startsWith("[[")) out.push(new TextRun({ text: "[" + t.slice(2, -2) + "]", highlight: HL, ...base }));
    else if (t.startsWith("`")) out.push(new TextRun({ text: t.slice(1, -1), font: "Consolas", size: 20, ...base }));
    else out.push(new TextRun({ text: t.slice(1, -1), italics: true, ...base }));
    last = m.index + t.length;
  }
  if (last < text.length) out.push(new TextRun({ text: text.slice(last), ...base }));
  return out;
}

// Justified lines that contain Arabic make LibreOffice's layout loop forever, so such paragraphs are left-aligned
const ARABIC = /[\u0600-\u06FF]/;
const align = (t) => (ARABIC.test(t) ? AlignmentType.LEFT : AlignmentType.JUSTIFIED);
const P = (t, o = {}) => new Paragraph({ children: runs(t), alignment: align(t), spacing: { after: 120 }, ...o });
const centered = (t, o = {}) => new Paragraph({ children: runs(t, o.run || {}), alignment: AlignmentType.CENTER, spacing: { after: o.after ?? 120, before: o.before ?? 0 } });

function chapterTitle(t) {
  const m = /^Chapter (\d+)/.exec(t);
  if (m) { counter.chapter = Number(m[1]); counter.Figure = 0; counter.Table = 0; }
  return new Paragraph({
    heading: HeadingLevel.HEADING_1, pageBreakBefore: true, alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: t })], spacing: { after: 240 },
  });
}
const H2 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun(t)] });
const H3 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_3, children: [new TextRun(t)] });
const bullets = (items) => items.map((t) => new Paragraph({ children: runs(t), numbering: { reference: "bullets", level: 0 }, alignment: align(t), spacing: { after: 60 } }));
let numberedListId = 0;
const numbers = (items) => { const ref = `num${++numberedListId}`; numberedConfigs.push(ref); return items.map((t) => new Paragraph({ children: runs(t), numbering: { reference: ref, level: 0 }, alignment: align(t), spacing: { after: 60 } })); };
const numberedConfigs = [];

// Chapter-based numbering (Figure 3.1, Table 3.2); lists are built from the two caption styles
const counter = { chapter: 0, Figure: 0, Table: 0 };
function caption(label, text) {
  counter[label] += 1;
  return new Paragraph({
    style: label === "Figure" ? "FigureCaption" : "TableCaption", alignment: AlignmentType.CENTER, keepLines: true,
    keepNext: label === "Table", spacing: label === "Figure" ? { before: 60, after: 200 } : { before: 120, after: 60 },
    children: [new TextRun(`${label} ${counter.chapter}.${counter[label]}: ${text}`)],
  });
}

function figure(file, cap, widthIn = 6.0) {
  const buf = fs.readFileSync(path.join(IMG, file));
  const w = buf.readUInt32BE(16), h = buf.readUInt32BE(20); // PNG header
  const width = Math.round(widthIn * 96), height = Math.round(width * h / w);
  return [
    new Paragraph({ alignment: AlignmentType.CENTER, keepNext: true, spacing: { before: 120, after: 60, line: 240, lineRule: LineRuleType.AUTO },
      children: [new ImageRun({ type: "png", data: buf, transformation: { width, height }, altText: { title: cap, description: cap, name: file } })] }),
    caption("Figure", cap),
  ];
}

const border = { style: BorderStyle.SINGLE, size: 4, color: "8C8C8C" };
const borders = { top: border, bottom: border, left: border, right: border };
function table(cap, headers, rows, fractions) {
  const fr = fractions || headers.map(() => 1 / headers.length);
  const widths = fr.map((f) => Math.round(f * CONTENT_W));
  widths[widths.length - 1] = CONTENT_W - widths.slice(0, -1).reduce((a, b) => a + b, 0);
  const keep = rows.length <= 10; // keep short tables on one page
  const cell = (t, i, head, last) => new TableCell({
    borders, width: { size: widths[i], type: WidthType.DXA }, verticalAlign: VerticalAlign.CENTER,
    shading: head ? { fill: "DCE6F2", type: ShadingType.CLEAR, color: "auto" } : undefined,
    margins: { top: 60, bottom: 60, left: 100, right: 100 },
    children: [new Paragraph({ keepNext: keep && !last, spacing: { after: 0, line: 260 }, children: runs(String(t), { size: 20, bold: head || undefined }) })],
  });
  return [
    caption("Table", cap),
    new Table({
      width: { size: CONTENT_W, type: WidthType.DXA }, columnWidths: widths,
      rows: [new TableRow({ tableHeader: true, children: headers.map((h, i) => cell(h, i, true)) }),
        ...rows.map((r, j) => new TableRow({ cantSplit: true, children: r.map((t, i) => cell(t, i, false, j === rows.length - 1)) }))],
    }),
    new Paragraph({ spacing: { before: 0, after: 0, line: 160, lineRule: LineRuleType.AUTO }, children: [new TextRun({ text: "", size: 12 })] }),
  ];
}

const code = (lines) => lines.map((l, i) => new Paragraph({
  spacing: { after: 0, line: 260 }, shading: { fill: "F2F2F2", type: ShadingType.CLEAR, color: "auto" },
  indent: { left: 360 }, children: [new TextRun({ text: l || " ", font: "Consolas", size: 19 })],
  keepNext: i < lines.length - 1,
}));
const eq = (t) => new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 120, after: 160 }, children: [new TextRun({ text: t, italics: true })] });

// ---- content -------------------------------------------------------------
const K = { P, H2, H3, bullets, numbers, figure, table, code, eq, centered, runs };
const chapters = ["front", "ch1", "ch2", "ch3", "ch4", "ch5", "ch6", "back"].map((f) => require(`./content/${f}.js`));

const children = [];
// Cover page (layout follows the college template)
const logo = fs.readFileSync(path.join(__dirname, "logo.jpeg"));
children.push(
  new Paragraph({ tabStops: [{ type: TabStopType.RIGHT, position: CONTENT_W }], children: [
    new TextRun({ text: "Kingdom of Saudi Arabia", bold: true }), new TextRun({ text: "\t" }),
    new ImageRun({ type: "jpg", data: logo, transformation: { width: 150, height: 62 }, altText: { title: "Gulf Colleges logo", description: "Gulf Colleges logo", name: "logo" } })] }),
  new Paragraph({ children: [new TextRun({ text: "Ministry of Education", bold: true })] }),
  new Paragraph({ children: [new TextRun({ text: "Gulf Colleges", bold: true })] }),
  new Paragraph({ children: [new TextRun({ text: "Department of Information Technology", bold: true })] }),
  centered("", { before: 1200 }),
  centered("An AI Platform for Analysing Customer Sentiment and Food Preference Behaviour in Saudi Restaurants", { run: { bold: true, italics: true, size: 34, color: "C00000" }, after: 120 }),
  centered("Saudi Restaurant Sentiment & Food Preference Analytics Platform", { run: { italics: true, size: 26, color: "C00000" }, after: 900 }),
  centered("Submitted by", { run: { bold: true, italics: true }, after: 240 }),
  centered("Name: [[Student name]]          ID: [[Student ID]]", { run: { bold: true, italics: true }, after: 600 }),
  centered("Graduation Project", { run: { bold: true, italics: true, size: 26 }, after: 1000 }),
  centered("Supervisor: Dr. Baha Eldin Hamouda", { run: { bold: true, italics: true }, after: 240 }),
  centered("November 2026", { run: { bold: true, italics: true } }),
);
for (const ch of chapters) children.push(...ch(K, { chapterTitle, TableOfContents, StyleLevel, PageBreak, Paragraph, TextRun, AlignmentType }).flat(Infinity));

const doc = new Document({
  creator: "Graduation project", title: "Saudi Restaurant Sentiment & Food Preference Analytics Platform",
  features: { updateFields: true },
  styles: {
    default: { document: { run: { font: FONT, size: 24 }, paragraph: { spacing: { line: 360, lineRule: LineRuleType.AUTO } } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 32, bold: true, italics: true, underline: {}, font: FONT, color: "000000" },
        paragraph: { spacing: { before: 0, after: 240 }, outlineLevel: 0, alignment: AlignmentType.CENTER } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 26, bold: true, font: FONT, color: "000000" }, paragraph: { spacing: { before: 280, after: 120 }, outlineLevel: 1, keepNext: true } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 24, bold: true, italics: true, font: FONT, color: "000000" }, paragraph: { spacing: { before: 200, after: 100 }, outlineLevel: 2, keepNext: true } },
      { id: "TOC1", name: "toc 1", basedOn: "Normal", next: "Normal", run: { bold: true },
        paragraph: { spacing: { before: 60, after: 0, line: 276, lineRule: LineRuleType.AUTO } } },
      { id: "TOC2", name: "toc 2", basedOn: "Normal", next: "Normal",
        paragraph: { indent: { left: 360 }, spacing: { before: 0, after: 0, line: 276, lineRule: LineRuleType.AUTO } } },
      { id: "FigureCaption", name: "Figure Caption", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 20, bold: true, font: FONT, color: "1F3864" }, paragraph: { spacing: { line: 276 } } },
      { id: "TableCaption", name: "Table Caption", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 20, bold: true, font: FONT, color: "1F3864" }, paragraph: { spacing: { line: 276 } } },
    ],
  },
  numbering: { config: [
    { reference: "bullets", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
    ...numberedConfigs.map((ref) => ({ reference: ref, levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] })),
  ] },
  sections: [{
    properties: { titlePage: true, page: { size: { width: PAGE_W, height: 15840 }, margin: { top: MARGIN, bottom: MARGIN, left: MARGIN, right: MARGIN } } },
    footers: {
      default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ children: [PageNumber.CURRENT], size: 20 })] })] }),
      first: new Footer({ children: [new Paragraph({ children: [] })] }),
    },
    children,
  }],
});

Packer.toBuffer(doc).then((buf) => { fs.writeFileSync(process.argv[2] || "report.docx", buf); console.log("written"); });
