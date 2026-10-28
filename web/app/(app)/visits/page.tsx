"use client";

import Link from "next/link";
import { Suspense } from "react";
import { carTitle, Plate } from "@/components/cars";
import { SearchBox, Segments, useQueryParam } from "@/components/search";
import { RequirePermission } from "@/components/shell";
import { Card, EmptyState, ErrorState, PageHeader, SkeletonRows } from "@/components/ui";
import { elapsed, type VisitSummary } from "@/components/visits";
import { useApi } from "@/lib/api";
import { day } from "@/lib/format";

export default function VisitsPage() {
  return (
    <RequirePermission permission="visits">
      <PageHeader title="Workshop" description="Cars in the workshop now. Every job starts with a check-in."
                  actions={<Link href="/visits/new" className="flex min-h-11 items-center rounded-control bg-accent px-5 font-medium text-accent-ink hover:bg-accent-2 active:bg-accent-3 active:duration-0">Check in a car</Link>} />
      <Suspense fallback={<Card flush><SkeletonRows /></Card>}>
        <Board />
      </Suspense>
    </RequirePermission>
  );
}

function Board() {
  const [status, setStatus] = useQueryParam("status");
  const [q] = useQueryParam("q");
  const list = useApi<VisitSummary[]>(`/api/visits?${new URLSearchParams({ status: status || "open", q })}`);
  return (
    <>
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <SearchBox placeholder="Plate, customer or visit number" />
        <Segments value={status || "open"} onChange={(v) => setStatus(v === "open" ? "" : v)}
                  options={[{ value: "open", label: "In now" }, { value: "closed", label: "Delivered" }, { value: "all", label: "All" }]} />
      </div>
      {list.error ? <Card flush><ErrorState message={list.error} onRetry={list.reload} /></Card>
        : !list.data ? <Card flush><SkeletonRows /></Card>
        : !list.data.length ? (
          <Card flush>
            <EmptyState title={status === "closed" ? "No cars delivered yet" : "The workshop is empty"}
                        action={<Link href="/visits/new" className="text-accent underline">Check in a car</Link>}>
              {q ? `Nothing matches “${q}”.` : "Checked-in cars appear here until they leave."}
            </EmptyState>
          </Card>
        ) : (
          <ul className="grid gap-3 sm:grid-cols-2 shell:grid-cols-3">
            {list.data.map((v) => (
              <li key={v.id}>
                <Link href={`/visits/${v.id}`} className="flex h-full flex-col gap-3 rounded-card bg-surface p-4 transition-colors duration-(--dur-micro) hover:bg-paper-3/40 active:bg-paper-3 active:duration-0">
                  <span className="flex items-start justify-between gap-3">
                    <Plate plate={v.car.plate} small />
                    <span className="text-sm text-muted">{v.status === "open" ? `In ${elapsed(v.checked_in_at)}` : v.status === "closed" ? `Out ${day(v.closed_at)}` : "Cancelled"}</span>
                  </span>
                  <span>
                    <span className="block font-medium">{carTitle(v.car)}</span>
                    <span className="block text-ink-2">{v.customer.name}</span>
                  </span>
                  {v.complaint && <span className="line-clamp-2 text-sm text-muted">{v.complaint}</span>}
                  <span className="mt-auto flex items-center justify-between text-sm text-muted">
                    <span>{v.number}</span>
                    {v.kind === "pre_purchase" && <span className="font-medium text-accent">Pre-purchase</span>}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
    </>
  );
}
