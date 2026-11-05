"use client";

import Link from "next/link";
import { CashHero, MonthMoneyCharts, WorkshopKpiCharts } from "@/components/dashboard-charts";
import { HowItWorks } from "@/components/how-it-works";
import { MyWork } from "@/components/my-work";
import { Card, ErrorState, PageHeader, SkeletonRows } from "@/components/ui";
import { useApi } from "@/lib/api";
import { useSession } from "@/lib/session";

type Dash = {
  workshop: { cars_in: number; open_quotes: number; quotes_waiting: number; repair_orders: number; ready_for_pickup: number; on_hold: number };
  stock: { low_stock: number; items: number };
  money?: { cash: Record<string, string>; cash_total: string; money_in_month: string; money_out_month: string; revenue_month: string; profit_month: string;
    receivables: string; overdue_receivables: string; payables: string; overdue_payables: string; stock_value: string };
  alerts?: { missing_proof: number; unclosed_months: string[]; low_stock: number; overdue_bills: number; overdue_invoices: number };
};

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

  const today = new Date().toLocaleDateString("en-PK", { weekday: "long", day: "numeric", month: "long" });

  const needsAttention = (
    <Card flush>
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-rule px-4 py-3 shell:px-5">
        <h2>Needs attention</h2>
        {todo.length > 0 && (
          <span className="inline-flex min-w-7 items-center justify-center rounded-full bg-action px-2 py-0.5 text-sm font-medium text-action-ink">{todo.length}</span>
        )}
      </header>
      {!todo.length ? <p className="px-4 py-4 text-success shell:px-5">Nothing needs attention.</p> : (
        <ul className="space-y-2 p-3 shell:p-4">
          {todo.map(([text, href, hint]) => (
            <li key={text}>
              <Link href={href} className="row-link flex min-h-14 flex-col justify-center rounded-control bg-warning-soft px-4 py-2.5 pr-10 hover:bg-paper-3 shell:pr-12">
                <span className="font-medium">{text}</span>
                <span className="text-sm text-muted">{hint}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );

  return (
    <>
      <PageHeader title="Dashboard"
        description={`${branch.name} · ${today}${todo.length ? ` · ${todo[0][0]}${todo.length > 1 ? `, and ${todo.length - 1} more thing${todo.length > 2 ? "s" : ""} to look at` : ""}` : ""}`}
        actions={can("visits") ? <Link href="/visits/new" className="flex min-h-11 items-center rounded-control bg-action px-5 font-medium text-action-ink hover:bg-action-2 active:bg-action-3 active:duration-0">Check in a car</Link> : undefined} />

      {overview && (
        <section aria-label="Key figures" className="mb-6 space-y-4">
          {m && (
            <CashHero
              cash={m.cash} cashTotal={m.cash_total}
              receivables={m.receivables} overdueReceivables={m.overdue_receivables}
              payables={m.payables} overduePayables={m.overdue_payables}
              stockValue={m.stock_value}
            />
          )}

          <div className={`grid gap-4 ${m ? "shell:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]" : ""}`}>
            {m && (
              <MonthMoneyCharts
                revenue={m.revenue_month} profit={m.profit_month}
                moneyIn={m.money_in_month} moneyOut={m.money_out_month}
              />
            )}
            <div className={!m ? "mb-0" : undefined} aria-label="Needs attention">
              {needsAttention}
            </div>
          </div>

          <div>
            <h2 className="mb-2">In the workshop</h2>
            <WorkshopKpiCharts
              carsIn={w.cars_in} openQuotes={w.open_quotes} quotesWaiting={w.quotes_waiting}
              repairOrders={w.repair_orders} ready={w.ready_for_pickup} onHold={w.on_hold}
              lowStock={d.data.stock.low_stock} items={d.data.stock.items}
            />
          </div>
        </section>
      )}

      <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
        <h2>My work</h2>
        <p className="text-sm text-muted">Follow the car: quote, repair, release.</p>
      </div>
      <div className="mb-6"><MyWork /></div>

      <HowItWorks />
    </>
  );
}
