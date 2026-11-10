import { type Cell, type Sheet, downloadXlsx } from "@/lib/xlsx";

export type ReportMeta = {
  title: string;
  branch?: string;
  /** e.g. "1 Nov 2026 – 11 Nov 2026" or "As of 11 Nov 2026" */
  period?: string;
};

/** Turn "1234.50", "-Rs 1,200", or a number into a real Excel number when possible. */
export function asAmount(v: string | number | null | undefined): Cell {
  if (v == null || v === "") return null;
  if (typeof v === "number") return Number.isFinite(v) ? v : null;
  const s = String(v).trim();
  if (/^-?(?:Rs\.?\s?)?-?\d[\d,]*(?:\.\d+)?$/.test(s) && !/^0\d/.test(s.replace(/^(-?Rs\.?\s?)/, ""))) {
    return Number(s.replace(/Rs\.?\s?|,/g, ""));
  }
  const n = Number(s);
  return Number.isFinite(n) && s !== "" ? n : s;
}

/**
 * A report-style sheet: title, optional branch + period, blank row, bold header, data rows.
 * Amount columns should already be numbers (use asAmount).
 */
export function reportSheet(
  name: string,
  meta: ReportMeta,
  headers: string[],
  rows: Cell[][],
  opts?: { totalRow?: Cell[]; widths?: number[] },
): Sheet {
  const out: Cell[][] = [[meta.title]];
  const bold = [0];
  if (meta.branch) out.push([meta.branch]);
  if (meta.period) out.push([meta.period]);
  out.push([]);
  bold.push(out.length);
  out.push(headers);
  for (const r of rows) out.push(r);
  if (opts?.totalRow) {
    bold.push(out.length);
    out.push(opts.totalRow);
  }
  return { name: name.slice(0, 31), rows: out, bold, widths: opts?.widths };
}

export function downloadReport(filename: string, sheets: Sheet[]) {
  const base = filename.replace(/\.xlsx$/i, "").replace(/\.csv$/i, "");
  downloadXlsx(`${base}.xlsx`, sheets.length ? sheets : [{ name: "Report", rows: [["Nothing to export"]] }]);
}
