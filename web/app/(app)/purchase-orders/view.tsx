"use client";

import Link from "next/link";
import { Suspense } from "react";
import { PoBadge, type PoStatus } from "@/components/purchasing";
import { Segments, useQueryParam } from "@/components/search";
import { PURCHASING, RequirePermission } from "@/components/shell";
import { Card, EmptyState, ErrorState, PageHeader, SkeletonRows } from "@/components/ui";
import { useApi } from "@/lib/api";
import { day, money } from "@/lib/format";
import { useSession } from "@/lib/session";

type Row = { id: string; number: string; status: PoStatus; created_at: string; expected_on: string | null; total: string; lines: number; vendor: { id: string; name: string } };
const TABS = [["open", "Open"], ["draft", "Drafts"], ["sent", "Waiting for goods"], ["received", "Received"], ["closed", "Closed"], ["all", "All"]];

export default function PurchaseOrdersPage() {
  const { can } = useSession();
  return (
    <RequirePermission permission={PURCHASING}>
      <PageHeader title="Purchase orders" description="What we have ordered from vendors. Goods are counted in against an order."
                  actions={can("purchasing") && <Link href="/purchase-orders/new" className="flex min-h-11 items-center rounded-control bg-primary px-5 font-medium text-primary-ink hover:bg-primary-2 active:bg-primary-3 active:duration-0">New purchase order</Link>} />
      <Suspense fallback={<Card flush><SkeletonRows /></Card>}>
        <List />
      </Suspense>
    </RequirePermission>
  );
}

function List() {
  const [status, setStatus] = useQueryParam("status");
  const list = useApi<Row[]>(`/api/purchase-orders?status=${status || "open"}`);
  return (
    <>
      <div className="mb-4 overflow-x-auto">
        <Segments value={status || "open"} onChange={(v) => setStatus(v === "open" ? "" : v)} options={TABS.map(([value, label]) => ({ value, label }))} />
      </div>
      <Card flush>
        {list.error ? <ErrorState message={list.error} onRetry={list.reload} />
          : !list.data ? <SkeletonRows />
          : !list.data.length ? <EmptyState title="No purchase orders here">Write an order to a vendor, send it, then count the goods in when they arrive.</EmptyState>
          : (
            <table className="table-stack w-full">
              <thead><tr className="text-left text-sm text-muted">
                <th className="px-4 py-2 font-normal shell:px-5">Order</th><th className="px-4 py-2 font-normal">Vendor</th>
                <th className="px-4 py-2 font-normal">Status</th><th className="px-4 py-2 text-right font-normal shell:pr-5">Value</th>
              </tr></thead>
              <tbody>
                {list.data.map((p) => (
                  <tr key={p.id} className="border-t border-rule">
                    <td className="px-4 py-3 shell:px-5 max-sm:px-0">
                      <Link href={`/purchase-orders/${p.id}`} className="font-medium underline">{p.number}</Link>
                      <span className="block text-sm text-muted">{day(p.created_at)}, {p.lines} {p.lines === 1 ? "item" : "items"}{p.expected_on ? `, due ${day(p.expected_on)}` : ""}</span>
                    </td>
                    <td data-label="Vendor" className="px-4 py-3 max-sm:px-0">{p.vendor.name}</td>
                    <td data-label="Status" className="px-4 py-3 max-sm:px-0"><PoBadge status={p.status} /></td>
                    <td data-label="Value" className="num px-4 py-3 text-right shell:pr-5 max-sm:px-0">{money(p.total)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
      </Card>
    </>
  );
}
