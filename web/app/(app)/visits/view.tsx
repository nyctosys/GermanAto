"use client";

import Link from "next/link";
import { Suspense } from "react";
import { carTitle, Plate } from "@/components/cars";
import { JobProgress, stepsOf } from "@/components/job-progress";
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
                  actions={<Link href="/visits/new" className="flex min-h-11 items-center rounded-control bg-action px-5 font-medium text-action-ink hover:bg-action-2 active:bg-action-3 active:duration-0">Check in a car</Link>} />
      <Suspense fallback={<Card flush><SkeletonRows /></Card>}>
        <Board />
      </Suspense>
    </RequirePermission>
  );
}

function Board() {
  const [status, setStatus] = useQueryParam("status");
  const [q] = useQueryParam("q");
  const list = useApi<VisitSummary[]>(`/api/visits?${new URLSearchParams({ status: status || "open", q })}`, { swr: true });
  return (
    <>
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <SearchBox placeholder="Plate, customer or visit" />
        <Segments value={status || "open"} onChange={(v) => setStatus(v === "open" ? "" : v)}
                  options={[{ value: "open", label: "In now" }, { value: "closed", label: "Delivered" }, { value: "all", label: "All" }]} />
      </div>
      {list.error ? <Card flush><ErrorState message={list.error} onRetry={list.reload} /></Card>
        : !list.data ? <Card flush><SkeletonRows /></Card>
        : !list.data.length ? (
          <Card flush>
            <EmptyState title={status === "closed" ? "No cars delivered yet" : "The workshop is empty"}
                        action={<Link href="/visits/new" className="text-primary underline">Check in a car</Link>}>
              {q ? `Nothing matches “${q}”.` : "Checked-in cars appear here until they leave."}
            </EmptyState>
          </Card>
        ) : (
          <ul className="grid gap-3">
            {list.data.map((v) => (
              <li key={v.id}>
                <Link href={`/visits/${v.id}`} className="flex flex-col gap-3 rounded-card bg-surface p-4 transition-colors duration-(--dur-micro) hover:bg-paper-3 shell:px-5">
                  <span className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
                    <span className="flex min-w-0 flex-wrap items-center gap-x-4 gap-y-2">
                      <Plate plate={v.car.plate} small />
                      <span className="min-w-0">
                        <span className="block font-medium">{carTitle(v.car)}</span>
                        <span className="block text-ink-2">{v.customer.name}</span>
                      </span>
                    </span>
                    <span className="text-right text-sm text-muted">
                      <span className="block">{v.status === "open" ? `In ${elapsed(v.checked_in_at)}` : v.status === "closed" ? `Out ${day(v.closed_at)}` : "Cancelled"}</span>
                      <span className="block">{v.number}{v.kind === "pre_purchase" && <span className="ml-2 font-medium text-primary">Pre-purchase</span>}</span>
                    </span>
                  </span>
                  {v.complaint && <span className="line-clamp-2 text-sm text-muted">{v.complaint}</span>}
                  {v.progress && v.status !== "cancelled" && <JobProgress flat steps={stepsOf(v.progress)} />}
                </Link>
              </li>
            ))}
          </ul>
        )}
    </>
  );
}
