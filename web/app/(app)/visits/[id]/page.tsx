"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { Suspense, useState, type FormEvent } from "react";
import { carTitle, Plate } from "@/components/cars";
import { QuoteBadge, type QuoteStatus } from "@/components/estimates";
import { RoBadge, type RoStatus } from "@/components/repairs";
import { RequirePermission } from "@/components/shell";
import { Badge, Button, Card, ErrorState, Field, Input, Notice, SkeletonRows } from "@/components/ui";
import { VehiclePanel } from "@/components/vehicle-panel";
import { type VisitSummary, elapsed } from "@/components/visits";
import { api, useApi } from "@/lib/api";
import { money, phone, when } from "@/lib/format";
import { useSession } from "@/lib/session";

type File = { id: string; name: string; url: string; mime: string };
type InspectionRef = { id: string; number: string; kind: string; status: string; signed_at: string | null; supersedes_id: string | null };
type Visit = VisitSummary & {
  fuel_eighths: number | null; items_left: string; condition_notes: string; odometer_out: number | null; close_note: string;
  photos: File[]; signature: File | null; inspections: InspectionRef[];
  job_card: { id: string; number: string; lines: number } | null;
  quotations: { id: string; number: string; revision: number; status: QuoteStatus | "revised"; expired: boolean }[];
  repair_order: { id: string; number: string; status: RoStatus } | null;
  payments: { id: string; number: string; kind: string; status: string; amount: string }[];
};

const KIND = { workshop: "Workshop inspection", delivery: "Delivery inspection", pre_purchase: "Pre-purchase inspection" } as Record<string, string>;

export default function VisitPage() {
  return (
    <RequirePermission permission="visits">
      <Suspense fallback={<Card flush><SkeletonRows rows={6} /></Card>}>
        <VisitDetail />
      </Suspense>
    </RequirePermission>
  );
}

function VisitDetail() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { data: v, error, reload } = useApi<Visit>(`/api/visits/${id}`);
  const [cancelling, setCancelling] = useState(false);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  if (error) return <Card flush><ErrorState message={error} onRetry={reload} /></Card>;
  if (!v) return <Card flush><SkeletonRows rows={6} /></Card>;
  const open = v.status === "open";

  async function startInspection(kind: string) {
    setBusy(true);
    setActionError(null);
    try {
      const ins = await api<{ id: string }>(`/api/visits/${id}/inspections`, { method: "POST", json: { kind } });
      router.push(`/inspections/${ins.id}`);
    } catch (err) {
      setActionError((err as Error).message);
      setBusy(false);
    }
  }

  return (
    <>
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div className="flex flex-wrap items-center gap-4">
          <Plate plate={v.car.plate} />
          <div>
            <h1>{carTitle(v.car)}</h1>
            <p className="text-muted">
              <Link href={`/customers/${v.customer.id}`} className="underline">{v.customer.name}</Link>
              <a href={`tel:${v.customer.phone}`} className="num ml-3">{phone(v.customer.phone)}</a>
            </p>
          </div>
        </div>
        <div className="text-right">
          <p className="font-medium">{v.number}</p>
          {open ? <Badge tone="accent">In the workshop {elapsed(v.checked_in_at)}</Badge>
            : v.status === "cancelled" ? <Badge>Cancelled</Badge> : <Badge tone="success">Delivered</Badge>}
        </div>
      </div>

      <div className="grid gap-4 shell:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
        <div className="space-y-4">
          <Card title="Inspections" flush>
            {v.inspections.length > 0 && (
              <ul>
                {v.inspections.map((i) => (
                  <li key={i.id} className="border-t border-rule first:border-t-0">
                    <Link href={`/inspections/${i.id}`} className="flex min-h-14 flex-wrap items-center justify-between gap-3 px-4 py-3 hover:bg-paper-2 shell:px-5">
                      <span>
                        <span className="block font-medium">{KIND[i.kind]}</span>
                        <span className="block text-sm text-muted">{i.number}{i.supersedes_id ? ", a revision" : ""}</span>
                      </span>
                      {i.status === "signed" ? <Badge tone="success">Signed {when(i.signed_at!)}</Badge> : <Badge tone="warning">Draft</Badge>}
                    </Link>
                  </li>
                ))}
              </ul>
            )}
            {open && (
              <div className="flex flex-wrap gap-2 border-t border-rule p-4 first:border-t-0 shell:px-5">
                {(v.kind === "pre_purchase" ? ["pre_purchase"] : ["workshop", "delivery"]).map((k) => (
                  <Button key={k} variant="secondary" disabled={busy} onClick={() => startInspection(k)}>Start {KIND[k].toLowerCase()}</Button>
                ))}
              </div>
            )}
            {actionError && <div className="px-4 pb-4"><Notice>{actionError}</Notice></div>}
          </Card>

          <Estimate v={v} onError={setActionError} />
        </div>

        <div className="space-y-4">
          <VehiclePanel carId={v.car.id} ownerId={v.customer.id} buyerId={v.buyer?.id} onChange={reload} />
          <Card title="Check-in">
            <dl className="grid gap-4 sm:grid-cols-2">
              <div><dt className="text-sm text-muted">Checked in</dt><dd>{when(v.checked_in_at)}</dd></div>
              <div><dt className="text-sm text-muted">Odometer</dt><dd className="num">{v.odometer_in != null ? `${v.odometer_in.toLocaleString("en-PK")} km` : "Not recorded"}</dd></div>
              <div><dt className="text-sm text-muted">Fuel</dt><dd>{v.fuel_eighths == null ? "Not recorded" : v.fuel_eighths === 8 ? "Full" : v.fuel_eighths === 0 ? "Empty" : `${v.fuel_eighths}/8`}</dd></div>
              {[["Complaint", v.complaint], ["Existing damage", v.condition_notes], ["Valuables in the car", v.items_left]].map(([l, t]) => (
                <div key={l} className="sm:col-span-2"><dt className="text-sm text-muted">{l}</dt><dd className={t ? "whitespace-pre-line" : "text-muted"}>{t || "None"}</dd></div>
              ))}
            </dl>
            {v.photos.length > 0 && (
              <ul className="mt-4 grid grid-cols-3 gap-2">
                {v.photos.map((p) => (
                  <li key={p.id}>
                    <a href={p.url} target="_blank" rel="noreferrer" className="block aspect-square overflow-hidden rounded-control border border-rule">
                      {/* eslint-disable-next-line @next/next/no-img-element -- authenticated API files */}
                      <img src={p.url} alt={p.name} className="h-full w-full object-cover" />
                    </a>
                  </li>
                ))}
              </ul>
            )}
            {v.signature && (
              <figure className="mt-4">
                {/* eslint-disable-next-line @next/next/no-img-element -- authenticated API files */}
                <img src={v.signature.url} alt="Customer signature" className="h-20 rounded-control border border-rule bg-surface" />
                <figcaption className="mt-1 text-sm text-muted">Signed by the customer at check-in</figcaption>
              </figure>
            )}
          </Card>

          {open && (
            cancelling ? <CancelVisit id={v.id} onDone={() => { setCancelling(false); reload(); }} onCancel={() => setCancelling(false)} />
              : <Button variant="ghost" onClick={() => setCancelling(true)}>Cancel this visit</Button>
          )}
          {v.status === "cancelled" && v.close_note && <Notice tone="warning">Cancelled: {v.close_note}</Notice>}
        </div>
      </div>
    </>
  );
}

function CancelVisit({ id, onDone, onCancel }: { id: string; onDone: () => void; onCancel: () => void }) {
  const [error, setError] = useState<string | null>(null);
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    try {
      await api(`/api/visits/${id}/cancel`, { method: "POST", json: { reason: new FormData(e.currentTarget).get("reason") } });
      onDone();
    } catch (err) {
      setError((err as Error).message);
    }
  }
  return (
    <Card title="Cancel this visit">
      <form onSubmit={submit} className="space-y-4">
        <Field label="Reason" hint="Kept on the visit and in the audit log."><Input name="reason" required minLength={3} autoFocus /></Field>
        <Notice>{error}</Notice>
        <div className="flex flex-wrap gap-2">
          <Button type="submit" variant="danger">Cancel visit</Button>
          <Button type="button" variant="secondary" onClick={onCancel}>Keep it open</Button>
        </div>
      </form>
    </Card>
  );
}

function Estimate({ v, onError }: { v: Visit; onError: (m: string | null) => void }) {
  const router = useRouter();
  const { can } = useSession();
  const [busy, setBusy] = useState(false);
  const quote = v.quotations.findLast((q) => q.status !== "revised");
  const advance = v.payments.filter((p) => p.kind === "advance" && p.status === "posted").reduce((s, p) => s + Number(p.amount), 0);

  async function openJobCard() {
    setBusy(true);
    onError(null);
    try {
      router.push(`/job-cards/${(await api<{ id: string }>(`/api/visits/${v.id}/job-card`, { method: "POST" })).id}`);
    } catch (err) {
      onError((err as Error).message);
      setBusy(false);
    }
  }

  const row = "flex min-h-14 flex-wrap items-center justify-between gap-3 border-t border-rule px-4 py-3 first:border-t-0 shell:px-5";
  return (
    <Card title="The job" flush>
      <ul>
        <li>
          {v.job_card ? (
            <Link href={`/job-cards/${v.job_card.id}`} className={`${row} hover:bg-paper-2`}>
              <span><span className="block font-medium">Job card</span><span className="block text-sm text-muted">{v.job_card.number}, {v.job_card.lines} {v.job_card.lines === 1 ? "line" : "lines"}</span></span>
            </Link>
          ) : (
            <div className={row}>
              <span><span className="block font-medium">Job card</span><span className="block text-sm text-muted">The work to quote: labour codes and parts.</span></span>
              {v.status === "open" && can("job-cards") && <Button variant="secondary" disabled={busy} onClick={openJobCard}>Start the job card</Button>}
            </div>
          )}
        </li>
        <li>
          {quote ? (
            <Link href={`/quotations/${quote.id}`} className={`${row} hover:bg-paper-2`}>
              <span><span className="block font-medium">Quotation</span><span className="block text-sm text-muted">{quote.number}{quote.revision > 1 ? `, revision ${quote.revision}` : ""}</span></span>
              <QuoteBadge status={quote.expired ? "expired" : quote.status as QuoteStatus} />
            </Link>
          ) : (
            <div className={row}><span><span className="block font-medium">Quotation</span><span className="block text-sm text-muted">Made from the job card.</span></span></div>
          )}
        </li>
        {advance > 0 && (
          <li className={row}><span className="font-medium">Advance received</span><span className="num">{money(advance)}</span></li>
        )}
        <li>
          {v.repair_order ? (
            <Link href={`/repair-orders/${v.repair_order.id}`} className={`${row} hover:bg-paper-2`}>
              <span><span className="block font-medium">Repair order</span><span className="block text-sm text-muted">{v.repair_order.number}</span></span>
              <RoBadge status={v.repair_order.status} />
            </Link>
          ) : (
            <div className={row}><span><span className="block font-medium">Repair order</span><span className="block text-sm text-muted">Made from the approved quotation.</span></span></div>
          )}
        </li>
        {["Invoice and payment", "Gate pass"].map((s) => (
          <li key={s} className={`${row} text-ink-2`}><span>{s}</span><span className="text-sm text-muted">Being built</span></li>
        ))}
      </ul>
    </Card>
  );
}
