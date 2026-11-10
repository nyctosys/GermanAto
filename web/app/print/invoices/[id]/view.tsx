"use client";

import { useParams } from "next/navigation";
import { Suspense } from "react";
import { type Invoice } from "@/components/billing";
import { ACCOUNT } from "@/components/payments";
import { Grid, Letterhead, PrintBar } from "@/components/print";
import { useApi } from "@/lib/api";
import { day, money, phone, qty, when } from "@/lib/format";

type Branch = { name: string; address: string; phone: string; ntn: string };

export default function PrintInvoice() {
  return <Suspense fallback={<p className="p-8">Loading</p>}><Doc /></Suspense>;
}

function Doc() {
  const { id } = useParams<{ id: string }>();
  const inv = useApi<Invoice>(`/api/invoices/${id}`);
  const branch = useApi<Branch>("/api/branch");
  if (inv.error) return <p className="p-8 text-error">{inv.error}</p>;
  if (!inv.data || !branch.data) return <p className="p-8">Loading</p>;
  return <A4 inv={inv.data} b={branch.data} />;
}

const billTo = (inv: Invoice) => inv.customer ? { name: inv.customer.name, phone: inv.customer.phone, number: inv.customer.number }
  : { name: inv.walk_in_name || "Walk-in customer", phone: inv.walk_in_phone, number: "" };

function A4({ inv, b }: { inv: Invoice; b: Branch }) {
  const t = inv.totals, who = billTo(inv);
  const title = "INVOICE";
  return (
    <div className="mx-auto max-w-[210mm] px-4 py-4 sm:px-[12mm] sm:py-[10mm] text-[12px] leading-snug print:p-0">
      <PrintBar back={{ href: `/invoices/${inv.id}`, label: "Back to the invoice" }} name={`Invoice-${inv.number}`}
                whatsapp={{ phone: who.phone, text: `Hello ${who.name}, here is invoice ${inv.number} from ${b.name}. Total ${money(t.total)}${Number(t.balance) > 0 ? `, balance ${money(t.balance)}` : ", paid in full"}. Thank you.` }}>
        {inv.status !== "issued" && <p className="text-error">Draft: not issued yet.</p>}
      </PrintBar>
      <Letterhead branch={{ ...b, ntn: inv.workshop_ntn || b.ntn }} title={title} right={<><p>No. <b>{inv.number}</b></p>{inv.kind === "counter_sale" && <p>Counter sale</p>}<p>Date {day(inv.issued_at ?? inv.created_at)}</p>{inv.visit && <p>Visit {inv.visit.number}</p>}</>} />
      <section className="mb-4 grid grid-cols-2 gap-6">
        <div><p className="font-bold">Bill to</p><p>{who.name}</p>{who.phone && <p>{phone(who.phone)}</p>}{who.number && <p className="text-muted">{who.number}</p>}</div>
        {inv.car && <div><p className="font-bold">Vehicle</p><p>{[inv.car.year, inv.car.make, inv.car.model].filter(Boolean).join(" ")}</p><p>Registration {inv.car.plate || "None"}</p>{inv.car.vin && <p>VIN / chassis {inv.car.vin}</p>}</div>}
      </section>
      <Grid head={["#", "Description", "Type", "Qty", "Rate", "Amount"]} right={[3, 4, 5]}
            rows={inv.lines.map((l, i) => [i + 1, <>{l.description}<span className="block text-muted">{l.labour_code?.code ?? l.item?.number}{l.in_quote ? "" : ", added after the quotation"}</span></>,
                                           l.kind === "labour" ? "Labour" : "Part", qty(l.qty), money(l.unit_price), money(l.amount)])} />
      <div className="mb-4 flex justify-end">
        <table className="w-72 border-collapse"><tbody>
          {[["Labour", t.labour], ["Parts", t.parts], ...(Number(t.discount) > 0 ? [["Discount", `-${t.discount}`]] : []),
            ...(inv.include_tax ? [[`Sales tax ${Number(inv.tax_rate)}%`, t.tax]] : [])].map(([l, v]) => (
            <tr key={l}><td className="px-2 py-0.5">{l}</td><td className="num px-2 py-0.5 text-right">{money(v)}</td></tr>
          ))}
          <tr className="border-t-2 border-ink font-bold"><td className="px-2 py-1">Total</td><td className="num px-2 py-1 text-right">{money(t.total)}</td></tr>
          <tr><td className="px-2 py-0.5">Paid</td><td className="num px-2 py-0.5 text-right">{money(t.paid)}</td></tr>
          <tr className="font-bold"><td className="px-2 py-0.5">Balance</td><td className="num px-2 py-0.5 text-right">{money(t.balance)}</td></tr>
        </tbody></table>
      </div>
      {inv.payments.length > 0 && <Grid head={["Payment", "Date", "Method", "Reference", "Amount"]} right={[4]}
            rows={inv.payments.map((p) => [`${p.number}${p.kind === "advance" ? " (advance)" : ""}`, when(p.received_at), ACCOUNT[p.account], p.reference, money(p.amount)])} />}
      {inv.credit_release && <p className="mb-3"><b>Released on credit</b> by {inv.credit_release.by}: {inv.credit_release.reason}</p>}
      {inv.notes && <p className="mb-4 whitespace-pre-line">{inv.notes}</p>}
      <div className="mt-12 grid grid-cols-2 gap-10">
        <div><div className="h-10 border-b border-ink" /><p>Received by (customer)</p></div>
        <div><div className="h-10 border-b border-ink" /><p>For {b.name}{inv.issued_by ? `, ${inv.issued_by}` : ""}</p></div>
      </div>
    </div>
  );
}
