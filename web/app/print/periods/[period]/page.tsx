"use client";

import { useParams } from "next/navigation";
import { Suspense } from "react";
import { Grid, Letterhead, PrintBar, Section } from "@/components/print";
import { useApi } from "@/lib/api";
import { day, money } from "@/lib/format";

type Any = Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any -- mirrors the API's JSON

const ACCOUNT: Record<string, string> = { cash: "Cash", bank: "Bank", wallet: "Wallet" };
const SOURCE: Record<string, string> = { invoice_payment: "Invoice payment", advance: "Advance", other_income: "Other income", owner_capital: "Owner capital", transfer: "Transfer", vendor_payment: "Vendor payment",
  expense: "Expense", drawings: "Owner drawings", refund: "Refund", salary: "Salary", salary_advance: "Salary advance" };

export default function PrintPack() {
  return <Suspense fallback={<p className="p-8">Loading</p>}><Pack /></Suspense>;
}

/** The closing pack: profit and loss, cash, what is owed, stock, the cash counts and every payment with its proof. */
function Pack() {
  const { period } = useParams<{ period: string }>();
  const d = useApi<Any>(`/api/periods/${period}/pack`);
  const branch = useApi<{ name: string; address: string; phone: string }>("/api/branch");
  if (d.error) return <p className="p-8 text-error">{d.error}</p>;
  if (!d.data || !branch.data) return <p className="p-8">Loading</p>;
  const p = d.data, pnl = p.pnl, cf = p.cashflow;
  const back = p.kind === "month" ? `/periods/${p.period}` : "/periods";
  return (
    <div className="mx-auto max-w-[210mm] px-4 py-4 text-[11px] leading-snug sm:px-[12mm] sm:py-[10mm] print:p-0">
      <PrintBar back={{ href: back, label: "Back to month end" }} name={`Closing-pack-${p.period}`}>
        {p.status.status !== "closed" && <p className="text-warning">{p.kind === "month" ? "This month isn't closed yet: figures may still change." : "This year isn't closed yet."}</p>}
      </PrintBar>
      <Letterhead branch={branch.data} title="CLOSING PACK" right={<><p className="font-bold">{p.label}</p><p>{p.status.status === "closed" ? `Closed ${p.status.closed_at ? day(p.status.closed_at) : ""}` : "Not closed"}</p></>} />

      <Section title="1. Profit and loss">
        <Grid head={["", "Amount"]} right={[1]} rows={[
          ["Revenue: labour", money(pnl.revenue.labour)], ["Revenue: parts", money(pnl.revenue.parts)], ["Other income", money(pnl.revenue.other)], [<b key="r">Total revenue</b>, <b key="rv">{money(pnl.revenue.total)}</b>],
          ["Cost of parts sold", `-${money(pnl.cost_of_parts_sold)}`], [<b key="g">Gross profit</b>, <b key="gv">{money(pnl.gross_profit)}</b>],
          ...Object.entries(pnl.expenses_by_category).map(([k, v]) => [k, `-${money(v as string)}`]), ...Object.entries(pnl.other_costs).map(([k, v]) => [k, `-${money(v as string)}`]),
          [<b key="e">Total expenses</b>, <b key="ev">-{money(pnl.total_expenses)}</b>], [<b key="n">Net profit</b>, <b key="nv">{money(pnl.net_profit)}</b>]]} />
        <p className="text-muted">Sales tax collected for the government ({money(pnl.sales_tax_collected)}) is not included.</p>
        {p.months.length > 0 && <Grid head={["Month", "Revenue", "Expenses", "Net profit"]} right={[1, 2, 3]} rows={p.months.map((m: Any) => [m.month, money(m.revenue.total), money(m.total_expenses), money(m.net_profit)])} />}
      </Section>

      <Section title="2. Cash, bank and wallet">
        <Grid head={["Account", "At the start", "Came in", "Went out", "At the end"]} right={[1, 2, 3, 4]}
              rows={[...Object.entries(cf.accounts).map(([k, a]: [string, any]) => [ACCOUNT[k], money(a.opening), money(a.in), money(a.out), money(a.closing)]), // eslint-disable-line @typescript-eslint/no-explicit-any
                     [<b key="t">Total</b>, money(cf.opening), money(cf.in), money(cf.out), <b key="c">{money(cf.closing)}</b>]]} />
        <Grid head={["Day", "Account", "Books said", "Counted", "Difference", "Reason"]} right={[2, 3, 4]}
              rows={p.cash_closes.map((c: Any) => [day(c.close_date), ACCOUNT[c.account], money(c.expected), money(c.counted), money(c.difference), c.reason])} />
      </Section>

      <Section title="3. Owed to us and by us">
        <Grid head={["Customers owe us", "Amount"]} right={[1]} rows={[...Object.entries(p.receivables.by_bucket).map(([k, v]) => [`${k} days`, money(v as string)]), [<b key="t">Total</b>, <b key="v">{money(p.receivables.total)}</b>]]} />
        <Grid head={["We owe vendors", "Amount"]} right={[1]} rows={[...Object.entries(p.payables.by_bucket).map(([k, v]) => [k, money(v as string)]), [<b key="t">Total</b>, <b key="v">{money(p.payables.total)}</b>]]} />
        <p>Stock at cost: <b>{money(p.stock.total)}</b></p>
      </Section>

      <Section title="4. Every payment, with its proof">
        <Grid head={["Date", "Record", "Kind", "From or to", "Account", "Proof", "Amount"]} right={[6]}
              rows={p.entries.map((e: Any) => [day(e.date), e.number, `${e.direction === "in" ? "In" : "Out"}: ${SOURCE[e.source] ?? e.source}`, e.party, ACCOUNT[e.account],
                e.proof_url ? "Attached" : e.signoff ? `Accepted: ${e.signoff.reason}` : `None: ${e.no_proof_reason}`, money(e.amount)])} />
      </Section>

      {p.payroll.length > 0 && <Section title="5. Payroll"><Grid head={["Month", "Status", "Pay for the month", "Paid out"]} right={[2, 3]} rows={p.payroll.map((r: Any) => [r.month, r.status, money(r.gross), money(r.net)])} /></Section>}

      <div className="mt-10 grid grid-cols-2 gap-10">
        <div><div className="h-10 border-b border-ink" /><p>Prepared by</p></div>
        <div><div className="h-10 border-b border-ink" /><p>Approved by, owner</p></div>
      </div>
    </div>
  );
}
