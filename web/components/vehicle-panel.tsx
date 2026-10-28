"use client";

import Link from "next/link";
import { useState } from "react";
import { type Car, CarForm, carTitle, FUELS } from "@/components/cars";
import { type Customer, CustomerForm } from "@/components/customers";
import { Button, Card, ErrorState, SkeletonRows } from "@/components/ui";
import { useApi } from "@/lib/api";
import { phone } from "@/lib/format";
import { useSession } from "@/lib/session";

type CarFields = Pick<Car, "plate" | "vin" | "engine_no" | "make" | "model" | "year" | "color" | "fuel"> & { odometer_km?: number | null };
type Person = { id?: string; name: string; phone: string; number: string };
/** The copy stored on a signed document (app/routers/workshop.py snapshot_of). */
export type Snapshot = { car: CarFields; owner: Person; buyer: Person | null };

/**
 * The one place a car and its people are shown on a visit or document. It reads
 * the central car and customer records, and Edit changes those records, so a
 * correction made here shows everywhere. Pass `frozen` for a signed document:
 * it then shows the copy taken at signing, read-only.
 */
export function VehiclePanel({ carId, ownerId, buyerId, frozen, onChange }:
  { carId: string; ownerId: string; buyerId?: string | null; frozen?: Snapshot | null; onChange?: () => void }) {
  if (frozen) return <PanelBody car={frozen.car} owner={frozen.owner} buyer={frozen.buyer} note="As recorded when the report was signed." />;
  return <LivePanel carId={carId} ownerId={ownerId} buyerId={buyerId} onChange={onChange} />;
}

function LivePanel({ carId, ownerId, buyerId, onChange }: { carId: string; ownerId: string; buyerId?: string | null; onChange?: () => void }) {
  const { can } = useSession();
  const car = useApi<Car>(`/api/cars/${carId}`);
  const owner = useApi<Customer>(`/api/customers/${ownerId}`);
  const buyer = useApi<Customer>(buyerId ? `/api/customers/${buyerId}` : null);
  const [editing, setEditing] = useState<"car" | "owner" | "buyer" | null>(null);

  const error = car.error ?? owner.error ?? buyer.error;
  if (error) return <Card flush><ErrorState message={error} onRetry={() => { car.reload(); owner.reload(); buyer.reload(); }} /></Card>;
  if (!car.data || !owner.data || (buyerId && !buyer.data)) return <Card flush><SkeletonRows rows={3} /></Card>;

  const saved = (reload: () => void) => () => { setEditing(null); reload(); onChange?.(); };
  if (editing === "car") {
    return <Card title="Edit car"><CarForm car={car.data} onSaved={saved(car.reload)} onCancel={() => setEditing(null)} /></Card>;
  }
  if (editing) {
    const who = editing === "owner" ? owner : buyer;
    return (
      <Card title={`Edit ${editing}`}>
        <CustomerForm customer={who.data!} onSaved={saved(who.reload)} onCancel={() => setEditing(null)} />
      </Card>
    );
  }
  return (
    <PanelBody car={car.data} owner={owner.data} buyer={buyer.data} carId={carId}
               note="Edits change the car and customer records everywhere."
               onEdit={can("customers") ? setEditing : undefined} />
  );
}

function PanelBody({ car, owner, buyer, carId, note, onEdit }:
  { car: CarFields; owner: Person; buyer: Person | null; carId?: string; note: string; onEdit?: (what: "car" | "owner" | "buyer") => void }) {
  const facts: [string, string][] = [
    ["Number plate", car.plate], ["VIN / chassis number", car.vin], ["Engine number", car.engine_no],
    ["Fuel", FUELS[car.fuel] ?? ""], ["Colour", car.color],
    ...(car.odometer_km != null ? [["Odometer", `${car.odometer_km.toLocaleString("en-PK")} km`] as [string, string]] : []),
  ];
  return (
    <Card title="Vehicle and people" actions={onEdit && <Button variant="ghost" onClick={() => onEdit("car")}>Edit car</Button>}>
      <p className="font-medium">
        {carId ? <Link href={`/cars/${carId}`} className="underline">{carTitle(car)}</Link> : carTitle(car)}
      </p>
      <dl className="mt-4 grid gap-4 sm:grid-cols-2 shell:grid-cols-3">
        {facts.map(([l, v]) => (
          <div key={l}><dt className="text-sm text-muted">{l}</dt><dd className={v ? "num break-all" : "text-muted"}>{v || "Not recorded"}</dd></div>
        ))}
      </dl>
      <div className="mt-5 grid gap-4 border-t border-rule pt-4 sm:grid-cols-2">
        <PersonRow label={buyer ? "Owner (seller)" : "Owner"} p={owner} onEdit={onEdit && (() => onEdit("owner"))} />
        {buyer && <PersonRow label="Buyer" p={buyer} onEdit={onEdit && (() => onEdit("buyer"))} />}
      </div>
      <p className="mt-4 text-sm text-muted">{note}</p>
    </Card>
  );
}

function PersonRow({ label, p, onEdit }: { label: string; p: Person; onEdit?: () => void }) {
  return (
    <div className="flex items-start justify-between gap-3">
      <div className="min-w-0">
        <p className="text-sm text-muted">{label}</p>
        <p className="font-medium">{p.id ? <Link href={`/customers/${p.id}`} className="underline">{p.name}</Link> : p.name}</p>
        <p className="flex flex-wrap gap-3 text-sm text-muted">
          <span>{p.number}</span>
          {p.phone && <a href={`tel:${p.phone}`} className="num">{phone(p.phone)}</a>}
        </p>
      </div>
      {onEdit && <Button variant="ghost" onClick={onEdit}>Edit</Button>}
    </div>
  );
}
