"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Suspense, useState } from "react";
import { SearchBox, useQueryParam } from "@/components/search";
import { PURCHASING, RequirePermission } from "@/components/shell";
import { type Vendor, VendorForm } from "@/components/purchasing";
import { Button, Card, EmptyState, ErrorState, PageHeader, SkeletonRows } from "@/components/ui";
import { useApi } from "@/lib/api";
import { money, phone } from "@/lib/format";
import { useSession } from "@/lib/session";

export default function VendorsPage() {
  return (
    <RequirePermission permission={PURCHASING}>
      <Suspense fallback={<Card flush><SkeletonRows /></Card>}>
        <List />
      </Suspense>
    </RequirePermission>
  );
}

function List() {
  const router = useRouter();
  const { can } = useSession();
  const [q] = useQueryParam("q");
  const [adding, setAdding] = useState(false);
  const list = useApi<Vendor[]>(`/api/vendors?${new URLSearchParams({ q })}`);
  const owed = list.data?.reduce((s, v) => s + Number(v.owed ?? 0), 0) ?? 0;
  return (
    <>
      <PageHeader title="Vendors" description={list.data ? `We owe ${money(owed)} in total.` : "Who we buy from, and what we owe them."}
                  actions={can("vendors") && !adding && <Button onClick={() => setAdding(true)}>Add a vendor</Button>} />
      {adding && <div className="mb-4"><Card title="New vendor"><VendorForm onCancel={() => setAdding(false)} onSaved={(v) => router.push(`/vendors/${v.id}`)} /></Card></div>}
      <div className="mb-4 flex"><SearchBox placeholder="Name, phone or number" /></div>
      <Card flush>
        {list.error ? <ErrorState message={list.error} onRetry={list.reload} />
          : !list.data ? <SkeletonRows />
          : !list.data.length ? <EmptyState title="No vendors yet">{q ? `Nothing matches “${q}”.` : "Add the people you buy parts from, then write purchase orders to them."}</EmptyState>
          : (
            <table className="table-stack w-full">
              <thead><tr className="text-left text-sm text-muted">
                <th className="px-4 py-2 font-normal shell:px-5">Vendor</th><th className="px-4 py-2 font-normal">Phone</th>
                <th className="px-4 py-2 text-right font-normal shell:pr-5">We owe</th>
              </tr></thead>
              <tbody>
                {list.data.map((v) => (
                  <tr key={v.id} className="border-t border-rule">
                    <td className="px-4 py-3 shell:px-5 max-sm:px-0">
                      <Link href={`/vendors/${v.id}`} className="font-medium underline">{v.name}</Link>
                      <span className="block text-sm text-muted">{v.number}{v.contact_person ? `, ${v.contact_person}` : ""}</span>
                    </td>
                    <td data-label="Phone" className="num px-4 py-3 max-sm:px-0">{v.phone ? phone(v.phone) : ""}</td>
                    <td data-label="We owe" className="num px-4 py-3 text-right shell:pr-5 max-sm:px-0">{Number(v.owed) > 0 ? money(v.owed) : "Nothing"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
      </Card>
    </>
  );
}
