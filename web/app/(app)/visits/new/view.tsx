"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { type Uploaded, PhotoCapture, SignaturePad, upload } from "@/components/capture";
import { type Car, carTitle, Plate } from "@/components/cars";
import { type Customer, CustomerPicker } from "@/components/customers";
import { Segments } from "@/components/search";
import { RequirePermission } from "@/components/shell";
import { Button, Card, Field, Input, Notice, PageHeader } from "@/components/ui";
import { VehiclePanel } from "@/components/vehicle-panel";
import { FuelGauge } from "@/components/visits";
import { api, ApiError } from "@/lib/api";
import { useFormErrors } from "@/lib/form";
import { checkInSchemaAt, parseForm } from "@/lib/schemas";

export default function CheckInPage() {
  const [car, setCar] = useState<Car | null>(null);
  return (
    <RequirePermission permission="visits">
      <PageHeader title="Check in a car" description="Find the car, record its condition, and have the customer sign." />
      {car ? <CheckInForm car={car} onChangeCar={() => setCar(null)} /> : <FindCar onPick={setCar} />}
    </RequirePermission>
  );
}

function FindCar({ onPick }: { onPick: (c: Car) => void }) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<Car[] | null>(null);

  useEffect(() => {
    if (q.trim().length < 2) return;
    const t = setTimeout(() => api<Car[]>(`/api/cars?${new URLSearchParams({ q, limit: "10" })}`).then(setResults), 200);
    return () => clearTimeout(t);
  }, [q]);

  return (
    <Card title="Which car?">
      <Field label="Plate, VIN / chassis number or owner's name">
        <Input value={q} onChange={(e) => setQ(e.target.value)} autoFocus autoCapitalize="characters" spellCheck={false} enterKeyHint="search" />
      </Field>
      {results && q.trim().length >= 2 && (
        <ul className="mt-4 divide-y divide-rule rounded-control border border-rule">
          {results.map((c) => (
            <li key={c.id}>
              <button onClick={() => onPick(c)} className="flex min-h-14 w-full flex-wrap items-center gap-4 px-3 py-2 text-left hover:bg-paper-2 active:bg-paper-3">
                <Plate plate={c.plate} small />
                <span className="min-w-0">
                  <span className="block font-medium">{carTitle(c)}</span>
                  <span className="block text-sm text-muted">{c.owner?.name ?? "No owner"}</span>
                </span>
              </button>
            </li>
          ))}
          {!results.length && <li className="px-3 py-4 text-muted">No car matches “{q}”.</li>}
        </ul>
      )}
      <p className="mt-4 text-sm text-muted">
        A new car? Add it from its owner&apos;s page under <Link href="/customers" className="underline">Customers</Link>, then come back.
      </p>
    </Card>
  );
}

function CheckInForm({ car, onChangeCar }: { car: Car; onChangeCar: () => void }) {
  const router = useRouter();
  const [kind, setKind] = useState<"workshop" | "pre_purchase">("workshop");
  const [buyer, setBuyer] = useState<Customer | null>(null);
  const [fuel, setFuel] = useState<number | null>(null);
  const [photos, setPhotos] = useState<Uploaded[]>([]);
  const [signature, setSignature] = useState<Blob | null>(null);
  const [error, setError] = useState<string | null>(null);
  const schema = () => checkInSchemaAt(car.odometer_km);
  const { errors, setErrors, live, applyApi } = useFormErrors(schema);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const { data: f, errors } = parseForm(schema(), e.currentTarget);
    const buyerMissing = kind === "pre_purchase" && !buyer;
    setErrors({ ...errors, ...(buyerMissing ? { buyer: "Choose the buyer" } : {}) });
    if (!f || buyerMissing) return;
    setBusy(true);
    setError(null);
    try {
      const sig = signature ? await upload(signature, "check-in-signature.png", "Customer signature at check-in") : null;
      const visit = await api<{ id: string }>("/api/visits", { method: "POST", json: {
        car_id: car.id, kind, buyer_id: kind === "pre_purchase" ? buyer?.id ?? null : null, ...f, fuel_eighths: fuel,
        photo_ids: photos.map((p) => p.id), signature_id: sig?.id ?? null,
      } });
      router.push(`/visits/${visit.id}`);
    } catch (err) {
      const d = err instanceof ApiError ? (err.detail as { visit_id?: string }) : undefined;
      if (d?.visit_id) { router.push(`/visits/${d.visit_id}`); return; }
      setError(applyApi(err));
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} noValidate className="space-y-4" {...live}>
      {car.owner ? <VehiclePanel carId={car.id} ownerId={car.owner.id} />
        : <Notice>This car has no owner on file. Add or transfer it to a customer first.</Notice>}
      <Button type="button" variant="ghost" onClick={onChangeCar}>Different car</Button>

      <Card title="Why it's here">
        <div className="grid gap-5 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <p className="mb-1.5 text-sm font-medium text-ink-2">Visit type</p>
            <Segments value={kind} onChange={(v) => setKind(v as typeof kind)}
                      options={[{ value: "workshop", label: "Repair or service" }, { value: "pre_purchase", label: "Pre-purchase inspection" }]} />
          </div>
          {kind === "pre_purchase" && (
            <div className="sm:col-span-2">
              <p className="mb-1.5 text-sm font-medium text-ink-2">Buyer</p>
              <CustomerPicker value={buyer} onChange={setBuyer} exclude={car.owner?.id} />
              {errors.buyer && <p role="alert" className="mt-1 text-sm text-error">{errors.buyer}</p>}
              <p className="mt-1 text-sm text-muted">The person buying the car. The current owner is the seller. A new buyer? Add them under <Link href="/customers" className="underline">Customers</Link> first.</p>
            </div>
          )}
          <div className="sm:col-span-2">
            <Field error={errors.complaint} label="What the customer says" hint="In their words: noises, warning lights, what they want done.">
              <textarea name="complaint" rows={3} maxLength={3000}
                        className="w-full rounded-control border border-rule-strong bg-surface px-3 py-2.5 text-base focus-visible:border-accent" />
            </Field>
          </div>
          <Field error={errors.odometer_in} label="Odometer (km)" hint={car.odometer_km ? `Last reading ${car.odometer_km.toLocaleString("en-PK")} km` : undefined}>
            <Input name="odometer_in" type="number" inputMode="numeric" min={car.odometer_km ?? 0} required />
          </Field>
          <div>
            <p className="mb-1.5 text-sm font-medium text-ink-2">Fuel</p>
            <FuelGauge value={fuel} onChange={setFuel} />
          </div>
        </div>
      </Card>

      <Card title="Condition">
        <div className="space-y-5">
          <PhotoCapture value={photos} onChange={setPhotos} note="Check-in photo" label="Take photos of all four sides" />
          <Field error={errors.condition_notes} label="Existing damage" hint="Dents, scratches, cracked glass: anything the customer should agree was already there.">
            <Input name="condition_notes" maxLength={3000} />
          </Field>
          <Field error={errors.items_left} label="Valuables left in the car"><Input name="items_left" maxLength={1000} placeholder="e.g. sunglasses in the glovebox" /></Field>
        </div>
      </Card>

      <Card title="Customer signature">
        <SignaturePad label="Customer agrees with the condition recorded above" onChange={setSignature} />
      </Card>

      <Notice>{error}</Notice>
      <div className="flex flex-wrap gap-2">
        <Button type="submit" disabled={busy}>{busy ? "Checking in" : "Check in"}</Button>
        <Link href="/visits" className="flex min-h-11 items-center rounded-control border border-rule-strong bg-surface px-4 font-medium">Cancel</Link>
      </div>
    </form>
  );
}
