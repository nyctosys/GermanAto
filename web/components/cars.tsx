"use client";

import { useRef, useState, type FormEvent } from "react";
import { Button, Field, Input, Notice, Select } from "@/components/ui";
import { api } from "@/lib/api";

export type Car = {
  id: string; plate: string; vin: string; engine_no: string; make: string; model: string;
  year: number | null; color: string; fuel: string; odometer_km: number | null; notes: string; version: number;
  owner: { id: string; name: string; number: string; phone: string } | null;
};

export const FUELS: Record<string, string> = {
  petrol: "Petrol", diesel: "Diesel", hybrid: "Hybrid", ev: "Electric", cng: "CNG", other: "Other",
};

export const carTitle = (c: Pick<Car, "make" | "model" | "year">) => [c.year, c.make, c.model].filter(Boolean).join(" ");

/** Add a car to an owner, or edit one. */
export function CarForm({ car, ownerId, onSaved, onCancel }:
  { car?: Car; ownerId?: string; onSaved: (c: Car) => void; onCancel: () => void }) {
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const form = useRef<HTMLFormElement>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    const f = new FormData(form.current!);
    const num = (k: string) => (f.get(k) ? Number(f.get(k)) : null);
    const body = {
      plate: f.get("plate"), vin: f.get("vin"), engine_no: f.get("engine_no"),
      make: f.get("make"), model: f.get("model"), year: num("year"), color: f.get("color"), fuel: f.get("fuel"),
      odometer_km: num("odometer_km"), notes: f.get("notes"),
    };
    setBusy(true);
    setError(null);
    try {
      onSaved(car
        ? await api<Car>(`/api/cars/${car.id}`, { method: "PUT", json: { ...body, version: car.version } })
        : await api<Car>("/api/cars", { method: "POST", json: { ...body, owner_id: ownerId } }));
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  return (
    <form ref={form} onSubmit={submit} className="grid gap-5 sm:grid-cols-2 shell:grid-cols-3">
      <Field label="Number plate" hint="As written, e.g. LEA-21-1234"><Input name="plate" defaultValue={car?.plate} maxLength={20} autoCapitalize="characters" /></Field>
      <Field label="Make"><Input name="make" defaultValue={car?.make} required placeholder="BMW" /></Field>
      <Field label="Model"><Input name="model" defaultValue={car?.model} placeholder="520i" /></Field>
      <Field label="Year"><Input name="year" type="number" inputMode="numeric" min={1950} max={new Date().getFullYear() + 1} defaultValue={car?.year ?? ""} /></Field>
      <Field label="Fuel">
        <Select name="fuel" defaultValue={car?.fuel ?? "petrol"}>
          {Object.entries(FUELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </Select>
      </Field>
      <Field label="Colour"><Input name="color" defaultValue={car?.color} /></Field>
      <Field label="VIN / chassis number" hint="As stamped on the car, e.g. NZE141-6012345. Optional."><Input name="vin" defaultValue={car?.vin} maxLength={30} autoCapitalize="characters" spellCheck={false} /></Field>
      <Field label="Engine number"><Input name="engine_no" defaultValue={car?.engine_no} autoCapitalize="characters" spellCheck={false} /></Field>
      <Field label="Odometer (km)"><Input name="odometer_km" type="number" inputMode="numeric" min={0} defaultValue={car?.odometer_km ?? ""} /></Field>
      <div className="sm:col-span-2"><Field label="Notes"><Input name="notes" defaultValue={car?.notes} /></Field></div>
      <div className="flex flex-col gap-3 sm:col-span-2 shell:col-span-3">
        <Notice>{error}</Notice>
        <div className="flex flex-wrap gap-2">
          <Button type="submit" disabled={busy}>{busy ? "Saving" : car ? "Save changes" : "Add car"}</Button>
          <Button type="button" variant="secondary" onClick={onCancel}>Cancel</Button>
        </div>
      </div>
    </form>
  );
}

/** The number plate, set like the real thing: the way staff recognise a car. */
export function Plate({ plate, small = false }: { plate: string; small?: boolean }) {
  return (
    <span className={`num inline-flex shrink-0 items-center rounded-control border-2 border-ink bg-surface font-semibold tracking-wide text-ink ${small ? "min-w-28 justify-center px-2 py-0.5 text-sm" : "px-4 py-1.5 text-2xl"}`}>
      {plate || "No plate"}
    </span>
  );
}
