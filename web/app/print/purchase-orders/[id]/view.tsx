"use client";

import { useParams } from "next/navigation";
import { Suspense } from "react";
import { type Po } from "@/components/purchasing";
import { Grid, Letterhead, PrintBar } from "@/components/print";
import { useApi } from "@/lib/api";
import { day, money, phone, qty } from "@/lib/format";

export default function PrintPo() {
  return <Suspense fallback={<p className="p-8">Loading</p>}><Doc /></Suspense>;
}

function Doc() {
  const { id } = useParams<{ id: string }>();
  const po = useApi<Po>(`/api/purchase-orders/${id}`);
  const branch = useApi<{ name: string; address: string; phone: string }>("/api/branch");
  if (po.error) return <p className="p-8 text-error">{po.error}</p>;
  if (!po.data || !branch.data) return <p className="p-8">Loading</p>;
  const p = po.data;
  return (
    <div className="mx-auto max-w-[210mm] px-4 py-4 sm:px-[12mm] sm:py-[10mm] text-[12px] leading-snug print:p-0">
      <PrintBar back={{ href: `/purchase-orders/${p.id}`, label: "Back to the order" }} name={`Purchase-order-${p.number}`}
                whatsapp={{ phone: p.vendor.phone, text: `Hello ${p.vendor.contact_person || p.vendor.name}, please find purchase order ${p.number} from ${branch.data.name}. Total ${money(p.total)}. Please confirm.` }}>
        {p.status === "draft" && <p className="text-error">Draft: not sent yet.</p>}
      </PrintBar>
      <Letterhead branch={branch.data} title="PURCHASE ORDER" right={<><p>No. <b>{p.number}</b></p><p>Date {day(p.sent_at ?? p.created_at)}</p>{p.expected_on && <p>Needed by {day(p.expected_on)}</p>}</>} />
      <section className="mb-4">
        <p className="font-bold">To</p>
        <p>{p.vendor.name}</p>
        {p.vendor.contact_person && <p>{p.vendor.contact_person}</p>}
        {p.vendor.phone && <p>{phone(p.vendor.phone)}</p>}
        {p.vendor.address && <p className="text-muted">{p.vendor.address}</p>}
      </section>
      <Grid head={["#", "Item", "Code", "Qty", "Cost each", "Amount"]} right={[3, 4, 5]}
            rows={p.lines.map((l, i) => [i + 1, l.name, l.codes[0] ?? l.number, `${qty(l.qty)} ${l.unit}`, money(l.unit_cost), money(l.amount)])} />
      <p className="mb-6 text-right text-sm font-bold">Total {money(p.total)}</p>
      {p.notes && <p className="mb-6 whitespace-pre-line"><b>Notes.</b> {p.notes}</p>}
      <p className="mb-10 text-muted">Please quote this order number on your delivery note and invoice. Goods are checked on arrival and may be returned if they differ from this order.</p>
      <div className="grid grid-cols-2 gap-10">
        <div><div className="h-10 border-b border-ink" /><p>Authorised by, {branch.data.name}</p></div>
        <div><div className="h-10 border-b border-ink" /><p>Vendor acknowledgement</p></div>
      </div>
    </div>
  );
}
