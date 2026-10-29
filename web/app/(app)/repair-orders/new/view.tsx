"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type ReactNode } from "react";
import { carTitle, Plate } from "@/components/cars";
import { SearchBox, useQueryParam } from "@/components/search";
import { RequirePermission } from "@/components/shell";
import { Button, Card, EmptyState, ErrorState, Notice, PageHeader, SkeletonRows } from "@/components/ui";
import { type VisitSummary } from "@/components/visits";
import { api, ApiError, useApi } from "@/lib/api";
import { useSession } from "@/lib/session";

type QuoteRef = { id: string; number: string; status: string; expired: boolean };
type VisitDetail = {
  id: string;
  repair_order: { id: string; number: string } | null;
  quotations: QuoteRef[];
  job_card: { id: string; number: string; lines: number } | null;
};

/** Pick a car in the workshop; only an approved quotation can become a repair order. */
export default function NewRepairOrderPage() {
  return (
    <RequirePermission permission="repair-orders">
      <PageHeader title="Make a repair order" description="Choose a car that is in the workshop. The repair order is made from an approved quotation."
                  actions={<Link href="/repair-orders" className="flex min-h-11 items-center rounded-control border border-rule-strong bg-surface px-4 font-medium hover:bg-paper-2">Back to repair orders</Link>} />
      <Picker />
    </RequirePermission>
  );
}

function Picker() {
  const { can } = useSession();
  const [q] = useQueryParam("q");
  const list = useApi<VisitSummary[]>(can("visits") ? `/api/visits?${new URLSearchParams({ status: "open", q })}` : null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<ReactNode>(null);
  const router = useRouter();

  async function makeRepairOrder(visitId: string) {
    setBusyId(visitId);
    setError(null);
    try {
      const v = await api<VisitDetail>(`/api/visits/${visitId}`);
      if (v.repair_order) { router.push(`/repair-orders/${v.repair_order.id}`); return; }

      const quotes = v.quotations.filter((x) => x.status !== "revised");
      const approved = quotes.find((x) => x.status === "approved");
      if (approved) {
        const ro = await api<{ id: string }>(`/api/quotations/${approved.id}/repair-order`, { method: "POST" });
        router.push(`/repair-orders/${ro.id}`);
        return;
      }

      const current = quotes[0];
      if (!current) {
        if (!v.job_card) {
          setError(<>No quotation yet. Check the car in, write the job card, then <Link href="/quotations/new" className="underline">make a quotation</Link> and get it approved first.</>);
        } else if (!v.job_card.lines) {
          setError(<>No quotation yet. Add the work on the <Link href={`/job-cards/${v.job_card.id}`} className="underline">job card</Link>, make a quotation, and get it approved first.</>);
        } else {
          setError(<>No quotation yet. <Link href="/quotations/new" className="underline">Make a quotation</Link> for this car and get it approved first.</>);
        }
        setBusyId(null);
        return;
      }
      if (current.status === "draft") {
        setError(<>Quotation {current.number} is still a draft. <Link href={`/quotations/${current.id}`} className="underline">Price and send it</Link>, then record the customer&apos;s approval.</>);
      } else if (current.status === "sent" && current.expired) {
        setError(<>Quotation {current.number} has expired. <Link href={`/quotations/${current.id}`} className="underline">Revise it</Link>, send it again, and get approval.</>);
      } else if (current.status === "sent") {
        setError(<>Quotation {current.number} is waiting for the customer. <Link href={`/quotations/${current.id}`} className="underline">Record the approval</Link> before making the repair order.</>);
      } else if (current.status === "rejected") {
        setError(<>Quotation {current.number} was rejected. <Link href={`/quotations/${current.id}`} className="underline">Revise it</Link> and get a new approval.</>);
      } else if (current.status === "converted") {
        setError(<>Quotation {current.number} was already converted. Open the visit if a repair order should already exist.</>);
      } else {
        setError(<>A repair order is made from an approved quotation. Open <Link href={`/quotations/${current.id}`} className="underline">{current.number}</Link>.</>);
      }
      setBusyId(null);
    } catch (err) {
      const detail = err instanceof ApiError ? (err.detail as { repair_order_id?: string; message?: string }) : undefined;
      if (detail?.repair_order_id) { router.push(`/repair-orders/${detail.repair_order_id}`); return; }
      setError((err as Error).message);
      setBusyId(null);
    }
  }

  if (!can("visits")) {
    return (
      <Card>
        <Notice>Repair orders are made for cars already checked in with an approved quotation. Ask someone with workshop access to check the car in first.</Notice>
        <p className="mt-3"><Link href="/repair-orders" className="underline">Back to repair orders</Link></p>
      </Card>
    );
  }

  return (
    <>
      <div className="mb-4"><SearchBox placeholder="Plate, customer or visit number" /></div>
      {error && <div className="mb-4"><Notice>{error}</Notice></div>}
      <Card flush>
        {list.error ? <ErrorState message={list.error} onRetry={list.reload} />
          : !list.data ? <SkeletonRows />
          : !list.data.length ? (
            <EmptyState title="No cars in the workshop" action={<Link href="/visits/new" className="text-accent underline">Check in a car</Link>}>
              {q ? `Nothing matches “${q}”.` : "Check a car in, make and approve a quotation, then make the repair order here."}
            </EmptyState>
          ) : (
            <ul>
              {list.data.map((v) => (
                <li key={v.id} className="flex flex-wrap items-center justify-between gap-4 border-t border-rule px-4 py-3 first:border-t-0 shell:px-5">
                  <div className="flex min-w-0 flex-wrap items-center gap-4">
                    <Plate plate={v.car.plate} small />
                    <div className="min-w-0">
                      <p className="font-medium">{carTitle(v.car)}</p>
                      <p className="text-sm text-muted">{v.customer.name}, {v.number}</p>
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Link href={`/visits/${v.id}`} className="flex min-h-11 items-center rounded-control border border-rule-strong bg-surface px-4 font-medium hover:bg-paper-2">Visit</Link>
                    <Button disabled={busyId === v.id} onClick={() => makeRepairOrder(v.id)}>
                      {busyId === v.id ? "Opening" : "Make repair order"}
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          )}
      </Card>
    </>
  );
}
