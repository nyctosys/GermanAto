"use client";

import Link from "next/link";
import { Suspense } from "react";
import { PayBadge, type PayStatus } from "@/components/billing";
import { SearchBox, Segments, useQueryParam } from "@/components/search";
import { RequirePermission } from "@/components/shell";
import { SortTh, sortRows, useTableSort } from "@/components/sort";
import { Card, EmptyState, ErrorState, PageHeader, SkeletonRows } from "@/components/ui";
import { useApi } from "@/lib/api";
import { day, money } from "@/lib/format";

type Row = { id: string; number: string; kind: "workshop" | "counter_sale" | "inspection"; status: string; pay_status: PayStatus; total: string;
  balance: string; created_at: string; issued_at: string | null; customer: string };

export default function InvoicesPage() {
  return (
    <RequirePermission permission="invoices">
      <PageHeader title="Invoices" description="Workshop invoices and counter sales."
                  actions={<Link href="/counter-sales/new" className="flex min-h-11 items-center rounded-control bg-action px-5 font-medium text-action-ink hover:bg-action-2 active:bg-action-3 active:duration-0">New counter sale</Link>} />
      <Suspense fallback={<Card flush><SkeletonRows /></Card>}>
        <List />
      </Suspense>
    </RequirePermission>
  );
}

function List() {
  const [kind, setKind] = useQueryParam("kind");
  const [status, setStatus] = useQueryParam("status");
  const [q] = useQueryParam("q");
  const list = useApi<Row[]>(`/api/invoices?${new URLSearchParams({ kind: kind || "all", status: status || "all", q })}`);
  const { sort, set } = useTableSort();
  const rows = sortRows(list.data ?? [], sort, {
    number: (r) => r.number,
    customer: (r) => r.customer,
    status: (r) => r.pay_status,
    total: (r) => Number(r.total),
    balance: (r) => Number(r.balance),
  });
  return (
    <>
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <SearchBox placeholder="Number, customer, phone or plate" />
        <Segments value={kind || "all"} onChange={(v) => setKind(v === "all" ? "" : v)}
                  options={[{ value: "all", label: "All" }, { value: "workshop", label: "Workshop" }, { value: "counter_sale", label: "Counter" }]} />
        <Segments value={status || "all"} onChange={(v) => setStatus(v === "all" ? "" : v)}
                  options={[{ value: "all", label: "Any" }, { value: "unpaid", label: "Owing" }, { value: "paid", label: "Paid" }, { value: "draft", label: "Drafts" }]} />
      </div>
      <Card flush>
        {list.error ? <ErrorState message={list.error} onRetry={list.reload} />
          : !list.data ? <SkeletonRows />
          : !list.data.length ? (
            <EmptyState title="No invoices here">Workshop invoices are made from a Ready repair order. Parts sold over the counter start from New counter sale.</EmptyState>
          ) : (
            <table className="table-stack w-full">
              <thead><tr className="text-left text-sm text-muted">
                <SortTh label="Invoice" k="number" sort={sort} onSort={set} className="px-4 py-2 font-normal shell:px-5" />
                <SortTh label="Customer" k="customer" sort={sort} onSort={set} className="px-4 py-2 font-normal" />
                <SortTh label="Status" k="status" sort={sort} onSort={set} className="px-4 py-2 font-normal" />
                <SortTh label="Total" k="total" sort={sort} onSort={set} align="right" className="px-4 py-2 text-right font-normal" />
                <SortTh label="Balance" k="balance" sort={sort} onSort={set} align="right" className="px-4 py-2 text-right font-normal shell:pr-5" />
              </tr></thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.id} className="border-t border-rule">
                    <td className="px-4 py-3 shell:px-5 max-sm:px-0">
                      <Link href={r.status === "draft" && r.kind === "counter_sale" ? `/counter-sales/${r.id}` : `/invoices/${r.id}`} className="font-medium underline">{r.number}</Link>
                      <span className="block text-sm text-muted">{r.kind === "counter_sale" ? "Counter sale" : r.kind === "inspection" ? "Inspection fee" : "Workshop"}, {day(r.issued_at ?? r.created_at)}</span>
                    </td>
                    <td data-label="Customer" className="px-4 py-3 max-sm:px-0">{r.customer}</td>
                    <td data-label="Status" className="px-4 py-3 max-sm:px-0"><PayBadge status={r.pay_status} /></td>
                    <td data-label="Total" className="num px-4 py-3 text-right max-sm:px-0">{money(r.total)}</td>
                    <td data-label="Balance" className="num px-4 py-3 text-right shell:pr-5 max-sm:px-0">{r.status === "issued" ? money(r.balance) : ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
      </Card>
    </>
  );
}
