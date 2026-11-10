"use client";

import Link from "next/link";
import { Suspense } from "react";
import { BillBadge } from "@/components/purchasing";
import { Segments, useQueryParam } from "@/components/search";
import { PURCHASING, RequirePermission } from "@/components/shell";
import { SortTh, sortRows, useTableSort } from "@/components/sort";
import { Badge, Card, EmptyState, ErrorState, PageHeader, SkeletonRows } from "@/components/ui";
import { useApi } from "@/lib/api";
import { day, money } from "@/lib/format";

type Row = { id: string; number: string; vendor: { id: string; name: string }; vendor_invoice_no: string; bill_date: string; due_on: string;
  total: string; balance: string; pay_state: string; overdue: boolean };
const TABS = [["owing", "Owing"], ["overdue", "Overdue"], ["paid", "Paid"], ["all", "All"]];

export default function BillsPage() {
  return (
    <RequirePermission permission={PURCHASING}>
      <PageHeader title="Bills and payments" description="What we owe vendors, oldest due date first. A bill is recorded from a delivery on its purchase order." />
      <Suspense fallback={<Card flush><SkeletonRows /></Card>}>
        <List />
      </Suspense>
    </RequirePermission>
  );
}

function List() {
  const [status, setStatus] = useQueryParam("status");
  const list = useApi<Row[]>(`/api/bills?status=${status || "owing"}`);
  const owed = list.data?.reduce((s, b) => s + Number(b.balance), 0) ?? 0;
  const { sort, set } = useTableSort();
  const rows = sortRows(list.data ?? [], sort, {
    number: (b) => b.number,
    vendor: (b) => b.vendor.name,
    due: (b) => b.due_on,
    status: (b) => b.pay_state,
    total: (b) => Number(b.total),
    balance: (b) => Number(b.balance),
  });
  return (
    <>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="overflow-x-auto"><Segments value={status || "owing"} onChange={(v) => setStatus(v === "owing" ? "" : v)} options={TABS.map(([value, label]) => ({ value, label }))} /></div>
        {list.data && status !== "paid" && <p className="num text-ink-2">Balance shown: {money(owed)}</p>}
      </div>
      <Card flush>
        {list.error ? <ErrorState message={list.error} onRetry={list.reload} />
          : !list.data ? <SkeletonRows />
          : !list.data.length ? <EmptyState title="No bills here">Record a bill from a delivery on a purchase order.</EmptyState>
          : (
            <table className="table-stack w-full">
              <thead><tr className="text-left text-sm text-muted">
                <SortTh label="Bill" k="number" sort={sort} onSort={set} className="px-4 py-2 font-normal shell:px-5" />
                <SortTh label="Vendor" k="vendor" sort={sort} onSort={set} className="px-4 py-2 font-normal" />
                <SortTh label="Due" k="due" sort={sort} onSort={set} className="px-4 py-2 font-normal" />
                <SortTh label="Status" k="status" sort={sort} onSort={set} className="px-4 py-2 font-normal" />
                <SortTh label="Total" k="total" sort={sort} onSort={set} align="right" className="px-4 py-2 text-right font-normal" />
                <SortTh label="Balance" k="balance" sort={sort} onSort={set} align="right" className="px-4 py-2 text-right font-normal shell:pr-5" />
              </tr></thead>
              <tbody>
                {rows.map((b) => (
                  <tr key={b.id} className="border-t border-rule">
                    <td className="px-4 py-3 shell:px-5 max-sm:px-0">
                      <Link href={`/bills/${b.id}`} className="font-medium underline">{b.number}</Link>
                      <span className="block text-sm text-muted">{b.vendor_invoice_no ? `Invoice ${b.vendor_invoice_no}, ` : ""}{day(b.bill_date)}</span>
                    </td>
                    <td data-label="Vendor" className="px-4 py-3 max-sm:px-0">{b.vendor.name}</td>
                    <td data-label="Due" className="px-4 py-3 max-sm:px-0">{day(b.due_on)} {b.overdue && <Badge tone="error">Overdue</Badge>}</td>
                    <td data-label="Status" className="px-4 py-3 max-sm:px-0"><BillBadge state={b.pay_state} /></td>
                    <td data-label="Total" className="num px-4 py-3 text-right max-sm:px-0">{money(b.total)}</td>
                    <td data-label="Balance" className="num px-4 py-3 text-right shell:pr-5 max-sm:px-0">{money(b.balance)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
      </Card>
    </>
  );
}
