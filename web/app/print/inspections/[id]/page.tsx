"use client";

import Image from "next/image";
import { useParams } from "next/navigation";
import { Suspense, type ReactNode } from "react";
import { useApi } from "@/lib/api";
import { day, money, phone, when } from "@/lib/format";

type Any = Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any -- mirrors the API's JSON

const CODES: Record<string, string> = { good: "G", average: "A", attention: "NA", not_checked: "NC" };
const KIND: Record<string, string> = { workshop: "Workshop inspection", delivery: "Delivery inspection", pre_purchase: "Pre-purchase inspection" };

export default function PrintInspection() {
  return <Suspense fallback={<p className="p-8">Loading</p>}><Report /></Suspense>;
}

function Report() {
  const { id } = useParams<{ id: string }>();
  const ins = useApi<Any>(`/api/inspections/${id}`);
  const tpl = useApi<Any>("/api/inspection-template");
  const branch = useApi<Any>("/api/branch");
  if (ins.error || tpl.error) return <p className="p-8 text-error">{ins.error ?? tpl.error}</p>;
  if (!ins.data || !tpl.data || !branch.data) return <p className="p-8">Loading</p>;
  const i = ins.data, t = tpl.data, d = i.data, b = branch.data;
  const rating = (k: string) => d.items[k]?.rating ?? "not_checked";
  const notes = Object.entries(d.items as Any).filter(([, a]) => a.note);
  const labelOf = Object.fromEntries(t.sections.flatMap((s: Any) => s.items.map((it: Any) => [it.key, it.label])));

  return (
    <div className="mx-auto max-w-[210mm] px-[10mm] py-[8mm] text-[11px] leading-snug print:p-0">
      <div className="no-print mb-4 flex gap-2">
        <button onClick={() => window.print()} className="min-h-11 rounded-control bg-accent px-4 font-medium text-accent-ink">Print or save as PDF</button>
        {i.status !== "signed" && <p className="self-center text-error">Draft: this report is not signed yet.</p>}
      </div>

      <header className="mb-3 flex items-start justify-between gap-4 border-b-2 border-ink pb-2">
        <div className="flex items-center gap-3">
          <Image src="/logo.png" alt="" width={56} height={56} />
          <div>
            <p className="text-xl font-bold tracking-tight">{b.name.toUpperCase()}</p>
            <p className="text-muted">{[b.address, b.phone && phone(b.phone)].filter(Boolean).join(", ")}</p>
          </div>
        </div>
        <div className="text-right">
          <p className="font-bold">VEHICLE INSPECTION REPORT</p>
          <p>{KIND[i.kind]}</p>
          <p>Report no. <b>{i.number}</b></p>
          <p>Date {day(i.signed_at ?? i.created_at)}</p>
        </div>
      </header>

      <Band n={1} title="Vehicle and customer details" />
      <table className="mb-2 w-full border-collapse">
        <tbody>
          <Row cells={[["Make", i.car.make], ["Model", i.car.model], ["Year", d.details.year], ["Mileage", d.assessment.odometer_km != null ? `${d.assessment.odometer_km.toLocaleString("en-PK")} km` : ""]]} />
          <Row cells={[["VIN / chassis", i.car.vin || i.car.chassis_no], ["Registration", i.car.plate], ["Engine no.", d.details.engine_no], ["Colour", i.car.color]]} />
          <Row cells={i.kind === "pre_purchase"
            ? [["Buyer", d.details.buyer_name], ["Buyer phone", d.details.buyer_phone], ["Seller", d.details.seller_name], ["Fuel", d.details.fuel]]
            : [["Customer", i.customer.name], ["Phone", phone(i.customer.phone)], ["Visit", i.visit.number], ["Fuel", d.details.fuel]]} />
        </tbody>
      </table>
      <p className="mb-2 rounded border border-rule bg-paper-2 px-2 py-1"><b>Rating:</b> G = Good, A = Average, <b>NA = Needs attention</b>, NC = Not checked</p>

      <Rated n={2} section={t.sections[0]} rating={rating} />

      <Band n={3} title="Paint / accident check and 4. tyres / wheels" />
      <div className="mb-2 grid grid-cols-3 gap-3 border border-rule p-2">
        <div>
          <p className="font-bold">Paint meter / panel findings</p>
          {Object.entries(d.paint.findings as Any).map(([p, f]) => <p key={p}>{p}: {String(f)}</p>)}
          {d.paint.notes && <p>{d.paint.notes}</p>}
        </div>
        <div>
          <p className="font-bold">Accident / structural findings</p>
          <p>{d.paint.accident === "none" ? "No obvious structural repair" : d.paint.accident === "repair_signs" ? "Repair signs found" : "Not checked"}</p>
          {d.paint.structural_notes && <p>{d.paint.structural_notes}</p>}
        </div>
        <div>
          <p className="font-bold">Tyres and wheels</p>
          {(["fl", "fr", "rl", "rr"] as const).map((k) => <p key={k}>{k.toUpperCase()}: {d.tyres[k].mm ?? "__"} mm / {d.tyres[k].pct ?? "__"}%</p>)}
          <p>Spare: {d.tyres.spare || "__"}. Wheel damage: {d.tyres.wheel_damage == null ? "__" : d.tyres.wheel_damage ? "Yes" : "No"}</p>
        </div>
      </div>

      {t.sections.slice(1, 4).map((s: Any, idx: number) => <Rated key={s.key} n={[5, 6, 7][idx]} section={s} rating={rating} />)}

      <div className="break-before-page" />
      <Band n={8} title="Diagnostic scan / electronic systems" />
      <table className="mb-1 w-full border-collapse">
        <tbody>
          <Row cells={[["Tool", d.scan.tool], ["Scan date", d.scan.scanned_on ? day(d.scan.scanned_on) : ""], ["12V battery", `${d.scan.battery_rest_v ?? "__"} V rest / ${d.scan.battery_running_v ?? "__"} V running`]]} />
          <Row cells={[["Warning lights", d.scan.warning_lights.length ? d.scan.warning_lights.join(", ").replaceAll("_", " ") + (d.scan.other_light ? ` (${d.scan.other_light})` : "") : "None"],
                       ["DTCs stored", d.scan.dtcs.length ? "Yes, see below" : "None"], ["Modules not communicating", d.scan.modules_not_communicating]]} />
        </tbody>
      </table>
      <Table head={["Module", "DTC / fault code", "Description / status", "Priority"]} rows={d.scan.dtcs.map((x: Any) => [x.module, x.code, x.description, x.priority])} />

      {(d.details.fuel === "hybrid" || d.details.fuel === "ev") && (
        <>
          <Band n={9} title="Hybrid / EV checks" />
          <table className="mb-2 w-full border-collapse"><tbody>
            <Row cells={[["SOC", `${d.ev.soc_pct ?? "__"} %`], ["SOH / capacity", `${d.ev.soh_pct ?? "__"} % / ${d.ev.capacity_kwh ?? "__"} kWh`], ["Pack voltage", `${d.ev.pack_voltage ?? "__"} V`], ["Cell imbalance", `${d.ev.cell_imbalance_mv ?? "__"} mV`]]} />
            <Row cells={[["Isolation", `${d.ev.isolation_mohm ?? "__"} MΩ`], ["Charging AC", d.ev.charging_ac], ["Charging DC", d.ev.charging_dc], ["Cooling", d.ev.cooling]]} />
          </tbody></table>
          {d.ev.notes && <p className="mb-2">{d.ev.notes}</p>}
        </>
      )}

      <Rated n={10} section={t.sections[4]} rating={rating} />

      <Band n={11} title="Repairs / estimated work required" />
      <Table head={["Priority", "Repair / part required", "Remarks", "Estimated cost"]}
             rows={d.repairs.map((r: Any) => [r.priority, r.repair, r.remarks, r.estimated_cost ? money(r.estimated_cost) : ""])} />

      {notes.length > 0 && (
        <>
          <p className="mb-1 font-bold">Inspector notes on checked items</p>
          <ul className="mb-2 list-inside list-disc">{notes.map(([k, a]) => <li key={k}><b>{labelOf[k]}</b> ({CODES[a.rating]}): {a.note}</li>)}</ul>
        </>
      )}

      <Band n={12} title="Overall assessment" />
      <div className="mb-2 grid grid-cols-3 gap-3 border border-rule p-2">
        <p><b>Overall condition</b><br />{t.overall[d.assessment.overall] ?? "Not given"}</p>
        <p><b>Recommendation</b><br />{t.recommendation[d.assessment.recommendation] ?? "Not given"}</p>
        <p><b>Estimated immediate repair budget</b><br />{d.assessment.budget ? money(d.assessment.budget) : "None"}</p>
        <p className="col-span-3"><b>Inspector summary</b><br />{d.assessment.summary || "None"}</p>
      </div>
      <div className="mb-2 grid grid-cols-3 gap-3 border border-rule p-2">
        <Sig label="Inspector" name={i.inspector} url={i.inspector_signature_url} />
        <Sig label={i.kind === "pre_purchase" ? "Buyer acknowledgement" : "Customer acknowledgement"} name={d.customer_ack_name} url={i.customer_signature_url} />
        <p><b>Inspection time</b><br />{i.signed_at ? when(i.signed_at) : "Not signed"}<br /><b>Odometer</b> {d.assessment.odometer_km?.toLocaleString("en-PK") ?? "__"} km</p>
      </div>
      <p className="text-[10px] text-muted"><b>Inspection disclaimer:</b> {t.disclaimer}</p>
      <style>{`@page { size: A4; margin: 10mm; } @media print { body { background: white; } }`}</style>
    </div>
  );
}

function Band({ n, title }: { n: number; title: string }) {
  return <p className="mb-1 mt-2 break-after-avoid bg-ink px-2 py-1 font-bold text-accent-ink [print-color-adjust:exact]">{n}. {title.toUpperCase()}</p>;
}

function Row({ cells }: { cells: [string, ReactNode][] }) {
  return (
    <tr>{cells.map(([l, v]) => <td key={l} className="border border-rule px-2 py-1 align-top"><span className="font-bold">{l}</span> {v || "__________"}</td>)}</tr>
  );
}

function Rated({ n, section, rating }: { n: number; section: Any; rating: (k: string) => string }) {
  return (
    <div className="break-inside-avoid">
      <Band n={n} title={section.title} />
      <div className="mb-2 grid grid-cols-4 border-l border-t border-rule">
        {section.items.map((it: Any) => (
          <div key={it.key} className="flex items-center justify-between gap-2 border-b border-r border-rule px-2 py-1">
            <span>{it.label}</span>
            <span className={`rounded px-1.5 font-bold [print-color-adjust:exact] ${rating(it.key) === "attention" ? "bg-error text-accent-ink" : rating(it.key) === "good" ? "bg-success-soft text-success" : rating(it.key) === "average" ? "bg-warning-soft text-warning" : "text-muted"}`}>{CODES[rating(it.key)]}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function Table({ head, rows }: { head: string[]; rows: ReactNode[][] }) {
  return (
    <table className="mb-2 w-full border-collapse">
      <thead><tr>{head.map((h) => <th key={h} className="border border-rule bg-paper-2 px-2 py-1 text-left [print-color-adjust:exact]">{h}</th>)}</tr></thead>
      <tbody>
        {(rows.length ? rows : [head.map(() => "")]).map((r, i) => <tr key={i}>{r.map((c, j) => <td key={j} className="h-6 border border-rule px-2 py-1">{c}</td>)}</tr>)}
      </tbody>
    </table>
  );
}

function Sig({ label, name, url }: { label: string; name: string | null; url: string | null }) {
  return (
    <div>
      <p className="font-bold">{label}</p>
      {/* eslint-disable-next-line @next/next/no-img-element -- authenticated API files */}
      {url ? <img src={url} alt="" className="h-12" /> : <div className="h-12 border-b border-ink" />}
      <p>Name: {name || "__________"}</p>
    </div>
  );
}
