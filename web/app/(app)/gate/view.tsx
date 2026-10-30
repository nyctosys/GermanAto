"use client";

import { useState, type FormEvent } from "react";
import { RequirePermission } from "@/components/shell";
import { Badge, Button, Card, EmptyState, ErrorState, Field, Input, Notice, PageHeader, SkeletonRows } from "@/components/ui";
import { api, useApi } from "@/lib/api";
import { useFormErrors } from "@/lib/form";
import { money, when } from "@/lib/format";
import { gatePassSchemaAt, parseForm } from "@/lib/schemas";
import { Plate } from "@/components/cars";

type Car = { id: string; number: string; plate: string; car: string; customer: string; invoice: string | null; balance: string; odometer_in: number | null; can_release: boolean };

export default function GatePage() {
  const [released, setReleased] = useState(0);  // a release refreshes the list of cars that have left
  return (
    <RequirePermission permission={["gate", "visits"]}>
      <PageHeader title="Cars ready to leave" description="Repaired, invoiced and checked. Hand the car over only after you have checked the paperwork." />
      <Cars onReleased={() => setReleased((n) => n + 1)} />
      <History key={released} />
    </RequirePermission>
  );
}

type Left = { id: string; number: string; plate: string; car: string; customer: string; left_at: string; handed_to: string; released_by: string | null;
  odometer_in: number | null; odometer_out: number | null; on_credit: boolean; credit_reason: string };

/** Cars that have already left, newest first. */
function History() {
  const [q, setQ] = useState("");
  const list = useApi<Left[]>(`/api/gate/history?${new URLSearchParams({ q })}`);
  return (
    <div className="mt-8">
      <h2 className="mb-3 text-lg font-semibold">Cars that have left</h2>
      <Input aria-label="Search cars that have left" placeholder="Plate, customer, visit or who collected" value={q} onChange={(e) => setQ(e.target.value)} className="mb-3" />
      <Card flush>
        {list.error ? <ErrorState message={list.error} onRetry={list.reload} /> : !list.data ? <SkeletonRows rows={3} />
          : !list.data.length ? <EmptyState title="No cars have left yet">Each car you release is listed here with who took it.</EmptyState> : (
            <ul>
              {list.data.map((r) => (
                <li key={r.id} className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2 border-t border-rule px-4 py-3 first:border-t-0 shell:px-5">
                  <div className="flex flex-wrap items-center gap-3"><Plate plate={r.plate} small /><span><span className="block font-medium">{r.car}</span><span className="block text-sm text-muted">{r.customer}, {r.number}</span></span></div>
                  <div className="text-sm text-muted sm:text-right">
                    <span className="block">{when(r.left_at)}</span>
                    <span className="block">Taken by {r.handed_to || "not written down"}. Released by {r.released_by ?? "unknown"}.</span>
                    {r.on_credit && <Badge tone="warning">Left owing money: {r.credit_reason}</Badge>}
                  </div>
                </li>
              ))}
            </ul>
          )}
      </Card>
    </div>
  );
}

function Cars({ onReleased }: { onReleased: () => void }) {
  const list = useApi<Car[]>("/api/gate/queue");
  const [open, setOpen] = useState<string | null>(null);
  if (list.error) return <Card flush><ErrorState message={list.error} onRetry={list.reload} /></Card>;
  if (!list.data) return <Card flush><SkeletonRows rows={3} /></Card>;
  if (!list.data.length) return <Card flush><EmptyState title="No car is ready to leave">When a repair is finished and invoiced, the car appears here by itself.</EmptyState></Card>;
  return (
    <ul className="grid gap-4">
      {list.data.map((c) => (
        <li key={c.id}>
          <Card>
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div className="flex flex-wrap items-center gap-4">
                <Plate plate={c.plate} />
                <div><p className="text-lg font-medium">{c.car}</p><p className="text-muted">{c.customer}{c.invoice ? `, invoice ${c.invoice}` : ""}</p></div>
              </div>
              {c.can_release && open !== c.id
                ? <Button onClick={() => setOpen(c.id)}>Release this car</Button>
                : !c.can_release && <Badge tone="error">Owes {money(c.balance)}</Badge>}
            </div>
            {!c.can_release && <div className="mt-3"><Notice tone="warning">Do not release this car. It still owes {money(c.balance)}. Send the customer to the cashier. Only an administrator can release it on credit.</Notice></div>}
            {open === c.id && <Release car={c} onDone={() => { setOpen(null); list.reload(); onReleased(); }} onCancel={() => setOpen(null)} />}
          </Card>
        </li>
      ))}
    </ul>
  );
}

function Release({ car, onDone, onCancel }: { car: Car; onDone: () => void; onCancel: () => void }) {
  const schema = () => gatePassSchemaAt({ minOut: car.odometer_in, requireHandedTo: true });
  const { errors, setErrors, live, applyApi } = useFormErrors(schema);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const { data, errors } = parseForm(schema(), e.currentTarget);
    setErrors(errors ?? {});
    if (!data) return;
    setBusy(true);
    setError(null);
    try {
      await api(`/api/visits/${car.id}/gate-pass`, { method: "POST", json: data, toast: `${car.plate} released` });
      onDone();
    } catch (err) {
      setError(applyApi(err));
      setBusy(false);
    }
  }
  return (
    <form noValidate onSubmit={submit} className="mt-4 grid gap-4 border-t border-rule pt-4 sm:grid-cols-2" {...live}>
      <Field label="Odometer reading now" hint={car.odometer_in ? `It was ${car.odometer_in.toLocaleString()} km at check-in.` : undefined} error={errors.odometer_out}>
        <Input name="odometer_out" inputMode="numeric" autoFocus />
      </Field>
      <Field label="Who is taking the car" error={errors.handed_to}><Input name="handed_to" maxLength={120} /></Field>
      <div className="sm:col-span-2"><Field label="Note (optional)"><Input name="note" maxLength={500} /></Field></div>
      <div className="flex flex-col gap-3 sm:col-span-2">
        <Notice>{error}</Notice>
        <div className="flex flex-wrap gap-2"><Button type="submit" disabled={busy}>{busy ? "Releasing" : "Release the car"}</Button><Button type="button" variant="danger" onClick={onCancel}>Cancel</Button></div>
      </div>
    </form>
  );
}
