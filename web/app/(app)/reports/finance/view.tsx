"use client";

import Link from "next/link";
import { Suspense } from "react";
import { ExportButton, Line, rangeQuery, type Range, Stat, useRange } from "@/components/reports";
import { Segments, useQueryParam } from "@/components/search";
import { RequirePermission } from "@/components/shell";
import { Badge, Card, EmptyState, ErrorState, PageHeader, SkeletonRows } from "@/components/ui";
import { useApi } from "@/lib/api";
import { day, money, qty } from "@/lib/format";

const TABS = [["pnl", "Profit and loss"], ["cashflow", "Cash flow"], ["receivables", "Customers owe us"], ["payables", "We owe vendors"], ["stock", "Stock value"], ["discounts", "Discounts and voids"]];
const ACCOUNT: Record<string, string> = { cash: "Cash", bank: "Bank", wallet: "Mobile wallet" };
const SOURCE: Record<string, string> = { payment: "Customer payments and advances", vendor_payment: "Vendor payments", money_entry: "Other money in and out", account_opening: "Opening balance",
  cash_close: "Cash count differences", stock_movement: "Stock", invoice: "Invoices", other: "Other" };

export default function FinanceReports() {
  return (
    <RequirePermission permission="reports-finance">
      <PageHeader title="Finance reports" description="Every figure is worked out from the books. Click a line to see the records behind it." />
      <Suspense fallback={<Card flush><SkeletonRows /></Card>}>
        <Body />
      </Suspense>
    </RequirePermission>
  );
}

function Body() {
  const [tab, setTab] = useQueryParam("r");
  const [range, control] = useRange();
  const t = tab || "pnl";
  const dated = ["pnl", "cashflow", "discounts"].includes(t);
  return (
    <div className="space-y-4">
      <div className="overflow-x-auto"><Segments value={t} onChange={setTab} options={TABS.map(([value, label]) => ({ value, label }))} /></div>
      {dated && control}
      {t === "pnl" && <Pnl range={range} />}
      {t === "cashflow" && <Cashflow range={range} />}
      {t === "receivables" && <Aging kind="receivables" />}
      {t === "payables" && <Aging kind="payables" />}
      {t === "stock" && <Stock />}
      {t === "discounts" && <Discounts range={range} />}
    </div>
  );
}

function Load<T>({ path, children }: { path: string; children: (d: T) => React.ReactNode }) {
  const r = useApi<T>(path);
  if (r.error) return <Card flush><ErrorState message={r.error} onRetry={r.reload} /></Card>;
  if (!r.data) return <Card flush><SkeletonRows rows={6} /></Card>;
  return <>{children(r.data)}</>;
}

type Pnl = { revenue: { labour: string; parts: string; other: string; total: string }; cost_of_parts_sold: string; gross_profit: string; gross_margin_pct: number | null;
  expenses_by_category: Record<string, string>; other_costs: Record<string, string>; total_expenses: string; net_profit: string; sales_tax_collected: string };

function Pnl({ range }: { range: Range }) {
  const q = `from=${range.from}&to=${range.to}`;
  return (
    <Load<Pnl> path={`/api/reports/pnl?${rangeQuery(range)}`}>
      {(p) => (
        <>
          <div className="grid gap-4 sm:grid-cols-3">
            <Stat label="Revenue" value={money(p.revenue.total)} />
            <Stat label="Gross profit" value={money(p.gross_profit)} hint={p.gross_margin_pct != null ? `${p.gross_margin_pct.toFixed(0)}% of revenue` : undefined} />
            <Stat label="Net profit" value={money(p.net_profit)} tone={Number(p.net_profit) < 0 ? "error" : "success"} />
          </div>
          <Card title="Statement" actions={<ExportButton name={`profit-and-loss-${range.from}-to-${range.to}`} headers={["Line", "Amount"]}
            rows={[["Revenue: labour", p.revenue.labour], ["Revenue: parts", p.revenue.parts], ["Other income", p.revenue.other], ["Total revenue", p.revenue.total], ["Cost of parts sold", p.cost_of_parts_sold],
              ["Gross profit", p.gross_profit], ...Object.entries(p.expenses_by_category).map(([k, v]) => [k, v]), ...Object.entries(p.other_costs).map(([k, v]) => [k, v]), ["Total expenses", p.total_expenses], ["Net profit", p.net_profit]]} />}>
            <dl>
              <Line label="Revenue: labour" value={p.revenue.labour} href={`/invoices?kind=workshop`} indent />
              <Line label="Revenue: parts" value={p.revenue.parts} href="/invoices" indent />
              {Number(p.revenue.other) !== 0 && <Line label="Other income" value={p.revenue.other} href={`/money-in?source=other_income&${q}`} indent />}
              <Line label="Total revenue" value={p.revenue.total} strong />
              <Line label="Cost of parts sold" value={`-${p.cost_of_parts_sold}`} href="/inventory" indent />
              <Line label="Gross profit" value={p.gross_profit} strong />
              {Object.entries(p.expenses_by_category).map(([k, v]) => <Line key={k} label={k} value={`-${v}`} href={`/money-out?source=expense&${q}`} indent />)}
              {Object.entries(p.other_costs).map(([k, v]) => <Line key={k} label={k} value={`-${v}`} href={k.startsWith("Salaries") ? "/payroll" : undefined} indent />)}
              <Line label="Total expenses" value={`-${p.total_expenses}`} strong />
              <Line label="Net profit" value={p.net_profit} strong />
            </dl>
            <p className="mt-4 text-sm text-muted">Sales tax collected for the government, {money(p.sales_tax_collected)}, is not income and isn&apos;t counted above.</p>
          </Card>
        </>
      )}
    </Load>
  );
}

type Cash = { accounts: Record<string, { opening: string; in: string; out: string; closing: string; in_by_source: Record<string, string>; out_by_source: Record<string, string> }>;
  opening: string; in: string; out: string; closing: string };

function Cashflow({ range }: { range: Range }) {
  return (
    <Load<Cash> path={`/api/reports/cashflow?${rangeQuery(range)}`}>
      {(c) => (
        <>
          <div className="grid gap-4 sm:grid-cols-4">
            <Stat label="At the start" value={money(c.opening)} /><Stat label="Came in" value={money(c.in)} href="/money-in" /><Stat label="Went out" value={money(c.out)} href="/money-out" /><Stat label="At the end" value={money(c.closing)} />
          </div>
          <div className="grid gap-4 shell:grid-cols-3">
            {Object.entries(c.accounts).map(([k, a]) => (
              <Card key={k} title={ACCOUNT[k]}>
                <dl>
                  <Line label="At the start" value={a.opening} />
                  <Line label="Came in" value={a.in} href={`/money-in?account=${k}&from=${range.from}&to=${range.to}`} />
                  {Object.entries(a.in_by_source).map(([s, v]) => <Line key={s} label={SOURCE[s] ?? s} value={v} indent />)}
                  <Line label="Went out" value={`-${a.out}`} href={`/money-out?account=${k}&from=${range.from}&to=${range.to}`} />
                  {Object.entries(a.out_by_source).map(([s, v]) => <Line key={s} label={SOURCE[s] ?? s} value={`-${v}`} indent />)}
                  <Line label="At the end" value={a.closing} strong />
                </dl>
              </Card>
            ))}
          </div>
        </>
      )}
    </Load>
  );
}

type Rec = { as_of: string; total: string; by_bucket: Record<string, string>; rows: { id: string; number: string; customer: string; vendor?: string; kind?: string; purchase_order_id?: string; issued_on?: string; due_on?: string; days?: number; days_overdue?: number; bucket: string; balance: string }[] };

function Aging({ kind }: { kind: "receivables" | "payables" }) {
  const rec = kind === "receivables";
  const order = rec ? ["0-30", "31-60", "61-90", "90+", "credit"] : ["not billed", "not yet due", "0-30", "31-60", "61-90", "90+"];
  const names: Record<string, string> = { "0-30": rec ? "0 to 30 days" : "1 to 30 days late", "31-60": rec ? "31 to 60 days" : "31 to 60 days late", "61-90": rec ? "61 to 90 days" : "61 to 90 days late", "90+": rec ? "Over 90 days" : "Over 90 days late", credit: "Owed back to customers", "not yet due": "Not yet due", "not billed": "Received, not billed" };
  return (
    <Load<Rec> path={`/api/reports/${kind}`}>
      {(r) => (
        <>
          <div className="grid gap-4 sm:grid-cols-2 shell:grid-cols-5">
            <Stat label="Total" value={money(r.total)} />
            {order.filter((b) => r.by_bucket[b]).map((b) => <Stat key={b} label={names[b]} value={money(r.by_bucket[b])} tone={["61-90", "90+"].includes(b) ? "warning" : undefined} />)}
          </div>
          <Card title={rec ? "Unpaid invoices" : "Unpaid bills"} actions={r.rows.length ? <ExportButton name={`${kind}-${r.as_of}`} headers={[rec ? "Invoice" : "Bill", rec ? "Customer" : "Vendor", rec ? "Issued" : "Due", "Age", "Balance"]}
            rows={r.rows.map((x) => [x.number, x.customer ?? x.vendor, x.issued_on ?? x.due_on, x.bucket, x.balance])} /> : undefined} flush>
            {!r.rows.length ? <EmptyState title="Nothing outstanding">{rec ? "Every invoice is settled." : "Every bill is paid and every delivery is billed."}</EmptyState> : (
              <table className="table-stack w-full">
                <thead><tr className="text-left text-sm text-muted"><th className="px-4 py-2 font-normal shell:px-5">{rec ? "Invoice" : "Bill or receipt"}</th><th className="px-4 py-2 font-normal">{rec ? "Customer" : "Vendor"}</th>
                  <th className="px-4 py-2 font-normal">{rec ? "Issued" : "Due"}</th><th className="px-4 py-2 font-normal">Age</th><th className="px-4 py-2 text-right font-normal shell:pr-5">Balance</th></tr></thead>
                <tbody>
                  {r.rows.map((x) => (
                    <tr key={x.id} className="border-t border-rule">
                      <td className="px-4 py-3 shell:px-5 max-sm:px-0"><Link href={rec ? `/invoices/${x.id}` : x.kind === "grn" ? `/purchase-orders/${x.purchase_order_id}` : `/bills/${x.id}`} className="font-medium underline">{x.number}</Link></td>
                      <td data-label={rec ? "Customer" : "Vendor"} className="px-4 py-3 max-sm:px-0">{x.customer ?? x.vendor}</td>
                      <td data-label={rec ? "Issued" : "Due"} className="px-4 py-3 max-sm:px-0">{day((x.issued_on ?? x.due_on)!)}</td>
                      <td data-label="Age" className="px-4 py-3 max-sm:px-0"><Badge tone={["61-90", "90+"].includes(x.bucket) ? "error" : x.bucket === "31-60" || x.bucket === "not billed" ? "warning" : "neutral"}>{names[x.bucket]}</Badge></td>
                      <td data-label="Balance" className="num px-4 py-3 text-right shell:pr-5 max-sm:px-0">{money(x.balance)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Card>
        </>
      )}
    </Load>
  );
}

type Stk = { total: string; low_stock: number; items: { id: string; number: string; name: string; unit: string; on_hand: string; value: string; avg_cost: string; low: boolean }[] };

function Stock() {
  return (
    <Load<Stk> path="/api/reports/stock-value">
      {(s) => (
        <>
          <div className="grid gap-4 sm:grid-cols-3"><Stat label="Stock at cost" value={money(s.total)} /><Stat label="Items in stock" value={s.items.length} /><Stat label="Low on stock" value={s.low_stock} tone={s.low_stock ? "warning" : undefined} href="/inventory?stock=low" /></div>
          <Card title="By item" actions={<ExportButton name="stock-value" headers={["Item", "Number", "On hand", "Average cost", "Value"]} rows={s.items.map((i) => [i.name, i.number, i.on_hand, i.avg_cost, i.value])} />} flush>
            <table className="table-stack w-full">
              <thead><tr className="text-left text-sm text-muted"><th className="px-4 py-2 font-normal shell:px-5">Item</th><th className="px-4 py-2 text-right font-normal">On hand</th><th className="px-4 py-2 text-right font-normal">Average cost</th><th className="px-4 py-2 text-right font-normal shell:pr-5">Value</th></tr></thead>
              <tbody>
                {s.items.map((i) => (
                  <tr key={i.id} className="border-t border-rule">
                    <td className="px-4 py-3 shell:px-5 max-sm:px-0"><Link href={`/inventory/${i.id}`} className="font-medium underline">{i.name}</Link><span className="block text-sm text-muted">{i.number}{i.low ? ", low" : ""}</span></td>
                    <td data-label="On hand" className="num px-4 py-3 text-right max-sm:px-0">{qty(i.on_hand)} {i.unit}</td>
                    <td data-label="Average cost" className="num px-4 py-3 text-right max-sm:px-0">{money(i.avg_cost)}</td>
                    <td data-label="Value" className="num px-4 py-3 text-right shell:pr-5 max-sm:px-0">{money(i.value)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        </>
      )}
    </Load>
  );
}

type Disc = { discount_total: string; discounts_by_user: Record<string, string>; discounts: { id: string; number: string; by: string | null; discount: string }[]; voids: { kind: string; number: string; amount: string; reason: string }[] };

function Discounts({ range }: { range: Range }) {
  return (
    <Load<Disc> path={`/api/reports/discounts?${rangeQuery(range)}`}>
      {(d) => (
        <div className="grid gap-4 shell:grid-cols-2">
          <Card title="Discounts given" actions={<span className="num font-medium">{money(d.discount_total)}</span>} flush>
            {!d.discounts.length ? <p className="px-4 py-4 text-muted shell:px-5">No discounts in this period.</p> : (
              <ul>
                {Object.entries(d.discounts_by_user).map(([u, v]) => <li key={u} className="flex justify-between gap-3 border-t border-rule px-4 py-2.5 first:border-t-0 shell:px-5"><span>{u}</span><span className="num">{money(v)}</span></li>)}
                <li className="border-t border-rule px-4 py-2 text-sm font-medium text-ink-2 shell:px-5">Invoices</li>
                {d.discounts.map((x) => <li key={x.id} className="flex justify-between gap-3 border-t border-rule px-4 py-2.5 shell:px-5"><Link href={`/invoices/${x.id}`} className="underline">{x.number}</Link><span className="num">{money(x.discount)}</span></li>)}
              </ul>
            )}
          </Card>
          <Card title="Voided records" flush>
            {!d.voids.length ? <p className="px-4 py-4 text-muted shell:px-5">Nothing was voided in this period.</p> : (
              <ul>{d.voids.map((v) => <li key={v.number} className="border-t border-rule px-4 py-2.5 first:border-t-0 shell:px-5"><div className="flex justify-between gap-3"><span>{v.number} <span className="text-sm text-muted">{v.kind}</span></span><span className="num">{money(v.amount)}</span></div><p className="text-sm text-muted">{v.reason}</p></li>)}</ul>
            )}
          </Card>
        </div>
      )}
    </Load>
  );
}
