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

type VisitDetail = {
  id: string;
  job_card: { id: string; number: string; lines: number } | null;
  quotations: { id: string; number: string; status: string }[];
  repair_order: { id: string; number: string } | null;
};

/** Pick a car that is in the workshop, then open or make its quotation. */
export default function NewQuotationPage() {
  return (
    <RequirePermission permission="quotations">
      <PageHeader title="Make a quotation" description="Choose a car that is in the workshop. The quotation is made from its job card."
                  actions={<Link href="/quotations" className="flex min-h-11 items-center rounded-control border border-rule-strong bg-surface px-4 font-medium hover:bg-paper-2">Back to quotations</Link>} />
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

  async function makeQuote(visitId: string) {
    setBusyId(visitId);
    setError(null);
    try {
      const v = await api<VisitDetail>(`/api/visits/${visitId}`);
      const current = v.quotations.find((x) => x.status !== "revised");
      if (current) { router.push(`/quotations/${current.id}`); return; }

      if (!v.job_card) {
        if (!can("job-cards")) {
          setError(<>This car has no job card yet. Ask someone with the job-cards permission to write one on the <Link href={`/visits/${visitId}`} className="underline">visit</Link> first.</>);
          setBusyId(null);
          return;
        }
        setError(<>This car has no job card yet. Opening a new one so you can add the work, then make the quotation.</>);
        const jc = await api<{ id: string }>(`/api/visits/${visitId}/job-card`, { method: "POST" });
        router.push(`/job-cards/${jc.id}`);
        return;
      }

      if (!v.job_card.lines) {
        setError(<>Add the labour and parts on the job card before making a quotation. <Link href={`/job-cards/${v.job_card.id}`} className="underline">Open job card {v.job_card.number}</Link></>);
        setBusyId(null);
        return;
      }

      const quote = await api<{ id: string }>(`/api/job-cards/${v.job_card.id}/quotation`, { method: "POST" });
      router.push(`/quotations/${quote.id}`);
    } catch (err) {
      const detail = err instanceof ApiError ? (err.detail as { quotation_id?: string; message?: string }) : undefined;
      if (detail?.quotation_id) { router.push(`/quotations/${detail.quotation_id}`); return; }
      setError((err as Error).message);
      setBusyId(null);
    }
  }

  if (!can("visits")) {
    return (
      <Card>
        <Notice>Quotations are made from cars already checked in. Ask someone with workshop access to check the car in, write the job card, then come back here.</Notice>
        <p className="mt-3"><Link href="/quotations" className="underline">Back to quotations</Link></p>
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
              {q ? `Nothing matches “${q}”.` : "Check a car in first, then make its quotation here."}
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
                    <Button disabled={busyId === v.id} onClick={() => makeQuote(v.id)}>
                      {busyId === v.id ? "Opening" : "Make quotation"}
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
