import { api } from "@/lib/api";
import { asAmount, downloadReport, reportSheet, type ReportMeta } from "@/lib/report-xlsx";
import { type Sheet } from "@/lib/xlsx";

const SOURCE: Record<string, string> = {
  payment: "Customer payment / advance", vendor_payment: "Vendor payment", money_entry: "Money in/out",
  account_opening: "Opening balance", cash_close: "Cash count difference", stock_movement: "Stock movement",
  invoice: "Invoice", goods_receipt: "Goods receipt", vendor_bill: "Vendor bill", credit_note: "Credit note",
  payroll: "Payroll", other: "Other",
};

export type LedgerApi = {
  from: string; to: string;
  rows: {
    date: string; entry_number: string; memo: string; source_type: string | null;
    account_code: string; account_name: string; debit: string; credit: string; category: string | null;
  }[];
  debit: string; credit: string; truncated: boolean;
};

export type TrialApi = {
  as_of: string | null;
  rows: { code: string; name: string; type: string; debit: string; credit: string; balance: string }[];
  debit: string; credit: string; balanced: boolean;
};

function particulars(r: LedgerApi["rows"][0]) {
  const src = r.source_type ? (SOURCE[r.source_type] ?? r.source_type) : "";
  return [r.memo, src, r.category].filter(Boolean).join(" — ");
}

/** Chronological journal book: one row per debit/credit line. */
export function monthJournalSheet(meta: ReportMeta, ledger: LedgerApi): Sheet {
  const rows = ledger.rows.map((r) => [
    r.date, r.entry_number, particulars(r), r.account_code, r.account_name,
    asAmount(r.debit) || null, asAmount(r.credit) || null,
  ]);
  return reportSheet(
    "Month journal",
    { ...meta, title: "Month journal (full ledger)" },
    ["Date", "Voucher No.", "Particulars", "Account code", "Account name", "Debit (Rs)", "Credit (Rs)"],
    rows,
    {
      totalRow: ["", "", "", "", "Total", asAmount(ledger.debit), asAmount(ledger.credit)],
      widths: [12, 16, 40, 12, 24, 14, 14],
    },
  );
}

/** Account-wise general ledger with running balance (debit − credit) per account. */
export function generalLedgerSheet(meta: ReportMeta, ledger: LedgerApi): Sheet {
  const sorted = [...ledger.rows].sort((a, b) =>
    a.account_code.localeCompare(b.account_code) || a.date.localeCompare(b.date) || a.entry_number.localeCompare(b.entry_number));
  const rows: (string | number | null)[][] = [];
  let bal = 0;
  let prev = "";
  for (const r of sorted) {
    if (r.account_code !== prev) {
      bal = 0;
      prev = r.account_code;
    }
    const d = Number(r.debit) || 0;
    const c = Number(r.credit) || 0;
    bal = Math.round((bal + d - c) * 100) / 100;
    rows.push([
      r.account_code, r.account_name, r.date, r.entry_number, particulars(r),
      d || null, c || null, bal,
    ]);
  }
  return reportSheet(
    "General ledger",
    { ...meta, title: "General ledger by account" },
    ["Account code", "Account name", "Date", "Voucher No.", "Particulars", "Debit (Rs)", "Credit (Rs)", "Balance (Rs)"],
    rows,
    { widths: [12, 24, 12, 16, 40, 14, 14, 14] },
  );
}

export function trialBalanceSheet(meta: ReportMeta, trial: TrialApi, asOf: string): Sheet {
  return reportSheet(
    "Trial balance",
    { title: "Trial balance", branch: meta.branch, period: `As of ${asOf}` },
    ["Account code", "Account name", "Type", "Debit (Rs)", "Credit (Rs)", "Balance (Rs)"],
    trial.rows.map((r) => [r.code, r.name, r.type, asAmount(r.debit), asAmount(r.credit), asAmount(r.balance)]),
    {
      totalRow: ["", "", "Total", asAmount(trial.debit), asAmount(trial.credit), ""],
      widths: [12, 28, 12, 14, 14, 14],
    },
  );
}

/** Fetch period ledger + trial balance and build the accountant sheets (journal first). */
export async function fetchMonthLedgerSheets(branchName: string, from: string, to: string): Promise<{ sheets: Sheet[]; truncated: boolean }> {
  const meta: ReportMeta = { title: "", branch: branchName, period: `${from} – ${to}` };
  const [ledger, trial] = await Promise.all([
    api<LedgerApi>(`/api/journal/ledger?date_from=${from}&date_to=${to}`),
    api<TrialApi>(`/api/journal/trial-balance?as_of=${to}`),
  ]);
  return {
    truncated: ledger.truncated,
    sheets: [
      monthJournalSheet(meta, ledger),
      generalLedgerSheet(meta, ledger),
      trialBalanceSheet(meta, trial, to),
    ],
  };
}

/** Download a finance workbook: month ledger sheets first, then optional summary sheets. */
export async function downloadFinanceWorkbook(
  filename: string,
  branchName: string,
  from: string,
  to: string,
  extraSheets: Sheet[] = [],
) {
  const { sheets, truncated } = await fetchMonthLedgerSheets(branchName, from, to);
  if (truncated) {
    sheets[0].rows.push([]);
    sheets[0].rows.push(["Note: export capped at the first lines — narrow the period for a complete ledger."]);
  }
  downloadReport(filename, [...sheets, ...extraSheets]);
}
