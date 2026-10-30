"use client";

import Link from "next/link";
import { Suspense } from "react";
import { QuoteBadge, type QuoteStatus } from "@/components/estimates";
import { SearchBox, Segments, useQueryParam } from "@/components/search";
import { RequirePermission } from "@/components/shell";
import { Card, EmptyState, ErrorState, PageHeader, SkeletonRows } from "@/components/ui";
import { useApi } from "@/lib/api";
import { day, money } from "@/lib/format";

type Row = { id: string; number: string; revision: number; status: QuoteStatus; total: string; created_at: string; valid_until: string;
  visit: { id: string; number: string }; customer: { id: string; name: string } };

const TABS = [["all", "All"], ["draft", "Draft"], ["sent", "Sent"], ["approved", "Approved"], ["rejected", "Rejected"], ["expired", "Expired"]];

export default function QuotationsPage() {
  return (
    <RequirePermission permission="quotations">
      <PageHeader title="Quotations" description="Every estimate, from draft to approved. A quotation is made from a visit's job card."
                  actions={<Link href="/quotations/new" className="flex min-h-11 items-center rounded-control bg-action px-5 font-medium text-action-ink hover:bg-action-2 active:bg-action-3 active:duration-0">Make a quotation</Link>} />
      <Suspense fallback={<Card flush><SkeletonRows /></Card>}>
        <List />
      </Suspense>
    </RequirePermission>
  );
}

function List() {
  const [status, setStatus] = useQueryParam("status");
  const [q] = useQueryParam("q");
  const list = useApi<Row[]>(`/api/quotations?${new URLSearchParams({ status: status || "all", q })}`);
  return (
    <>
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <SearchBox placeholder="Number, customer, phone or plate" />
        <Segments value={status || "all"} onChange={(v) => setStatus(v === "all" ? "" : v)} options={TABS.map(([value, label]) => ({ value, label }))} />
      </div>
      <Card flush>
        {list.error ? <ErrorState message={list.error} onRetry={list.reload} />
          : !list.data ? <SkeletonRows />
          : !list.data.length ? (
            <EmptyState title="No quotations here" action={<Link href="/quotations/new" className="text-primary underline">Make a quotation</Link>}>
              Pick a car that is in the workshop, write its job card if needed, then make the quotation.
            </EmptyState>
          ) : (
            <table className="table-stack w-full">
              <thead><tr className="text-left text-sm text-muted">
                <th className="px-4 py-2 font-normal shell:px-5">Quotation</th><th className="px-4 py-2 font-normal">Customer</th>
                <th className="px-4 py-2 font-normal">Status</th><th className="px-4 py-2 text-right font-normal shell:pr-5">Total</th>
              </tr></thead>
              <tbody>
                {list.data.map((q) => (
                  <tr key={q.id} className="border-t border-rule">
                    <td className="px-4 py-3 shell:px-5 max-sm:px-0">
                      <Link href={`/quotations/${q.id}`} className="font-medium underline">{q.number}{q.revision > 1 ? `, rev ${q.revision}` : ""}</Link>
                      <span className="block text-sm text-muted">{q.visit.number}, {day(q.created_at)}</span>
                    </td>
                    <td data-label="Customer" className="px-4 py-3 max-sm:px-0">{q.customer.name}</td>
                    <td data-label="Status" className="px-4 py-3 max-sm:px-0"><QuoteBadge status={q.status} /></td>
                    <td data-label="Total" className="num px-4 py-3 text-right shell:pr-5 max-sm:px-0">{money(q.total)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
      </Card>
    </>
  );
}
