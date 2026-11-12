"use client";

import Link from "next/link";
import { Suspense } from "react";
import { ExportButton, Line, periodLabel, rangeQuery, type Range, Stat, useRange } from "@/components/reports";
import { Segments, useQueryParam } from "@/components/search";
import { RequirePermission } from "@/components/shell";
import { SortTh, sortRows, useTableSort } from "@/components/sort";
import { Badge, Card, EmptyState, ErrorState, PageHeader, SkeletonRows } from "@/components/ui";
import { useApi } from "@/lib/api";
import { day, money, qty } from "@/lib/format";
import { asAmount, reportSheet } from "@/lib/report-xlsx";
import { useSession } from "@/lib/session";
import type { Cell } from "@/lib/xlsx";

const TABS = [
  ["pnl", "Profit and loss"], ["cashflow", "Cash flow"], ["journal", "Journal"],
  ["receivables", "Customers owe us"], ["payables", "We owe vendors"], ["stock", "Inventory asset"], ["discounts", "Discounts and voids"],
];
const ACCOUNT: Record<string, string> = { cash: "Cash", bank: "Bank", wallet: "Mobile wallet" };
const SOURCE: Record<string, string> = {
  payment: "Customer payments and advances", vendor_payment: "Vendor payments", money_entry: "Other money in and out",
  account_opening: "Opening balance", cash_close: "Cash count differences", stock_movement: "Stock", invoice: "Invoices",
  goods_receipt: "Goods received", vendor_bill: "Vendor bills", credit_note: "Credit notes", payroll: "Payroll", other: "Other",
};

export default function FinanceReports() {
  return (
    <RequirePermission permission="reports-finance">
      <PageHeader title="Finance reports" description="Every figure is worked out from the books. Click a line to see the records behind it. Download for Excel makes a real spreadsheet." />
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
  const dated = ["pnl", "cashflow", "journal", "discounts"].includes(t);
  return (
    <div className="space-y-4">
      <div className="overflow-x-auto"><Segments value={t} onChange={setTab} options={TABS.map(([value, label]) => ({ value, label }))} /></div>
      {dated && control}
      {t === "pnl" && <Pnl range={range} />}
      {t === "cashflow" && <Cashflow range={range} />}
      {t === "journal" && <Journal range={range} />}
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

type Pnl = { revenue: { labour: string; parts: string; other: string; total: string; before_discounts: string; discounts: string };
  advances: { received: string; refunded: string; applied: string; held_at_end: string };
  inventory: { opening: string; purchased: string; issued: string; returned: string; adjusted: string; closing: string };
  cost_of_parts_sold: string; gross_profit: string; gross_margin_pct: number | null;
  expenses_by_category: Record<string, string>; other_costs: Record<string, string>; total_expenses: string; net_profit: string; sales_tax_collected: string };

function Pnl({ range }: { range: Range }) {
  const { branch } = useSession();
  const q = `from=${range.from}&to=${range.to}`;
  const period = periodLabel(range);
  return (
    <Load<Pnl> path={`/api/reports/pnl?${rangeQuery(range)}`}>
      {(p) => {
        const hasDisc = Number(p.revenue.discounts) !== 0;
        const hasAdv = Number(p.advances.received) !== 0 || Number(p.advances.refunded) !== 0 || Number(p.advances.applied) !== 0 || Number(p.advances.held_at_end) !== 0;
        const inv = p.inventory;
        const statementRows: [string, string][] = [
          ...(hasDisc
            ? ([
                ["Revenue before discounts", p.revenue.before_discounts],
                ["Discounts given", `-${p.revenue.discounts}`],
                ["Revenue", p.revenue.total],
              ] as [string, string][])
            : ([["Revenue", p.revenue.total]] as [string, string][])),
          ...(Number(p.revenue.other) !== 0
            ? ([["Other income (in revenue)", p.revenue.other]] as [string, string][])
            : []),
          ["Cost of parts sold", `-${p.cost_of_parts_sold}`], ["Gross profit", p.gross_profit],
          ...Object.entries(p.expenses_by_category).map(([k, v]) => [k, `-${v}`] as [string, string]),
          ...Object.entries(p.other_costs).map(([k, v]) => [k, `-${v}`] as [string, string]),
          ["Total expenses", `-${p.total_expenses}`], ["Net profit", p.net_profit],
          ...(hasAdv ? ([
            ["Advances received (not income)", p.advances.received],
            ["Advances refunded", `-${p.advances.refunded}`],
            ["Advances applied to invoices", `-${p.advances.applied}`],
            ["Advances still held at period end", p.advances.held_at_end],
          ] as [string, string][]) : []),
        ];
        const invRows: [string, string][] = [
          ["At the start (asset)", inv.opening], ["Purchased into stock (still an asset)", inv.purchased],
          ["Installed or sold (expense)", `-${inv.issued}`],
          ...(Number(inv.returned) !== 0 ? [["Returned to stock", inv.returned]] as [string, string][] : []),
          ...(Number(inv.adjusted) !== 0 ? [["Adjustments", inv.adjusted]] as [string, string][] : []),
          ["At the end (asset)", inv.closing],
        ];
        const meta = { branch: branch.name, period };
        const sheets = [
          reportSheet("Statement", { title: "Profit and loss", ...meta }, ["Line", "Amount"], statementRows.map(([l, a]) => [l, asAmount(a)])),
          reportSheet("Inventory asset", { title: "Inventory asset movement", ...meta }, ["Line", "Amount"], invRows.map(([l, a]) => [l, asAmount(a)])),
        ];
        return (
        <>
          <div className="grid gap-4 sm:grid-cols-2 shell:grid-cols-4">
            <Stat label="Revenue" value={money(p.revenue.total)} hint={hasDisc ? `Before discounts ${money(p.revenue.before_discounts)}` : undefined} />
            <Stat label="Gross profit" value={money(p.gross_profit)} hint={p.gross_margin_pct != null ? `${p.gross_margin_pct.toFixed(0)}% of revenue` : undefined} />
            <Stat label="Net profit" value={money(p.net_profit)} tone={Number(p.net_profit) < 0 ? "error" : "success"} />
            <Stat label="Inventory asset" value={money(inv.closing)} hint={`Purchased ${money(inv.purchased)} · Issued ${money(inv.issued)}`} href="/reports/finance?r=stock" />
          </div>
          <Card title="Inventory asset (parts on the shelf)" actions={<ExportButton name={`inventory-asset-${range.from}-to-${range.to}`} title="Inventory asset movement" period={period} headers={["Line", "Amount"]} rows={invRows} ledgerRange={range} />}>
            <dl>
              <Line label="At the start" value={inv.opening} href="/reports/finance?r=stock" />
              <Line label="Purchased into stock" value={inv.purchased} href="/purchase-orders" indent />
              <Line label="Installed or sold (expense)" value={`-${inv.issued}`} href="/inventory" indent />
              {Number(inv.returned) !== 0 && <Line label="Returned to stock" value={inv.returned} indent />}
              {Number(inv.adjusted) !== 0 && <Line label="Adjustments" value={inv.adjusted} href="/inventory" indent />}
              <Line label="At the end (asset on hand)" value={inv.closing} strong href="/reports/finance?r=stock" />
            </dl>
            <p className="mt-3 text-sm text-muted">Buying parts does not hit expense — they sit as Inventory asset. Expense (Cost of parts sold) is only when a part is installed on a car or sold over the counter, in that month.</p>
          </Card>
          <Card title="Statement" actions={<ExportButton name={`profit-and-loss-${range.from}-to-${range.to}`} sheets={sheets} ledgerRange={range} />}>
            <dl>
              {hasDisc && <Line label="Revenue before discounts" value={p.revenue.before_discounts} href="/invoices" indent />}
              {hasDisc && <Line label="Discounts given" value={`-${p.revenue.discounts}`} href={`/reports/finance?r=discounts&from=${range.from}&to=${range.to}`} indent />}
              <Line label="Revenue" value={p.revenue.total} strong href="/invoices" />
              {Number(p.revenue.other) !== 0 && <Line label="Other income (included above)" value={p.revenue.other} href={`/money-in?source=other_income&${q}`} indent />}
              <Line label="Cost of parts sold" value={`-${p.cost_of_parts_sold}`} href="/inventory" indent />
              <Line label="Gross profit" value={p.gross_profit} strong />
              {Object.entries(p.expenses_by_category).map(([k, v]) => <Line key={k} label={k} value={`-${v}`} href={`/money-out?source=expense&${q}`} indent />)}
              {Object.entries(p.other_costs).map(([k, v]) => <Line key={k} label={k} value={`-${v}`} href={k.startsWith("Salaries") ? "/payroll" : undefined} indent />)}
              <Line label="Total expenses" value={`-${p.total_expenses}`} strong />
              <Line label="Net profit" value={p.net_profit} strong />
              {hasAdv && (
                <>
                  <Line label="Advances received this month" value={p.advances.received} href="/money-in?source=advance" indent />
                  {Number(p.advances.refunded) !== 0 && <Line label="Advances refunded" value={`-${p.advances.refunded}`} href="/money-out?source=refund" indent />}
                  {Number(p.advances.applied) !== 0 && <Line label="Advances applied to invoices" value={`-${p.advances.applied}`} href="/invoices" indent />}
                  <Line label="Advances still held" value={p.advances.held_at_end} indent />
                </>
              )}
            </dl>
            <p className="mt-4 text-sm text-muted">Sales tax collected for the government, {money(p.sales_tax_collected)}, is not income and isn&apos;t counted above. Discounts sit in the same month the invoice was issued. Advances are listed for the month they were taken; they are not income until the invoice is issued. Labour vs parts is on the Workshop report.</p>
          </Card>
        </>
        );
      }}
    </Load>
  );
}

type Cash = { accounts: Record<string, { opening: string; in: string; out: string; closing: string; in_by_source: Record<string, string>; out_by_source: Record<string, string> }>;
  opening: string; in: string; out: string; closing: string };

function Cashflow({ range }: { range: Range }) {
  const { branch } = useSession();
  const period = periodLabel(range);
  return (
    <Load<Cash> path={`/api/reports/cashflow?${rangeQuery(range)}`}>
      {(c) => {
        const summary = [
          ["At the start", c.opening], ["Came in", c.in], ["Went out", `-${c.out}`], ["At the end", c.closing],
        ];
        const byAccount: Cell[][] = [];
        for (const [k, a] of Object.entries(c.accounts)) {
          const account = ACCOUNT[k] ?? k;
          byAccount.push([account, "At the start", asAmount(a.opening)]);
          byAccount.push([account, "Came in", asAmount(a.in)]);
          for (const [s, v] of Object.entries(a.in_by_source)) byAccount.push([account, `  In: ${SOURCE[s] ?? s}`, asAmount(v)]);
          byAccount.push([account, "Went out", asAmount(`-${a.out}`)]);
          for (const [s, v] of Object.entries(a.out_by_source)) byAccount.push([account, `  Out: ${SOURCE[s] ?? s}`, asAmount(`-${v}`)]);
          byAccount.push([account, "At the end", asAmount(a.closing)]);
        }
        const meta = { branch: branch.name, period };
        const sheets = [
          reportSheet("Summary", { title: "Cash flow", ...meta }, ["Line", "Amount"], summary.map(([l, a]) => [l, asAmount(a)])),
          reportSheet("By account", { title: "Cash flow by account", ...meta }, ["Account", "Line", "Amount"], byAccount),
        ];
        return (
        <>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="grid flex-1 gap-4 sm:grid-cols-4">
              <Stat label="At the start" value={money(c.opening)} hint="Each period starts at zero" />
              <Stat label="Came in" value={money(c.in)} href="/money-in" />
              <Stat label="Went out" value={money(c.out)} href="/money-out" />
              <Stat label="At the end" value={money(c.closing)} hint="This period only (in − out)" />
            </div>
            <ExportButton name={`cash-flow-${range.from}-to-${range.to}`} sheets={sheets} ledgerRange={range} />
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
          <p className="text-sm text-muted">At the start is always 0 so a new month begins clean — last month&apos;s figures stay on last month&apos;s cash flow. This report does not bring prior balances into the month.</p>
        </>
        );
      }}
    </Load>
  );
}

type LedgerRow = {
  date: string; entry_number: string; memo: string; source_type: string | null;
  account_code: string; account_name: string; debit: string; credit: string; category: string | null;
};
type Ledger = { from: string; to: string; rows: LedgerRow[]; debit: string; credit: string; truncated: boolean };

function Journal({ range }: { range: Range }) {
  const ledger = useApi<Ledger>(`/api/journal/ledger?${rangeQuery(range)}`);

  if (ledger.error) return <Card flush><ErrorState message={ledger.error} onRetry={ledger.reload} /></Card>;
  if (!ledger.data) return <Card flush><SkeletonRows rows={8} /></Card>;
  const d = ledger.data;

  return (
    <>
      <div className="grid gap-4 sm:grid-cols-3">
        <Stat label="Journal lines" value={d.rows.length} hint={d.truncated ? "Export capped — narrow the dates" : undefined} />
        <Stat label="Total debits" value={money(d.debit)} />
        <Stat label="Total credits" value={money(d.credit)} />
      </div>
      {d.truncated && <p className="text-sm text-warning">Showing the first {d.rows.length} lines. Narrow the period for a complete export.</p>}
      <Card
        title="Month ledger"
        actions={<ExportButton name={`month-ledger-${range.from}-to-${range.to}`} ledgerRange={range} />}
        flush
      >
        {!d.rows.length ? (
          <EmptyState title="No journal entries in this period">Money and stock movements in this date range will appear here.</EmptyState>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-muted">
                  <th className="px-4 py-2 font-normal shell:px-5">Date</th>
                  <th className="px-3 py-2 font-normal">Voucher</th>
                  <th className="px-3 py-2 font-normal">Particulars</th>
                  <th className="px-3 py-2 font-normal">Account</th>
                  <th className="px-3 py-2 text-right font-normal">Debit</th>
                  <th className="px-4 py-2 text-right font-normal shell:pr-5">Credit</th>
                </tr>
              </thead>
              <tbody>
                {d.rows.map((r, i) => (
                  <tr key={`${r.entry_number}-${r.account_code}-${i}`} className="border-t border-rule">
                    <td className="whitespace-nowrap px-4 py-2 shell:px-5">{day(r.date)}</td>
                    <td className="num whitespace-nowrap px-3 py-2">{r.entry_number}</td>
                    <td className="px-3 py-2">
                      <span className="block">{r.memo || "—"}</span>
                      <span className="text-muted">{r.source_type ? (SOURCE[r.source_type] ?? r.source_type) : ""}{r.category ? ` · ${r.category}` : ""}</span>
                    </td>
                    <td className="px-3 py-2"><span className="num">{r.account_code}</span> {r.account_name}</td>
                    <td className="num px-3 py-2 text-right">{Number(r.debit) ? money(r.debit) : ""}</td>
                    <td className="num px-4 py-2 text-right shell:pr-5">{Number(r.credit) ? money(r.credit) : ""}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="border-t-2 border-ink font-medium">
                  <td className="px-4 py-2 shell:px-5" colSpan={4}>Total</td>
                  <td className="num px-3 py-2 text-right">{money(d.debit)}</td>
                  <td className="num px-4 py-2 text-right shell:pr-5">{money(d.credit)}</td>
                </tr>
              </tfoot>
            </table>
          </div>
        )}
      </Card>
      <p className="text-sm text-muted">Download for Excel gives the accountant: Month journal (every voucher line), General ledger by account with running balance, and Trial balance as of the period end. P&amp;L and Cash flow downloads include those ledger sheets first, then the summary.</p>
    </>
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
          <AgingTable rec={rec} asOf={r.as_of} kind={kind} names={names} rows={r.rows} />
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
          <div className="grid gap-4 sm:grid-cols-3">
            <Stat label="Inventory asset at cost" value={money(s.total)} hint="Parts on the shelf — an asset, not an expense" />
            <Stat label="Items in stock" value={s.items.length} href="/inventory" />
            <Stat label="Low on stock" value={s.low_stock} tone={s.low_stock ? "warning" : undefined} href="/inventory?stock=low" />
          </div>
          <p className="text-sm text-muted">Purchases increase this asset. When a part is installed on a car or sold at the counter, its cost leaves the asset and becomes Cost of parts sold (expense) in that month — see Profit and loss.</p>
          <StockTable items={s.items} total={s.total} />
        </>
      )}
    </Load>
  );
}

function AgingTable({ rec, asOf, kind, names, rows }: {
  rec: boolean; asOf: string; kind: "receivables" | "payables"; names: Record<string, string>; rows: Rec["rows"];
}) {
  const { sort, set } = useTableSort();
  const sorted = sortRows(rows, sort, {
    number: (x) => x.number,
    party: (x) => x.customer ?? x.vendor ?? "",
    date: (x) => x.issued_on ?? x.due_on ?? "",
    age: (x) => x.bucket,
    balance: (x) => Number(x.balance),
  });
  return (
    <Card title={rec ? "Unpaid invoices" : "Unpaid bills"} actions={rows.length ? <ExportButton
      name={`${kind}-${asOf}`}
      title={rec ? "Customers owe us" : "We owe vendors"}
      period={`As of ${asOf}`}
      headers={[rec ? "Invoice" : "Bill", rec ? "Customer" : "Vendor", rec ? "Issued" : "Due", "Age", "Balance"]}
      rows={rows.map((x) => [x.number, x.customer ?? x.vendor, x.issued_on ?? x.due_on, names[x.bucket] ?? x.bucket, x.balance])}
    /> : undefined} flush>
      {!rows.length ? <EmptyState title="Nothing outstanding">{rec ? "Every invoice is settled." : "Every bill is paid and every delivery is billed."}</EmptyState> : (
        <table className="table-stack w-full">
          <thead><tr className="text-left text-sm text-muted">
            <SortTh label={rec ? "Invoice" : "Bill or receipt"} k="number" sort={sort} onSort={set} className="px-4 py-2 font-normal shell:px-5" />
            <SortTh label={rec ? "Customer" : "Vendor"} k="party" sort={sort} onSort={set} className="px-4 py-2 font-normal" />
            <SortTh label={rec ? "Issued" : "Due"} k="date" sort={sort} onSort={set} className="px-4 py-2 font-normal" />
            <SortTh label="Age" k="age" sort={sort} onSort={set} className="px-4 py-2 font-normal" />
            <SortTh label="Balance" k="balance" sort={sort} onSort={set} align="right" className="px-4 py-2 text-right font-normal shell:pr-5" />
          </tr></thead>
          <tbody>
            {sorted.map((x) => (
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
  );
}

function StockTable({ items, total }: { items: Stk["items"]; total: string }) {
  const { sort, set } = useTableSort();
  const sorted = sortRows(items, sort, {
    name: (i) => i.name,
    on_hand: (i) => Number(i.on_hand),
    avg_cost: (i) => Number(i.avg_cost),
    value: (i) => Number(i.value),
  });
  return (
    <Card title="Asset by item" actions={<ExportButton
      name="inventory-asset"
      title="Inventory asset by item"
      headers={["Item", "Number", "On hand", "Unit", "Average cost", "Asset value"]}
      rows={items.map((i) => [i.name, i.number, i.on_hand, i.unit, i.avg_cost, i.value])}
      amountCols={[2, 4, 5]}
    />} flush>
      <table className="table-stack w-full">
        <thead><tr className="text-left text-sm text-muted">
          <SortTh label="Item" k="name" sort={sort} onSort={set} className="px-4 py-2 font-normal shell:px-5" />
          <SortTh label="On hand" k="on_hand" sort={sort} onSort={set} align="right" className="px-4 py-2 text-right font-normal" />
          <SortTh label="Average cost" k="avg_cost" sort={sort} onSort={set} align="right" className="px-4 py-2 text-right font-normal" />
          <SortTh label="Asset value" k="value" sort={sort} onSort={set} align="right" className="px-4 py-2 text-right font-normal shell:pr-5" />
        </tr></thead>
        <tbody>
          {sorted.map((i) => (
            <tr key={i.id} className="border-t border-rule">
              <td className="px-4 py-3 shell:px-5 max-sm:px-0"><Link href={`/inventory/${i.id}`} className="font-medium underline">{i.name}</Link><span className="block text-sm text-muted">{i.number}{i.low ? ", low" : ""}</span></td>
              <td data-label="On hand" className="num px-4 py-3 text-right max-sm:px-0">{qty(i.on_hand)} {i.unit}</td>
              <td data-label="Average cost" className="num px-4 py-3 text-right max-sm:px-0">{money(i.avg_cost)}</td>
              <td data-label="Asset value" className="num px-4 py-3 text-right shell:pr-5 max-sm:px-0">{money(i.value)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="border-t border-rule px-4 py-3 text-sm text-muted shell:px-5">Total asset value {money(total)}</p>
    </Card>
  );
}

type Disc = { discount_total: string; discounts_by_user: Record<string, string>; discounts: { id: string; number: string; by: string | null; discount: string }[]; voids: { kind: string; number: string; amount: string; reason: string }[] };

function Discounts({ range }: { range: Range }) {
  const { branch } = useSession();
  const period = periodLabel(range);
  return (
    <Load<Disc> path={`/api/reports/discounts?${rangeQuery(range)}`}>
      {(d) => {
        const meta = { branch: branch.name, period };
        const sheets = [
          reportSheet("Discounts", { title: "Discounts given", ...meta }, ["Invoice", "By", "Discount"],
            d.discounts.map((x) => [x.number, x.by ?? "", asAmount(x.discount)]),
            { totalRow: ["", "Total", asAmount(d.discount_total)] }),
          reportSheet("Voids", { title: "Voided records", ...meta }, ["Kind", "Number", "Amount", "Reason"],
            d.voids.map((v) => [v.kind, v.number, asAmount(v.amount), v.reason])),
        ];
        return (
        <div className="space-y-4">
          <div className="flex justify-end"><ExportButton name={`discounts-voids-${range.from}-to-${range.to}`} sheets={sheets} ledgerRange={range} /></div>
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
        </div>
        );
      }}
    </Load>
  );
}
