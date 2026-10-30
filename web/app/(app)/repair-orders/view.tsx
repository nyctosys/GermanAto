"use client";

import Link from "next/link";
import { Suspense } from "react";
import { carTitle, Plate } from "@/components/cars";
import { RoBadge, type RoStatus } from "@/components/repairs";
import { SearchBox, Segments, useQueryParam } from "@/components/search";
import { RequirePermission } from "@/components/shell";
import { Card, EmptyState, ErrorState, PageHeader, SkeletonRows } from "@/components/ui";
import { useApi } from "@/lib/api";
import { day } from "@/lib/format";

type Row = { id: string; number: string; status: RoStatus; created_at: string; pending: number; lines: number;
  visit: { id: string; number: string }; customer: { id: string; name: string };
  car: { plate: string; make: string; model: string; year: number | null } };

const TABS = [["active", "In progress"], ["on_hold", "On hold"], ["ready", "Ready"], ["delivered", "Delivered"], ["all", "All"]];

export default function RepairOrdersPage() {
  return (
    <RequirePermission permission="repair-orders">
      <PageHeader title="Repair orders" description="The work under way. A repair order is made from an approved quotation."
                  actions={<Link href="/repair-orders/new" className="flex min-h-11 items-center rounded-control bg-primary px-5 font-medium text-primary-ink hover:bg-primary-2 active:bg-primary-3 active:duration-0">Make a repair order</Link>} />
      <Suspense fallback={<Card flush><SkeletonRows /></Card>}>
        <Board />
      </Suspense>
    </RequirePermission>
  );
}

function Board() {
  const [status, setStatus] = useQueryParam("status");
  const [q] = useQueryParam("q");
  const list = useApi<Row[]>(`/api/repair-orders?${new URLSearchParams({ status: status || "active", q })}`);
  return (
    <>
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <SearchBox placeholder="Number, customer, phone or plate" />
        <Segments value={status || "active"} onChange={(v) => setStatus(v === "active" ? "" : v)} options={TABS.map(([value, label]) => ({ value, label }))} />
      </div>
      {list.error ? <Card flush><ErrorState message={list.error} onRetry={list.reload} /></Card>
        : !list.data ? <Card flush><SkeletonRows /></Card>
        : !list.data.length ? (
          <Card flush><EmptyState title="No repair orders here" action={<Link href="/repair-orders/new" className="text-primary underline">Make a repair order</Link>}>Approve a quotation first, then make its repair order here.</EmptyState></Card>
        ) : (
          <ul className="grid gap-3 sm:grid-cols-2 shell:grid-cols-3">
            {list.data.map((r) => (
              <li key={r.id}>
                <Link href={`/repair-orders/${r.id}`} className="flex h-full flex-col gap-3 rounded-card bg-surface p-4 transition-colors duration-(--dur-micro) hover:bg-paper-3/40 active:bg-paper-3 active:duration-0">
                  <span className="flex items-start justify-between gap-3"><Plate plate={r.car.plate} small /><RoBadge status={r.status} /></span>
                  <span>
                    <span className="block font-medium">{carTitle(r.car)}</span>
                    <span className="block text-ink-2">{r.customer.name}</span>
                  </span>
                  <span className="mt-auto flex items-center justify-between text-sm text-muted">
                    <span>{r.number}</span>
                    <span>{r.pending ? `${r.pending} of ${r.lines} to do` : `Opened ${day(r.created_at)}`}</span>
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
    </>
  );
}
