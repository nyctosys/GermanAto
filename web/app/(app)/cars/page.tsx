"use client";

import Link from "next/link";
import { Suspense } from "react";
import { type Car, carTitle, Plate } from "@/components/cars";
import { useQueryParam, SearchBox } from "@/components/search";
import { RequirePermission } from "@/components/shell";
import { Card, EmptyState, ErrorState, PageHeader, SkeletonRows } from "@/components/ui";
import { useApi } from "@/lib/api";

export default function CarsPage() {
  return (
    <RequirePermission permission="customers">
      <PageHeader title="Cars" description="Search by plate, VIN, chassis number, make or owner. New cars are added from the owner's page." />
      <Suspense fallback={<Card flush><SkeletonRows /></Card>}>
        <Cars />
      </Suspense>
    </RequirePermission>
  );
}

function Cars() {
  const [q] = useQueryParam("q");
  const list = useApi<Car[]>(`/api/cars?${new URLSearchParams({ q, limit: "100" })}`);
  return (
    <>
      <div className="mb-4 flex"><SearchBox placeholder="Plate, VIN, make or owner" autoFocus /></div>
      <Card flush>
        {list.error ? <ErrorState message={list.error} onRetry={list.reload} />
          : !list.data ? <SkeletonRows />
          : !list.data.length ? (
            <EmptyState title={q ? `No car matches “${q}”` : "No cars yet"}>
              {q ? "Try part of the plate, or the owner's name." : "Open a customer and add their car."}
            </EmptyState>
          ) : (
            <ul>
              {list.data.map((c) => (
                <li key={c.id} className="border-t border-rule first:border-t-0">
                  <Link href={`/cars/${c.id}`} className="flex min-h-14 flex-wrap items-center justify-between gap-x-6 gap-y-1 px-4 py-3 hover:bg-paper-2 shell:px-5">
                    <span className="flex min-w-0 items-center gap-4">
                      <Plate plate={c.plate} small />
                      <span className="min-w-0">
                        <span className="block font-medium">{carTitle(c)}</span>
                        {c.vin && <span className="num block text-sm text-muted">{c.vin}</span>}
                      </span>
                    </span>
                    <span className="text-ink-2">{c.owner?.name ?? "No owner"}</span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
      </Card>
    </>
  );
}
