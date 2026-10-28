"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { Suspense, useState, type FormEvent } from "react";
import { type Car, CarForm, carTitle, FUELS, Plate } from "@/components/cars";
import { type Customer, CustomerPicker } from "@/components/customers";
import { RequirePermission } from "@/components/shell";
import { Badge, Button, Card, ErrorState, Field, Input, Notice, SkeletonRows } from "@/components/ui";
import { api, useApi } from "@/lib/api";
import { day, phone, today, when } from "@/lib/format";
import { useSession } from "@/lib/session";

type Ownership = {
  id: string; since: string; until: string | null; reason: string; odometer_km: number | null;
  customer: { id: string; name: string; number: string; phone: string };
  proofs: { id: string; name: string; url: string }[];
};
type Detail = Car & { ownerships: Ownership[] };
type Event = { at: string; on: string | null; kind: string; title: string; detail: string; odometer_km: number | null; link: string | null };

export default function CarPage() {
  return (
    <RequirePermission permission="customers">
      <Suspense fallback={<Card flush><SkeletonRows rows={6} /></Card>}>
        <CarDetail />
      </Suspense>
    </RequirePermission>
  );
}

function CarDetail() {
  const { id } = useParams<{ id: string }>();
  const { can } = useSession();
  const car = useApi<Detail>(`/api/cars/${id}`);
  const history = useApi<Event[]>(`/api/cars/${id}/history`);
  const [mode, setMode] = useState<"view" | "edit" | "transfer">("view");
  const reload = () => { car.reload(); history.reload(); setMode("view"); };

  if (car.error) return <Card flush><ErrorState message={car.error} onRetry={car.reload} /></Card>;
  if (!car.data) return <Card flush><SkeletonRows rows={6} /></Card>;
  const c = car.data;

  return (
    <>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <div className="flex flex-wrap items-center gap-4">
          <Plate plate={c.plate} />
          <div>
            <h1>{carTitle(c)}</h1>
            <p className="text-muted">{[FUELS[c.fuel], c.color].filter(Boolean).join(", ")}</p>
          </div>
        </div>
        {mode === "view" && (
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" onClick={() => setMode("edit")}>Edit details</Button>
            {can("car-transfer") && <Button variant="secondary" onClick={() => setMode("transfer")}>Transfer owner</Button>}
          </div>
        )}
      </div>

      {mode === "edit" && <div className="mb-6"><Card title="Edit car"><CarForm car={c} onCancel={() => setMode("view")} onSaved={reload} /></Card></div>}
      {mode === "transfer" && <div className="mb-6"><TransferForm car={c} onCancel={() => setMode("view")} onDone={reload} /></div>}

      <div className="grid gap-4 shell:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)]">
        <div className="space-y-4">
          <Card title="Owner">
            {c.owner ? (
              <Link href={`/customers/${c.owner.id}`} className="flex min-h-11 flex-col justify-center rounded-control hover:bg-paper-2">
                <span className="font-medium underline">{c.owner.name}</span>
                <span className="flex gap-3 text-sm text-muted"><span>{c.owner.number}</span><span className="num">{phone(c.owner.phone)}</span></span>
              </Link>
            ) : <p className="text-muted">No current owner</p>}
          </Card>
          <Card title="Identity">
            <dl className="grid gap-4 sm:grid-cols-2">
              {[["VIN / chassis", c.vin], ["Engine", c.engine_no],
                ["Odometer", c.odometer_km != null ? `${c.odometer_km.toLocaleString("en-PK")} km` : ""]].map(([l, v]) => (
                <div key={l} className={`min-w-0 ${l === "VIN / chassis" ? "sm:col-span-2" : ""}`}>
                  <dt className="text-sm text-muted">{l}</dt>
                  <dd className={`num break-all ${v ? "" : "text-muted"}`}>{v || "Not recorded"}</dd>
                </div>
              ))}
            </dl>
            {c.notes && <p className="mt-4 text-ink-2">{c.notes}</p>}
          </Card>
        </div>

        <Card title="History" flush>
          {history.error ? <ErrorState message={history.error} onRetry={history.reload} />
            : !history.data ? <SkeletonRows />
            : (
              <ol className="relative px-4 py-2 shell:px-5">
                {history.data.map((e, i) => (
                  <li key={i} className="relative border-l border-rule py-3 pl-5">
                    <span aria-hidden="true" className={`absolute -left-[5px] top-[18px] size-[9px] rounded-full ${e.kind === "ownership" ? "bg-accent" : "bg-rule-strong"}`} />
                    <p className="text-sm text-muted">{e.on ? day(e.on) : when(e.at)}</p>
                    <p className="font-medium">{e.link ? <Link href={e.link} className="underline">{e.title}</Link> : e.title}</p>
                    {e.detail && <p className="text-ink-2">{e.detail}</p>}
                    {e.odometer_km != null && <p className="num text-sm text-muted">{e.odometer_km.toLocaleString("en-PK")} km</p>}
                  </li>
                ))}
              </ol>
            )}
          <p className="border-t border-rule px-4 py-3 text-sm text-muted shell:px-5">Repairs and invoices will appear here too once those screens are in use.</p>
        </Card>
      </div>

      {c.ownerships.length > 1 && (
        <div className="mt-4">
          <Card title="Previous owners" flush>
            <ul>
              {c.ownerships.filter((o) => o.until).map((o) => (
                <li key={o.id} className="flex flex-wrap items-center justify-between gap-3 border-t border-rule px-4 py-3 first:border-t-0 shell:px-5">
                  <span>
                    <Link href={`/customers/${o.customer.id}`} className="font-medium underline">{o.customer.name}</Link>
                    <span className="block text-sm text-muted">{day(o.since)} to {day(o.until)}</span>
                  </span>
                  <span className="flex flex-wrap gap-2">
                    {o.proofs.map((p) => <a key={p.id} href={p.url} target="_blank" rel="noreferrer" className="flex min-h-11 items-center text-accent underline">{p.name}</a>)}
                  </span>
                </li>
              ))}
            </ul>
          </Card>
        </div>
      )}
    </>
  );
}

function TransferForm({ car, onCancel, onDone }: { car: Detail; onCancel: () => void; onDone: () => void }) {
  const [to, setTo] = useState<Customer | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const since = car.ownerships.find((o) => !o.until)?.since;

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!to) { setError("Choose the new owner."); return; }
    const f = new FormData(e.currentTarget);
    setBusy(true);
    setError(null);
    try {
      const ids: string[] = [];
      for (const file of f.getAll("proof") as File[]) {
        if (!file.size) continue;
        const up = new FormData();
        up.set("file", file);
        up.set("note", "Ownership transfer proof");
        ids.push((await api<{ id: string }>("/api/attachments", { method: "POST", body: up })).id);
      }
      await api(`/api/cars/${car.id}/transfer`, { method: "POST", json: {
        to_customer_id: to.id, on: f.get("on"), reason: f.get("reason"),
        odometer_km: f.get("odometer_km") ? Number(f.get("odometer_km")) : null, attachment_ids: ids,
      } });
      onDone();
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  return (
    <Card title="Transfer to a new owner">
      <form onSubmit={submit} className="grid gap-5 sm:grid-cols-2">
        <div className="sm:col-span-2">
          <p className="mb-1.5 text-sm font-medium text-ink-2">New owner</p>
          <CustomerPicker value={to} onChange={setTo} exclude={car.owner?.id} />
          <p className="mt-1.5 text-sm text-muted">Not on file yet? Add them under Customers first.</p>
        </div>
        <Field label="Date of transfer"><Input name="on" type="date" defaultValue={today()} min={since} max={today()} required /></Field>
        <Field label="Odometer (km)"><Input name="odometer_km" type="number" inputMode="numeric" min={car.odometer_km ?? 0} /></Field>
        <div className="sm:col-span-2"><Field label="Reason" hint="e.g. Sold to new owner, transferred to company fleet"><Input name="reason" required minLength={3} maxLength={300} /></Field></div>
        <div className="sm:col-span-2">
          <Field label="Proof (optional)" hint="Photo or PDF of the transfer letter or registration book. Up to 10 MB each.">
            <input name="proof" type="file" multiple accept="image/*,application/pdf" capture="environment"
                   className="min-h-11 w-full rounded-control border border-dashed border-rule-strong bg-surface p-2 text-base file:mr-3 file:min-h-10 file:rounded-[3px] file:border-0 file:bg-paper-3 file:px-3" />
          </Field>
        </div>
        <div className="flex flex-col gap-3 sm:col-span-2">
          <Notice>{error}</Notice>
          <p className="text-sm text-muted">Past visits and invoices stay with the owner at the time. <Badge>Can&apos;t be undone</Badge></p>
          <div className="flex flex-wrap gap-2">
            <Button type="submit" disabled={busy}>{busy ? "Transferring" : "Transfer car"}</Button>
            <Button type="button" variant="secondary" onClick={onCancel}>Cancel</Button>
          </div>
        </div>
      </form>
    </Card>
  );
}
