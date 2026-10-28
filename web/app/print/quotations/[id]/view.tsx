"use client";

import Image from "next/image";
import { useParams } from "next/navigation";
import { Suspense } from "react";
import { FUELS } from "@/components/cars";
import { PrintBar } from "@/components/print";
import { useApi } from "@/lib/api";
import { day, money, phone, qty } from "@/lib/format";

type Any = Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any -- mirrors the API's JSON

export default function PrintQuotation() {
  return <Suspense fallback={<p className="p-8">Loading</p>}><Quote /></Suspense>;
}

function Quote() {
  const { id } = useParams<{ id: string }>();
  const quote = useApi<Any>(`/api/quotations/${id}`);
  const branch = useApi<Any>("/api/branch");
  if (quote.error) return <p className="p-8 text-error">{quote.error}</p>;
  if (!quote.data || !branch.data) return <p className="p-8">Loading</p>;
  const q = quote.data, b = branch.data, t = q.totals, { car, owner, buyer } = q.people;
  const billTo = buyer ?? owner;
  const lines = q.lines.filter((l: Any) => !l.declined);

  return (
    <div className="mx-auto max-w-[210mm] px-4 py-4 sm:px-[12mm] sm:py-[10mm] text-[12px] leading-snug print:p-0">
      <PrintBar back={{ href: `/quotations/${q.id}`, label: "Back to the quotation" }} name={`Quotation-${q.number}${q.revision > 1 ? `-rev${q.revision}` : ""}`}
                whatsapp={{ phone: billTo.phone, text: `Hello ${billTo.name}, here is quotation ${q.number} from ${b.name}. Total ${money(t.total)}, valid until ${day(q.valid_until)}. Please reply to approve.` }}>
        {q.status === "draft" && <p className="text-error">Draft: prices may still change.</p>}
      </PrintBar>

      <header className="mb-4 flex items-start justify-between gap-4 border-b-2 border-ink pb-3">
        <div className="flex items-center gap-3">
          <Image src="/logo.png" alt="" width={56} height={56} />
          <div>
            <p className="text-xl font-bold tracking-tight">{b.name.toUpperCase()}</p>
            <p className="text-muted">{[b.address, b.phone && phone(b.phone)].filter(Boolean).join(", ")}</p>
          </div>
        </div>
        <div className="text-right">
          <p className="text-lg font-bold">QUOTATION</p>
          <p>No. <b>{q.number}</b>{q.revision > 1 ? ` (revision ${q.revision})` : ""}</p>
          <p>Date {day(q.sent_at ?? q.created_at)}</p>
          <p>Valid until {day(q.valid_until)}</p>
        </div>
      </header>

      <section className="mb-4 grid grid-cols-2 gap-6">
        <div>
          <p className="font-bold">For</p>
          <p>{billTo.name}</p>
          <p>{phone(billTo.phone)}</p>
          <p className="text-muted">{billTo.number}</p>
        </div>
        <div>
          <p className="font-bold">Vehicle</p>
          <p>{[car.year, car.make, car.model].filter(Boolean).join(" ")}{car.fuel ? `, ${FUELS[car.fuel]}` : ""}</p>
          <p>Registration {car.plate || "None"}</p>
          {car.vin && <p>VIN / chassis {car.vin}</p>}
          <p className="text-muted">Visit {q.visit.number}</p>
        </div>
      </section>

      <table className="mb-3 w-full border-collapse">
        <thead>
          <tr className="[print-color-adjust:exact]">
            {["#", "Description", "Type", "Qty", "Rate", "Amount"].map((h, i) => (
              <th key={h} className={`border border-rule bg-paper-2 px-2 py-1 ${i >= 3 ? "text-right" : "text-left"}`}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {lines.map((l: Any, i: number) => (
            <tr key={l.id}>
              <td className="border border-rule px-2 py-1">{i + 1}</td>
              <td className="border border-rule px-2 py-1">{l.description}<span className="block text-muted">{l.labour_code?.code ?? l.item?.number}</span></td>
              <td className="border border-rule px-2 py-1">{l.kind === "labour" ? "Labour" : "Part"}</td>
              <td className="num border border-rule px-2 py-1 text-right">{qty(l.qty)}</td>
              <td className="num border border-rule px-2 py-1 text-right">{money(l.unit_price)}</td>
              <td className="num border border-rule px-2 py-1 text-right">{money(l.amount)}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <div className="mb-6 flex justify-end">
        <table className="w-72 border-collapse">
          <tbody>
            {[["Labour", t.labour], ["Parts", t.parts], ...(Number(t.discount) > 0 ? [["Discount", `-${t.discount}`]] : []),
              ...(q.include_tax ? [[`Sales tax ${Number(q.tax_rate)}%`, t.tax]] : [])].map(([l, v]) => (
              <tr key={l}><td className="px-2 py-0.5">{l}</td><td className="num px-2 py-0.5 text-right">{money(v)}</td></tr>
            ))}
            <tr className="border-t-2 border-ink font-bold"><td className="px-2 py-1">Total</td><td className="num px-2 py-1 text-right">{money(t.total)}</td></tr>
            {Number(t.advance) > 0 && <>
              <tr><td className="px-2 py-0.5">Advance received</td><td className="num px-2 py-0.5 text-right">{money(`-${t.advance}`)}</td></tr>
              <tr className="font-bold"><td className="px-2 py-0.5">Balance</td><td className="num px-2 py-0.5 text-right">{money(t.balance)}</td></tr>
            </>}
          </tbody>
        </table>
      </div>

      {q.notes && <p className="mb-4 whitespace-pre-line"><b>Notes.</b> {q.notes}</p>}
      <p className="mb-10 text-muted">
        Prices are valid until {day(q.valid_until)}. Work starts once the quotation is approved. The terms and conditions on the next page apply.
      </p>
      <div className="grid grid-cols-2 gap-10">
        <div><div className="h-12 border-b border-ink" /><p>Customer approval and date</p></div>
        <div><div className="h-12 border-b border-ink" /><p>For {b.name}</p></div>
      </div>

      {/* The terms get their own page, as on the legacy quotation, so the quotation itself stays one clean sheet. */}
      <section className="mt-8 break-before-page print:mt-0">
        <h2 className="mb-3 border-b-2 border-ink pb-1 text-base font-bold">TERMS &amp; CONDITIONS</h2>
        <ol className="list-decimal space-y-1.5 pl-5 text-[11px] leading-snug">
          {(b.terms as string[]).map((t) => <li key={t} className="break-inside-avoid pl-1">{t}</li>)}
        </ol>
        <p className="mt-6">I have read and accept the terms and conditions above.</p>
        <div className="mt-8 grid grid-cols-2 gap-10">
          <div><div className="h-10 border-b border-ink" /><p>Customer signature, name and date</p></div>
          <div />
        </div>
      </section>
    </div>
  );
}
