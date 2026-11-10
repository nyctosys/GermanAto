"use client";

import Link from "next/link";
import { Suspense } from "react";
import { ExportButton, Line, rangeQuery, Stat, useRange } from "@/components/reports";
import { RequirePermission } from "@/components/shell";
import { Card, EmptyState, ErrorState, PageHeader, SkeletonRows } from "@/components/ui";
import { useApi } from "@/lib/api";
import { money, qty } from "@/lib/format";

type Ops = {
  visits: { total: number; by_status: Record<string, number>; avg_turnaround_hours: number | null };
  revenue_by_channel: { workshop: string; counter_sale: string }; revenue_per_visit: string | null;
  revenue_by_kind: { labour: string; parts: string; other: string; total: string };
  top_labour: { code: string; name: string; lines: number; revenue: string }[]; top_parts: { number: string; name: string; qty: string; revenue: string }[];
  comebacks: { visit_id: string; number: string; plate: string; previous: string; days: number }[];
  quotations: { made: number; sent: number; won: number; conversion_pct: number | null };
  avg_hours_in_stage: Record<string, number>; open_repair_orders_by_age: Record<string, number>;
};
const STAGE: Record<string, string> = { received: "Received", in_repair: "In repair", testing: "Testing", ready: "Ready", diagnosis: "Diagnosis", awaiting_approval: "Awaiting approval" };
const hours = (h: number | null) => (h == null ? "None yet" : h < 48 ? `${h.toFixed(1)} hours` : `${(h / 24).toFixed(1)} days`);

export default function OperationsReport() {
  return (
    <RequirePermission permission="reports-ops">
      <PageHeader title="Workshop report" description="How the workshop is running: how many cars, how fast, what sells, and what comes back." />
      <Suspense fallback={<Card flush><SkeletonRows /></Card>}>
        <Body />
      </Suspense>
    </RequirePermission>
  );
}

function Body() {
  const [range, control] = useRange();
  const r = useApi<Ops>(`/api/reports/operations?${rangeQuery(range)}`);
  return (
    <div className="space-y-4">
      {control}
      {r.error ? <Card flush><ErrorState message={r.error} onRetry={r.reload} /></Card> : !r.data ? <Card flush><SkeletonRows rows={6} /></Card> : <Report o={r.data} name={`workshop-${range.from}-to-${range.to}`} />}
    </div>
  );
}

function Report({ o, name }: { o: Ops; name: string }) {
  const q = o.quotations;
  return (
    <>
      <div className="grid gap-4 sm:grid-cols-2 shell:grid-cols-4">
        <Stat label="Cars checked in" value={o.visits.total} hint={Object.entries(o.visits.by_status).map(([k, v]) => `${v} ${k}`).join(", ") || "None"} href="/visits?status=all" />
        <Stat label="Average time in the workshop" value={hours(o.visits.avg_turnaround_hours)} hint="From check-in to the car leaving" />
        <Stat label="Workshop revenue" value={money(o.revenue_by_channel.workshop)} hint={o.revenue_per_visit ? `${money(o.revenue_per_visit)} per invoiced visit` : undefined} href="/invoices?kind=workshop" />
        <Stat label="Counter sales" value={money(o.revenue_by_channel.counter_sale)} href="/invoices?kind=counter_sale" />
      </div>

      <Card
        title="Where revenue came from"
        actions={
          <ExportButton
            name={`${name}-revenue`}
            headers={["Source", "Amount"]}
            rows={[
              ["Labour", o.revenue_by_kind.labour],
              ["Parts", o.revenue_by_kind.parts],
              ...(Number(o.revenue_by_kind.other) !== 0 ? [["Other income", o.revenue_by_kind.other] as [string, string]] : []),
              ["Total", o.revenue_by_kind.total],
              ["Workshop channel", o.revenue_by_channel.workshop],
              ["Counter sales channel", o.revenue_by_channel.counter_sale],
            ]}
          />
        }
      >
        <dl>
          <Line label="Labour" value={o.revenue_by_kind.labour} href="/invoices?kind=workshop" indent />
          <Line label="Parts" value={o.revenue_by_kind.parts} href="/invoices" indent />
          {Number(o.revenue_by_kind.other) !== 0 && <Line label="Other income" value={o.revenue_by_kind.other} href="/money-in?source=other_income" indent />}
          <Line label="Total (same as P&L revenue)" value={o.revenue_by_kind.total} strong />
        </dl>
        <p className="mt-3 text-sm text-muted">These figures match the books. Workshop vs counter above is by invoice kind (before tax).</p>
      </Card>

      <div className="grid gap-4 shell:grid-cols-2">
        <Card title="Quotations">
          <dl className="grid grid-cols-3 gap-4">
            <div><dt className="text-sm text-muted">Made</dt><dd className="num text-lg">{q.made}</dd></div>
            <div><dt className="text-sm text-muted">Sent</dt><dd className="num text-lg">{q.sent}</dd></div>
            <div><dt className="text-sm text-muted">Approved</dt><dd className="num text-lg">{q.won}</dd></div>
          </dl>
          <p className="mt-3 text-ink-2">{q.conversion_pct == null ? "Nothing sent in this period." : `${q.conversion_pct.toFixed(0)}% of the quotations sent were approved.`}</p>
          <Link href="/quotations" className="mt-2 inline-block text-sm underline">See the quotations</Link>
        </Card>
        <Card title="Time in each stage">
          {!Object.keys(o.avg_hours_in_stage).length ? <p className="text-muted">No repair orders have moved through stages yet.</p> : (
            <dl>{Object.entries(o.avg_hours_in_stage).map(([k, v]) => <div key={k} className="flex justify-between gap-4 py-1.5"><dt>{STAGE[k] ?? k}</dt><dd className="num">{hours(v)}</dd></div>)}</dl>
          )}
          <p className="mt-3 text-sm text-muted">Time on hold is not counted against a stage.</p>
        </Card>
      </div>

      <div className="grid gap-4 shell:grid-cols-2">
        <Card title="Top labour" actions={<ExportButton name={`${name}-labour`} headers={["Code", "Work", "Lines", "Revenue"]} rows={o.top_labour.map((l) => [l.code, l.name, l.lines, l.revenue])} />} flush>
          {!o.top_labour.length ? <EmptyState title="No labour invoiced" /> : (
            <ul>{o.top_labour.map((l) => <li key={l.code} className="flex justify-between gap-3 border-t border-rule px-4 py-2.5 first:border-t-0 shell:px-5"><span><span className="font-medium">{l.name}</span><span className="block text-sm text-muted">{l.code}, {l.lines} {l.lines === 1 ? "time" : "times"}</span></span><span className="num">{money(l.revenue)}</span></li>)}</ul>
          )}
        </Card>
        <Card title="Top parts" actions={<ExportButton name={`${name}-parts`} headers={["Number", "Part", "Quantity", "Revenue"]} rows={o.top_parts.map((p) => [p.number, p.name, p.qty, p.revenue])} />} flush>
          {!o.top_parts.length ? <EmptyState title="No parts sold" /> : (
            <ul>{o.top_parts.map((p) => <li key={p.number} className="flex justify-between gap-3 border-t border-rule px-4 py-2.5 first:border-t-0 shell:px-5"><span><span className="font-medium">{p.name}</span><span className="block text-sm text-muted">{p.number}, {qty(p.qty)} sold</span></span><span className="num">{money(p.revenue)}</span></li>)}</ul>
          )}
        </Card>
      </div>

      <div className="grid gap-4 shell:grid-cols-2">
        <Card title="Cars that came back within 30 days" flush>
          {!o.comebacks.length ? <p className="px-4 py-4 text-success shell:px-5">No comebacks in this period.</p> : (
            <ul>{o.comebacks.map((c) => <li key={c.visit_id} className="border-t border-rule first:border-t-0"><Link href={`/visits/${c.visit_id}`} className="row-link flex min-h-14 flex-col justify-center px-4 py-2 pr-10 hover:bg-paper-2 shell:px-5 shell:pr-12"><span className="font-medium">{c.plate} {c.number}</span><span className="text-sm text-muted">{c.days} days after {c.previous}</span></Link></li>)}</ul>
          )}
        </Card>
        <Card title="Repair orders still open, by age">
          {!Object.keys(o.open_repair_orders_by_age).length ? <p className="text-muted">None open.</p> : (
            <dl>{Object.entries(o.open_repair_orders_by_age).map(([k, v]) => <div key={k} className="flex justify-between gap-4 py-1.5"><dt>{k}</dt><dd className="num">{v}</dd></div>)}</dl>
          )}
          <Link href="/repair-orders" className="mt-2 inline-block text-sm underline">See the repair orders</Link>
        </Card>
      </div>
    </>
  );
}
