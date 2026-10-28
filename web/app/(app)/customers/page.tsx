"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Suspense, useState } from "react";
import { type Customer, CustomerForm } from "@/components/customers";
import { useQueryParam, SearchBox } from "@/components/search";
import { RequirePermission } from "@/components/shell";
import { Button, Card, EmptyState, ErrorState, PageHeader, SkeletonRows } from "@/components/ui";
import { useApi } from "@/lib/api";
import { phone } from "@/lib/format";

export default function CustomersPage() {
  return (
    <RequirePermission permission="customers">
      <Suspense fallback={<Card flush><SkeletonRows /></Card>}>
        <Customers />
      </Suspense>
    </RequirePermission>
  );
}

function Customers() {
  const router = useRouter();
  const [q] = useQueryParam("q");
  const list = useApi<Customer[]>(`/api/customers?${new URLSearchParams({ q, limit: "100" })}`);
  const [adding, setAdding] = useState(false);

  return (
    <>
      <PageHeader title="Customers" description="Everyone who brings a car in. Search by name, phone, customer number or plate."
                  actions={<Button onClick={() => setAdding(true)}>Add customer</Button>} />
      {adding && (
        <div className="mb-6">
          <Card title="New customer">
            <CustomerForm onCancel={() => setAdding(false)} onSaved={(c) => router.push(`/customers/${c.id}`)} />
          </Card>
        </div>
      )}
      <div className="mb-4 flex"><SearchBox placeholder="Search customers" autoFocus={!adding} /></div>
      <Card flush>
        {list.error ? <ErrorState message={list.error} onRetry={list.reload} />
          : !list.data ? <SkeletonRows />
          : !list.data.length ? (
            q ? <EmptyState title={`No customer matches “${q}”`}>Check the spelling, or search by phone or plate instead.</EmptyState>
              : <EmptyState title="No customers yet" action={<Button onClick={() => setAdding(true)}>Add customer</Button>}>
                  Customers are added here or while checking a car in.
                </EmptyState>
          ) : (
            <ul>
              {list.data.map((c) => (
                <li key={c.id} className="border-t border-rule first:border-t-0">
                  <Link href={`/customers/${c.id}`} className="flex min-h-14 flex-wrap items-center justify-between gap-x-6 gap-y-1 px-4 py-3 row-link pr-10 shell:pr-12 hover:bg-paper-2 shell:px-5">
                    <span className="min-w-0">
                      <span className="block font-medium">{c.name}{!c.is_active && <span className="ml-2 text-sm text-muted">inactive</span>}</span>
                      <span className="block text-sm text-muted">{c.number}</span>
                    </span>
                    <span className="num text-ink-2">{phone(c.phone)}</span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
      </Card>
    </>
  );
}
