"use client";

import Link from "next/link";
import { MyWork } from "@/components/my-work";
import { Stat, StatGroup } from "@/components/reports";
import { Card, ErrorState, PageHeader, SkeletonRows } from "@/components/ui";
import { useApi } from "@/lib/api";
import { money } from "@/lib/format";
import { useSession } from "@/lib/session";

type Dash = {
  workshop: { cars_in: number; open_quotes: number; quotes_waiting: number; repair_orders: number; ready_for_pickup: number; on_hold: number };
  stock: { low_stock: number; items: number };
  money?: { cash: Record<string, string>; cash_total: string; money_in_month: string; money_out_month: string; revenue_month: string; profit_month: string;
    receivables: string; overdue_receivables: string; payables: string; overdue_payables: string; stock_value: string };
  alerts?: { missing_proof: number; unclosed_months: string[]; low_stock: number; overdue_bills: number; overdue_invoices: number };
};
const ACCOUNT: Record<string, string> = { cash: "Cash", bank: "Bank", wallet: "Wallet" };
const monthName = (m: string) => new Date(`${m}-01`).toLocaleDateString("en-PK", { month: "long", year: "numeric" });

export default function Dashboard() {
  const { branch, can } = useSession();
  const d = useApi<Dash>("/api/dashboard");
  if (d.error) return <Card flush><ErrorState message={d.error} onRetry={d.reload} /></Card>;
  if (!d.data) return <Card flush><SkeletonRows rows={6} /></Card>;
  const { workshop: w, money: m, alerts: a } = d.data;
  const overview = can("visits") || can("reports-ops") || can("reports-finance") || can("inventory");
  const todo: [string, string, string][] = a ? [
    ...(a.missing_proof ? [[`${a.missing_proof} payment${a.missing_proof === 1 ? "" : "s"} with no proof`, "/missing-evidence", "Waiting for an admin to accept them"] as [string, string, string]] : []),
    ...(a.overdue_invoices ? [[`${a.overdue_invoices} invoice${a.overdue_invoices === 1 ? "" : "s"} unpaid for over 30 days`, "/reports/finance?r=receivables", "Customers who owe us"] as [string, string, string]] : []),
    ...(a.overdue_bills ? [[`${a.overdue_bills} vendor bill${a.overdue_bills === 1 ? "" : "s"} past due`, "/bills?status=overdue", "We owe these"] as [string, string, string]] : []),
    ...(a.low_stock ? [[`${a.low_stock} item${a.low_stock === 1 ? "" : "s"} at or below the reorder level`, "/inventory?stock=low", "Time to order"] as [string, string, string]] : []),
    ...(a.unclosed_months.length ? [[`${monthName(a.unclosed_months[0])} is not closed${a.unclosed_months.length > 1 ? `, and ${a.unclosed_months.length - 1} more` : ""}`, "/periods", "Month-end closing"] as [string, string, string]] : []),
  ] : (d.data.stock.low_stock ? [[`${d.data.stock.low_stock} item${d.data.stock.low_stock === 1 ? "" : "s"} at or below the reorder level`, "/inventory?stock=low", "Time to order"]] : []);

  return (
    <>
      <PageHeader title="Dashboard"
        description={`${branch.name}. ${todo.length ? `${todo[0][0]}${todo.length > 1 ? `, and ${todo.length - 1} more thing${todo.length > 2 ? "s" : ""} to look at` : ""}.` : "Everything is up to date."}`}
        actions={can("visits") ? <Link href="/visits/new" className="flex min-h-11 items-center rounded-control bg-accent px-5 font-medium text-accent-ink hover:bg-accent-2 active:bg-accent-3 active:duration-0">Check in a car</Link> : undefined} />

      <h2 className="mb-2">My work</h2>
      <div className="mb-6"><MyWork /></div>

      {overview && <>
      <section aria-label="Needs attention" className="mb-4">
        <Card title="Needs attention" flush>
          {!todo.length ? <p className="px-4 py-4 text-success shell:px-5">Nothing needs attention.</p> : (
            <ul>
              {todo.map(([text, href, hint]) => (
                <li key={text}>
                  <Link href={href} className="row-link flex min-h-14 flex-col justify-center border-t border-rule px-4 py-2.5 pr-10 first:border-t-0 hover:bg-paper-2 shell:px-5 shell:pr-12">
                    <span className="font-medium">{text}</span><span className="text-sm text-muted">{hint}</span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </section>

      <h2 className="mb-2">In the workshop</h2>
      <div className="mb-6"><StatGroup>
        <Stat label="Cars in the workshop" value={w.cars_in} href="/visits" />
        <Stat label="Quotations open" value={w.open_quotes} hint={`${w.quotes_waiting} waiting for the customer`} href="/quotations?status=sent" />
        <Stat label="Repair orders under way" value={w.repair_orders} hint={`${w.ready_for_pickup} ready, ${w.on_hold} on hold`} href="/repair-orders" />
        <Stat label="Low on stock" value={d.data.stock.low_stock} hint={`of ${d.data.stock.items} items`} href="/inventory?stock=low" tone={d.data.stock.low_stock ? "warning" : undefined} />
      </StatGroup></div>

      {m && (
        <>
          <h2 className="mb-2">Money this month</h2>
          <div className="mb-6"><StatGroup>
            <Stat label="Revenue" value={money(m.revenue_month)} href="/reports/finance?r=pnl" />
            <Stat label="Profit" value={money(m.profit_month)} hint="Revenue less cost of parts and expenses" href="/reports/finance?r=pnl" tone={Number(m.profit_month) < 0 ? "error" : undefined} />
            <Stat label="Money in" value={money(m.money_in_month)} href="/money-in" />
            <Stat label="Money out" value={money(m.money_out_month)} href="/money-out" />
          </StatGroup></div>
          <h2 className="mb-2">Where the money is</h2>
          <div className="mb-6"><StatGroup>
            <Stat label="Cash, bank and wallet" value={money(m.cash_total)} hint={Object.entries(m.cash).map(([k, v]) => `${ACCOUNT[k]} ${money(v)}`).join(", ")} href="/reports/finance?r=cashflow" />
            <Stat label="Customers owe us" value={money(m.receivables)} hint={Number(m.overdue_receivables) ? `${money(m.overdue_receivables)} over 30 days` : "Nothing overdue"} href="/reports/finance?r=receivables" tone={Number(m.overdue_receivables) ? "warning" : undefined} />
            <Stat label="We owe vendors" value={money(m.payables)} hint={Number(m.overdue_payables) ? `${money(m.overdue_payables)} past due` : "Nothing past due"} href="/reports/finance?r=payables" tone={Number(m.overdue_payables) ? "warning" : undefined} />
            <Stat label="Stock at cost" value={money(m.stock_value)} href="/reports/finance?r=stock" />
          </StatGroup></div>
        </>
      )}
      </>}
    </>
  );
}
