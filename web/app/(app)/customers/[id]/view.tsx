"use client";

import { DeleteButton } from "@/components/delete-button";
import Link from "next/link";
import { NextStep } from "@/components/next-step";
import { useParams, useRouter } from "next/navigation";
import { Suspense, useState } from "react";
import { type Car, CarForm, carTitle } from "@/components/cars";
import { type Customer, CustomerForm } from "@/components/customers";
import { RequirePermission } from "@/components/shell";
import { Badge, Button, Card, EmptyState, ErrorState, PageHeader, SkeletonRows } from "@/components/ui";
import { useApi } from "@/lib/api";
import { day, phone } from "@/lib/format";

type Detail = Customer & { cars: (Car & { since: string; until: string | null })[] };

export default function CustomerPage() {
  return (
    <RequirePermission permission="customers">
      <Suspense fallback={<Card flush><SkeletonRows /></Card>}>
        <CustomerDetail />
      </Suspense>
    </RequirePermission>
  );
}

function CustomerDetail() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { data, error, reload } = useApi<Detail>(`/api/customers/${id}`);
  const [editing, setEditing] = useState(false);
  const [addingCar, setAddingCar] = useState(false);

  if (error) return <Card flush><ErrorState message={error} onRetry={reload} /></Card>;
  if (!data) return <Card flush><SkeletonRows rows={6} /></Card>;
  const current = data.cars.filter((c) => !c.until);
  const past = data.cars.filter((c) => c.until);

  return (
    <>
      <PageHeader
        title={data.name}
        description={`${data.number}${data.kind === "company" ? ", company or fleet" : ""}`}
        actions={!editing && <><Button variant="secondary" onClick={() => setEditing(true)}>Edit details</Button><DeleteButton path={`/api/customers/${data.id}`} what="customer" goTo="/customers" label="Delete customer" /></>}
      />
      {!editing && (current.length === 0
        ? <NextStep who="Front desk" target="act-add-car" label="Add car">This customer has no car yet. Add the car, then check it in.</NextStep>
        : <NextStep who="Front desk" href={`/visits/new?car=${current[0].id}`} label="Check in this car">The car is here? Check it in to start a job.</NextStep>)}

      <div className="grid gap-4 shell:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
        <Card title="Contact">
          {editing ? (
            <CustomerForm customer={data} onCancel={() => setEditing(false)} onSaved={() => { setEditing(false); reload(); }} />
          ) : (
            <dl className="grid gap-4">
              {[
                ["Mobile", <a key="p" href={`tel:${data.phone}`} className="num underline">{phone(data.phone)}</a>],
                ["Other phone", data.phone_alt ? phone(data.phone_alt) : null],
                ["Email", data.email || null],
                ...(data.kind === "company" ? [["NTN", data.ntn || null] as const] : [["CNIC", data.cnic || null] as const]),
                ["Address", data.address || null],
                ["Notes", data.notes || null],
              ].map(([label, value]) => (
                <div key={label as string}>
                  <dt className="text-sm text-muted">{label}</dt>
                  <dd className={value ? "break-words" : "text-muted"}>{value ?? "Not given"}</dd>
                </div>
              ))}
              {data.whatsapp_opt_out && <Badge tone="warning">No WhatsApp messages</Badge>}
              {!data.is_active && <Badge>Inactive</Badge>}
            </dl>
          )}
        </Card>

        <Card title="Cars" actions={<Button id="act-add-car" variant="secondary" onClick={() => setAddingCar(true)}>Add car</Button>} flush>
          {addingCar && (
            <div className="border-b border-rule p-4 shell:p-5">
              <CarForm ownerId={data.id} onCancel={() => setAddingCar(false)} onSaved={(c) => router.push(`/cars/${c.id}`)} />
            </div>
          )}
          {!data.cars.length ? (
            <EmptyState title="No cars yet">Add the cars this customer brings in.</EmptyState>
          ) : (
            <ul>
              {[...current, ...past].map((c) => (
                <li key={`${c.id}-${c.since}`} className="border-t border-rule first:border-t-0">
                  <Link href={`/cars/${c.id}`} className="flex min-h-14 flex-wrap items-center justify-between gap-x-4 gap-y-1 px-4 py-3 row-link pr-10 shell:pr-12 hover:bg-paper-2 shell:px-5">
                    <span>
                      <span className="block font-medium">{c.plate || "No plate"}</span>
                      <span className="block text-sm text-muted">{carTitle(c)}</span>
                    </span>
                    {c.until ? <span className="text-sm text-muted">Owned until {day(c.until)}</span> : <Badge tone="success">Current</Badge>}
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </>
  );
}
