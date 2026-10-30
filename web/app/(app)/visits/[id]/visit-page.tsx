"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { Suspense, useState, type FormEvent } from "react";
import { carTitle, Plate } from "@/components/cars";
import { linkButton, QuoteBadge, type QuoteStatus } from "@/components/estimates";
import { RoBadge, type RoStatus } from "@/components/repairs";
import { RequirePermission } from "@/components/shell";
import { Badge, Button, Card, ErrorState, Field, Input, Notice, SkeletonRows } from "@/components/ui";
import { VehiclePanel } from "@/components/vehicle-panel";
import { type VisitSummary, elapsed } from "@/components/visits";
import { api, useApi } from "@/lib/api";
import { useFormErrors } from "@/lib/form";
import { money, phone, when } from "@/lib/format";
import { gatePassSchemaAt, parseForm } from "@/lib/schemas";
import { useSession } from "@/lib/session";

type File = { id: string; name: string; url: string; mime: string };
type InspectionRef = { id: string; number: string; kind: string; status: string; signed_at: string | null; supersedes_id: string | null };
type Visit = VisitSummary & {
  fuel_eighths: number | null; items_left: string; condition_notes: string; odometer_out: number | null; close_note: string;
  photos: File[]; signature: File | null; inspections: InspectionRef[];
  job_card: { id: string; number: string; lines: number } | null;
  quotations: { id: string; number: string; revision: number; status: QuoteStatus | "revised"; expired: boolean }[];
  repair_order: { id: string; number: string; status: RoStatus } | null;
  invoice: { id: string; number: string; status: string } | null;
  handed_to: string; credit_reason: string;
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

/** The one thing to do next on this visit, in plain words, worked out from where the visit has got to. */
function nextStep(v: Visit): { text: string; href?: string; who: string } | null {
  if (v.status !== "open") return null;
  const q = v.quotations.find((x) => x.status !== "revised");
  const ro = v.repair_order;
  if (v.invoice?.status === "issued") return { text: "The invoice is issued. Take any payment that is owed, then release the car with the gate pass below.", href: `/invoices/${v.invoice.id}`, who: "Cashier, then the guard" };
  if (v.invoice) return { text: "The invoice is a draft. Check it, then issue it.", href: `/invoices/${v.invoice.id}`, who: "Cashier" };
  if (ro?.status === "ready") return { text: "The repair is finished. Make the invoice.", href: `/repair-orders/${ro.id}`, who: "Cashier or manager" };
  if (ro) return { text: "The repair is under way. When every job is done, move it to Ready.", href: `/repair-orders/${ro.id}`, who: "Technician" };
  if (q?.status === "approved") return { text: "The customer approved the quotation. Make the repair order.", href: `/quotations/${q.id}`, who: "Manager" };
  if (q?.status === "rejected") return { text: "The customer said no. Revise the quotation, or cancel the visit.", href: `/quotations/${q.id}`, who: "Front desk" };
  if (q && (q.status === "sent" || q.expired)) return { text: q.expired ? "The quotation has expired. Revise it and send it again." : "Waiting for the customer. When they agree, record the approval.", href: `/quotations/${q.id}`, who: "Front desk" };
  if (q) return { text: "Price the quotation and send it to the customer.", href: `/quotations/${q.id}`, who: "Front desk" };
  if (v.job_card) return { text: "Make the quotation from the job card.", href: `/job-cards/${v.job_card.id}`, who: "Front desk" };
  return { text: "Write the job card: the list of work to quote. Inspect the car first if you need to.", href: "#the-job", who: "Front desk or technician" };
}

/** Where the visit has got to, as a bar: the steps done so far are filled in. */
function JobProgress({ v }: { v: Visit }) {
  const q = v.quotations.find((x) => x.status !== "revised");
  const steps: [string, boolean][] = [
    ["Checked in", true],
    ["Job card", !!v.job_card],
    ["Quotation", !!q && q.status !== "draft"],
    ["Approved", q?.status === "approved" || q?.status === "converted" || !!v.repair_order],
    ["Repair", !!v.repair_order && v.repair_order.status !== "received"],
    ["Ready", ["ready", "delivered"].includes(v.repair_order?.status ?? "")],
    ["Invoiced", !!v.invoice && v.invoice.status !== "draft"],
    ["Paid", v.invoice?.status === "paid"],
    ["Left", v.status === "closed"],
  ];
  const done = steps.filter(([, d]) => d).length;
  return (
    <div className="mb-4 rounded-card bg-surface px-4 py-3 shell:px-5" role="group" aria-label={`Progress: ${done} of ${steps.length} steps done`}>
      <div className="h-2 overflow-hidden rounded-full bg-paper-3"><div className="h-full rounded-full bg-primary transition-[width] duration-(--dur-micro)" style={{ width: `${(done / steps.length) * 100}%` }} /></div>
      <ol className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-sm">
        {steps.map(([name, d]) => <li key={name} className={d ? "font-medium text-ink" : "text-muted"}>{d ? "Done: " : ""}{name}</li>)}
      </ol>
    </div>
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
              <a href={`tel:${v.customer.phone}`} className="num ml-3 underline">{phone(v.customer.phone)}</a>
            </p>
          </div>
        </div>
        <div className="flex flex-col items-start gap-1.5 sm:items-end">
          <p className="font-medium">{v.number}</p>
          <Link href={`/print/visits/${v.id}`} target="_blank" className="text-sm underline">Print visit record</Link>
          {open ? <Badge tone="accent">In the workshop {elapsed(v.checked_in_at)}</Badge>
            : v.status === "cancelled" ? <Badge>Cancelled</Badge> : <Badge tone="success">Delivered</Badge>}
        </div>
      </div>

      {v.status !== "cancelled" && <JobProgress v={v} />}

      {(() => {
        const n = nextStep(v);
        return n && (
          <div className="mb-4 flex flex-wrap items-center justify-between gap-x-4 gap-y-1 rounded-card bg-surface px-4 py-3 shell:px-5">
            <p><span className="font-medium">Next step: </span>{n.text} <span className="text-sm text-muted">For: {n.who}.</span></p>
            {n.href && <Link href={n.href} className="inline-flex min-h-11 items-center font-medium underline underline-offset-4">{n.href.startsWith("#") ? "Go there" : "Open it"}</Link>}
          </div>
        );
      })()}

      <div className="grid gap-4 shell:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
        <div className="space-y-4">
          <Card title="Inspections" flush>
            {v.inspections.length > 0 && (
              <ul>
                {v.inspections.map((i) => (
                  <li key={i.id} className="border-t border-rule first:border-t-0">
                    <Link href={`/inspections/${i.id}`} className="flex min-h-14 flex-wrap items-center justify-between gap-3 px-4 py-3 row-link pr-10 shell:pr-12 hover:bg-paper-2 shell:px-5">
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

          {open ? <GatePass v={v} onDone={reload} /> : v.status === "closed" && <GatePassDone v={v} />}
          {open && (
            cancelling ? <CancelVisit id={v.id} onDone={() => { setCancelling(false); reload(); }} onCancel={() => setCancelling(false)} />
              : <Button variant="danger" onClick={() => setCancelling(true)}>Cancel this visit</Button>
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
    <div id="the-job" className="scroll-mt-4"><Card title="The job" flush>
      <ul>
        <li>
          {v.job_card ? (
            <Link href={`/job-cards/${v.job_card.id}`} className={`${row} row-link pr-10 shell:pr-12 hover:bg-paper-2`}>
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
            <Link href={`/quotations/${quote.id}`} className={`${row} row-link pr-10 shell:pr-12 hover:bg-paper-2`}>
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
            <Link href={`/repair-orders/${v.repair_order.id}`} className={`${row} row-link pr-10 shell:pr-12 hover:bg-paper-2`}>
              <span><span className="block font-medium">Repair order</span><span className="block text-sm text-muted">{v.repair_order.number}</span></span>
              <RoBadge status={v.repair_order.status} />
            </Link>
          ) : (
            <div className={row}><span><span className="block font-medium">Repair order</span><span className="block text-sm text-muted">Made from the approved quotation.</span></span></div>
          )}
        </li>
        <li>
          {v.invoice ? (
            <Link href={`/invoices/${v.invoice.id}`} className={`${row} row-link pr-10 shell:pr-12 hover:bg-paper-2`}>
              <span><span className="block font-medium">Invoice</span><span className="block text-sm text-muted">{v.invoice.number}</span></span>
              <Badge tone={v.invoice.status === "issued" ? "success" : "warning"}>{v.invoice.status === "issued" ? "Issued" : "Draft"}</Badge>
            </Link>
          ) : (
            <div className={row}><span><span className="block font-medium">Invoice</span><span className="block text-sm text-muted">Made from the repair order once it is Ready.</span></span></div>
          )}
        </li>
      </ul>
    </Card></div>
  );
}

type GateCheck = { blockers: string[]; warnings: string[]; balance: string; invoice_id: string | null };

function GatePass({ v, onDone }: { v: Visit; onDone: () => void }) {
  const { can } = useSession();
  const check = useApi<GateCheck>(`/api/visits/${v.id}/gate-check`);
  const [open, setOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const balance = Number(check.data?.balance ?? 0);
  const schema = () => gatePassSchemaAt({ minOut: v.odometer_in, creditBalance: balance });
  const { errors, setErrors, live, applyApi } = useFormErrors(schema);
  if (!can("visits") || !check.data) return null;

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const { data, errors } = parseForm(schema(), e.currentTarget);
    setErrors(errors ?? {});
    if (!data) return;
    setBusy(true);
    setError(null);
    try {
      await api(`/api/visits/${v.id}/gate-pass`, { method: "POST", json: data });
      onDone();
    } catch (err) {
      setError(applyApi(err));
      setBusy(false);
    }
  }

  return (
    <Card title="Gate pass">
      {check.data.blockers.length > 0 ? (
        <>
          <p className="mb-2 text-ink-2">Before the car can leave:</p>
          <ul className="list-disc space-y-1 pl-5 text-ink-2">{check.data.blockers.map((b) => <li key={b}>{b}</li>)}</ul>
        </>
      ) : !open ? (
        <div className="space-y-3">
          {balance > 0 && <Notice tone="warning">{`Balance of ${money(balance)} on the invoice. Take the payment first, or an admin can release the car on credit.`}</Notice>}
          {check.data.warnings.map((w) => <Notice key={w} tone="warning">{w}</Notice>)}
          <Button onClick={() => setOpen(true)} disabled={balance > 0 && !can("release-on-credit")}>Release the car</Button>
        </div>
      ) : (
        <form onSubmit={submit} noValidate className="space-y-4" {...live}>
          <Field error={errors.odometer_out} label="Odometer at exit (km)" hint={v.odometer_in != null ? `At check-in: ${v.odometer_in.toLocaleString("en-PK")} km` : undefined}>
            <Input name="odometer_out" type="number" inputMode="numeric" min={v.odometer_in ?? 0} />
          </Field>
          <Field label="Handed over to" hint="Who collected the car, if not the owner."><Input name="handed_to" maxLength={120} /></Field>
          <Field label="Note (optional)"><Input name="note" maxLength={500} /></Field>
          {balance > 0 && (
            <Field error={errors.credit_reason} label={`Reason for releasing with ${money(balance)} unpaid`} hint="Recorded with your name on the invoice and in the audit log.">
              <Input name="credit_reason" required minLength={5} maxLength={500} />
            </Field>
          )}
          <Notice>{error}</Notice>
          <div className="flex flex-wrap gap-2">
            <Button type="submit" disabled={busy}>{busy ? "Releasing" : balance > 0 ? "Release on credit" : "Release the car"}</Button>
            <Button type="button" variant="secondary" onClick={() => setOpen(false)}>Cancel</Button>
          </div>
        </form>
      )}
    </Card>
  );
}

function GatePassDone({ v }: { v: Visit }) {
  return (
    <Card title="Gate pass">
      <dl className="grid gap-4 sm:grid-cols-2">
        <div><dt className="text-sm text-muted">Left</dt><dd>{v.closed_at ? when(v.closed_at) : ""}</dd></div>
        <div><dt className="text-sm text-muted">Odometer at exit</dt><dd className="num">{v.odometer_out != null ? `${v.odometer_out.toLocaleString("en-PK")} km` : "Not recorded"}</dd></div>
        {v.handed_to && <div className="sm:col-span-2"><dt className="text-sm text-muted">Handed over to</dt><dd>{v.handed_to}</dd></div>}
        {v.credit_reason && <div className="sm:col-span-2"><dt className="text-sm text-muted">Released on credit</dt><dd>{v.credit_reason}</dd></div>}
      </dl>
      <div className="mt-4 flex flex-wrap gap-2">
        <Link href={`/print/gate-pass/${v.id}`} target="_blank" className={linkButton}>Print gate pass</Link>
        <Link href={`/print/visits/${v.id}`} target="_blank" className={linkButton}>Print visit record</Link>
      </div>
    </Card>
  );
}
