import { strToU8, zipSync } from "fflate";

/** One cell: text, a number (kept as a real number so Excel can add it up), or empty. */
export type Cell = string | number | null | undefined;
export type Sheet = {
  name: string;
  rows: Cell[][];
  /** Rows (0-based) to print in bold: the titles and the table's header row. */
  bold?: number[];
  /** Column widths in characters; guessed from the content when left out. */
  widths?: number[];
};

const esc = (s: string) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
const col = (i: number) => { let n = i, s = ""; do { s = String.fromCharCode(65 + (n % 26)) + s; n = Math.floor(n / 26) - 1; } while (n >= 0); return s; };

function sheetXml(sh: Sheet) {
  const bold = new Set(sh.bold ?? []);
  const widths = sh.widths ?? sh.rows.reduce<number[]>((w, r) => { r.forEach((c, i) => { w[i] = Math.min(60, Math.max(w[i] ?? 8, String(c ?? "").length + 2)); }); return w; }, []);
  const rows = sh.rows.map((r, y) => {
    const cells = r.map((c, x) => {
      if (c === null || c === undefined || c === "") return "";
      const ref = `${col(x)}${y + 1}`, s = bold.has(y) ? ' s="1"' : "";
      return typeof c === "number" && Number.isFinite(c)
        ? `<c r="${ref}"${s}><v>${c}</v></c>`
        : `<c r="${ref}"${s} t="inlineStr"><is><t xml:space="preserve">${esc(String(c))}</t></is></c>`;
    }).join("");
    return `<row r="${y + 1}">${cells}</row>`;
  }).join("");
  const cols = widths.map((w, i) => `<col min="${i + 1}" max="${i + 1}" width="${w}" customWidth="1"/>`).join("");
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetPr><pageSetUpPr fitToPage="1"/></sheetPr><cols>${cols}</cols><sheetData>${rows}</sheetData><pageSetup paperSize="9" orientation="portrait" fitToWidth="1" fitToHeight="0"/></worksheet>`;
}

/** Builds a real .xlsx (one or more sheets, A4 portrait, bold title rows) with no spreadsheet library. */
export function buildXlsx(sheets: Sheet[]): Blob {
  const head = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>';
  const files: Record<string, Uint8Array> = {
    "[Content_Types].xml": strToU8(`${head}<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>${sheets.map((_, i) => `<Override PartName="/xl/worksheets/sheet${i + 1}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>`).join("")}</Types>`),
    "_rels/.rels": strToU8(`${head}<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>`),
    "xl/workbook.xml": strToU8(`${head}<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>${sheets.map((s, i) => `<sheet name="${esc(s.name.replace(/[\\/?*[\]:]/g, " ").slice(0, 31))}" sheetId="${i + 1}" r:id="rId${i + 1}"/>`).join("")}</sheets></workbook>`),
    "xl/_rels/workbook.xml.rels": strToU8(`${head}<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">${sheets.map((_, i) => `<Relationship Id="rId${i + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet${i + 1}.xml"/>`).join("")}<Relationship Id="rId${sheets.length + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>`),
    "xl/styles.xml": strToU8(`${head}<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><name val="Calibri"/></font></fonts><fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills><borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>`),
  };
  sheets.forEach((s, i) => { files[`xl/worksheets/sheet${i + 1}.xml`] = strToU8(sheetXml(s)); });
  return new Blob([zipSync(files) as BlobPart], { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" });
}

export function downloadXlsx(filename: string, sheets: Sheet[]) {
  const url = URL.createObjectURL(buildXlsx(sheets));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
}

const NUMBER = /^-?(?:Rs\.?\s?)?-?\d[\d,]*(?:\.\d+)?$/;
/** "Rs 1,200" and "-500" become real numbers so Excel can add a column up; anything else stays text. */
const typed = (t: string): Cell => (NUMBER.test(t) && !/^0\d/.test(t.replace(/^(-?Rs\.?\s?)/, "")) ? Number(t.replace(/Rs\.?\s?|,/g, "")) : t);

/**
 * The printed document as a spreadsheet: every heading, line of text, list item and table in reading order,
 * one row each (a table row is one row of cells). What is on the page is what is in the file, and the
 * bar and anything marked no-print are left out.
 */
export function sheetFromDocument(root: HTMLElement, name: string): Sheet {
  const rows: Cell[][] = [], bold: number[] = [];
  const text = (e: Element) => (e.textContent ?? "").replace(/\s+/g, " ").trim();
  root.querySelectorAll("table, h1, h2, h3, p, li").forEach((el) => {
    if (el.closest(".no-print")) return;
    if (el.tagName === "TABLE") {
      if (el.parentElement?.closest("table")) return;
      el.querySelectorAll("tr").forEach((tr) => {
        const cells = [...tr.children].filter((c) => /^T[DH]$/.test(c.tagName));
        if (!cells.some((c) => text(c))) return;
        if (tr.closest("thead") || cells.every((c) => c.tagName === "TH")) bold.push(rows.length);
        rows.push(cells.map((c) => typed(text(c))));
      });
      rows.push([]);
      return;
    }
    if (el.closest("table")) return;
    if (el.tagName === "LI" && el.querySelector("p, li")) return;
    if (el.tagName === "P" && el.closest("li")) return;
    const t = text(el);
    if (!t) return;
    if (/^H\d$/.test(el.tagName) || /\bfont-bold\b/.test(el.className)) bold.push(rows.length);
    const n = el.tagName === "LI" && el.parentElement?.tagName === "OL" ? [...el.parentElement.children].indexOf(el) + 1 : null;
    rows.push(n ? [n, t] : [t]);
  });
  return { name, rows, bold, widths: undefined };
}
