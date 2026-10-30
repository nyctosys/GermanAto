"use client";

import { DeleteButton } from "@/components/delete-button";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Suspense, useState } from "react";
import { linkButton } from "@/components/estimates";
import { PoBadge, type PoStatus, type Vendor, VendorForm } from "@/components/purchasing";
import { PURCHASING, RequirePermission } from "@/components/shell";
import { Badge, Button, Card, EmptyState, ErrorState, SkeletonRows } from "@/components/ui";
import { useApi } from "@/lib/api";
import { day, money, phone, when } from "@/lib/format";
import { useSession } from "@/lib/session";

type Entry = { at: string; kind: "bill" | "payment"; id: string; number: string; void: boolean; detail: string | null; amount: string; balance: string };
type Detail = Vendor & { ledger: Entry[]; purchase_orders: { id: string; number: string; status: PoStatus; created_at: string }[] };

export default function VendorPage() {
  return (
    <RequirePermission permission={PURCHASING}>
      <Suspense fallback={<Card flush><SkeletonRows rows={6} /></Card>}>
        <View />
      </Suspense>
    </RequirePermission>
  );
}

function View() {
  const { id } = useParams<{ id: string }>();
  const { can } = useSession();
  const v = useApi<Detail>(`/api/vendors/${id}`);
  const [editing, setEditing] = useState(false);
  if (v.error) return <Card flush><ErrorState message={v.error} onRetry={v.reload} /></Card>;
  if (!v.data) return <Card flush><SkeletonRows rows={6} /></Card>;
  const d = v.data;
  return (
    <>
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1>{d.name}</h1>
          <p className="text-muted">{d.number}{d.is_active ? "" : ", inactive"}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {can("purchasing") && d.is_active && <Link href={`/purchase-orders/new?vendor=${d.id}`} className={linkButton}>New purchase order</Link>}
          {can("vendors") && !editing && <><Button variant="secondary" onClick={() => setEditing(true)}>Edit</Button><DeleteButton path={`/api/vendors/${d.id}`} what="vendor" goTo="/vendors" label="Delete vendor" /></>}
        </div>
      </div>
      <div className="grid gap-4 shell:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
        <div className="space-y-4">
          {editing && <Card title="Edit vendor"><VendorForm vendor={d} onCancel={() => setEditing(false)} onSaved={() => { setEditing(false); v.reload(); }} /></Card>}
          <Card title="Account" actions={<span className="num font-medium">{Number(d.owed) > 0 ? `We owe ${money(d.owed)}` : "Nothing owed"}</span>} flush>
            {!d.ledger.length ? <EmptyState title="No bills yet">Bills appear here when goods received from this vendor are billed.</EmptyState> : (
              <ul>
                {d.ledger.map((e) => (
                  <li key={`${e.kind}-${e.number}`} className="flex flex-wrap items-start justify-between gap-3 border-t border-rule px-4 py-3 first:border-t-0 shell:px-5">
                    <span className="min-w-0">
                      <Link href={`/bills/${e.id}`} className={`block font-medium underline ${e.void ? "text-muted line-through" : ""}`}>{e.number}</Link>
                      <span className="block text-sm text-muted">{e.kind === "bill" ? "Bill" : "Payment"}, {when(e.at)}{e.detail ? `, ${e.detail}` : ""}{e.void ? ", voided" : ""}</span>
                    </span>
                    <span className="text-right">
                      <span className={`num block ${e.void ? "text-muted line-through" : Number(e.amount) < 0 ? "text-success" : ""}`}>{Number(e.amount) < 0 ? `-${money(-Number(e.amount))}` : money(e.amount)}</span>
                      <span className="num block text-sm text-muted">Owed after: {money(e.balance)}</span>
                    </span>
                  </li>
                ))}
              </ul>
            )}
            <p className="border-t border-rule px-4 py-3 text-sm text-muted shell:px-5">Worked out from bills and payments each time; it is never typed in.</p>
          </Card>
        </div>
        <div className="space-y-4">
          <Card title="Details">
            <dl className="space-y-3">
              {[["Contact", d.contact_person], ["Phone", d.phone ? phone(d.phone) : ""], ["Email", d.email], ["Address", d.address],
                ["Pays within", d.terms_days ? `${d.terms_days} days` : "Due at once"], ["Notes", d.notes]].map(([l, t]) => (
                <div key={l}><dt className="text-sm text-muted">{l}</dt><dd className={t ? "" : "text-muted"}>{t || "None"}</dd></div>
              ))}
            </dl>
          </Card>
          <Card title="Purchase orders" flush>
            {d.purchase_orders.length ? (
              <ul>
                {d.purchase_orders.map((p) => (
                  <li key={p.id}>
                    <Link href={`/purchase-orders/${p.id}`} className="flex min-h-14 items-center justify-between gap-3 border-t border-rule px-4 py-3 first:border-t-0 row-link pr-10 shell:pr-12 hover:bg-paper-2 shell:px-5">
                      <span><span className="block font-medium">{p.number}</span><span className="block text-sm text-muted">{day(p.created_at)}</span></span>
                      <PoBadge status={p.status} />
                    </Link>
                  </li>
                ))}
              </ul>
            ) : <p className="px-4 py-4 text-muted shell:px-5">No orders yet. <Badge>Start one above</Badge></p>}
          </Card>
        </div>
      </div>
    </>
  );
}
