"use client";

import { useParams, useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { Letterhead, PrintBar } from "@/components/print";
import { useApi } from "@/lib/api";
import { phone, when } from "@/lib/format";

type Any = Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any -- mirrors the API's JSON

export default function PrintGatePass() {
  return <Suspense fallback={<p className="p-8">Loading</p>}><Doc /></Suspense>;
}

function Doc() {
  const { id } = useParams<{ id: string }>();
  const search = useSearchParams();
  const fromGate = search.get("from") === "gate";
  const d = useApi<Any>(`/api/visits/${id}/dossier`);
  const branch = useApi<{ name: string; address: string; phone: string }>("/api/branch");

  if (d.error) return <p className="p-8 text-error">{d.error}</p>;
  if (!d.data || !branch.data) return <p className="p-8">Loading</p>;
  const v = d.data.visit, g = d.data.gate_pass, inv = d.data.invoices.find((i: Any) => i.status === "issued");
  if (!g) return <p className="p-8">This car hasn&apos;t been released yet.</p>;
  return (
    <div className="mx-auto max-w-[210mm] px-4 py-4 sm:px-[10mm] sm:py-[8mm] text-[12px] leading-snug print:p-0">
      <PrintBar
        back={fromGate ? { href: "/gate", label: "Back to cars ready to leave" } : { href: `/visits/${v.id}`, label: "Back to the visit" }}
        name={`Gate-pass-${v.number}`}
      />
      <Letterhead branch={branch.data} title="GATE PASS" right={<><p>Visit <b>{v.number}</b></p><p>{when(g.at)}</p></>} />
      <table className="mb-6 w-full border-collapse"><tbody>
        {[["Vehicle", `${v.car.plate || "No plate"}, ${[v.car.year, v.car.make, v.car.model].filter(Boolean).join(" ")}`],
          ["Owner", `${v.customer.name}, ${phone(v.customer.phone)}`], ["Handed over to", g.handed_to || v.customer.name],
          ["Odometer in / out", `${v.odometer_in?.toLocaleString("en-PK") ?? "-"} / ${g.odometer_out?.toLocaleString("en-PK") ?? "-"} km`],
          ["Invoice", inv ? `${inv.number}, ${inv.pay_status === "paid" ? "paid" : "balance outstanding"}` : "No invoice"],
          ...(g.credit ? [["Released on credit", `${g.credit.by}: ${g.credit.reason}`]] : []), ["Released by", g.by ?? ""]].map(([l, val]) => (
          <tr key={l}><td className="w-40 border border-rule px-2 py-1.5 font-bold">{l}</td><td className="border border-rule px-2 py-1.5">{val}</td></tr>
        ))}
      </tbody></table>
      <div className="grid grid-cols-2 gap-10">
        <div><div className="h-10 border-b border-ink" /><p>Customer: car received in order</p></div>
        <div><div className="h-10 border-b border-ink" /><p>Security / gate</p></div>
      </div>
    </div>
  );
}
