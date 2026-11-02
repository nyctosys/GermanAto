"use client";

import { useParams } from "next/navigation";
import { Suspense } from "react";
import { ACCOUNT } from "@/components/payments";
import { Grid, Letterhead, PrintBar, Section } from "@/components/print";
import { STAGE } from "@/components/repairs";
import { useApi } from "@/lib/api";
import { day, money, phone, qty, when } from "@/lib/format";

type Any = Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any -- mirrors the API's JSON

const KIND: Record<string, string> = { workshop: "Workshop inspection", delivery: "Delivery inspection", pre_purchase: "Pre-purchase inspection" };
const QSTATUS: Record<string, string> = { draft: "Draft", sent: "Sent", approved: "Approved", rejected: "Rejected", expired: "Expired", revised: "Replaced by a revision", converted: "Approved, repair order made" };
const ACTIVITY: Record<string, string> = { parts: "Parts", line: "Work list", note: "Note", finding: "Finding", customer_update: "Customer update" };
const NOISE = new Set(["id", "branch_id", "created_at", "updated_at", "created_by", "updated_by", "version"]);
const METHOD: Record<string, string> = { in_person: "in person", whatsapp: "by WhatsApp reply", phone: "by phone" };

export default function PrintVisit() {
  return <Suspense fallback={<p className="p-8">Loading</p>}><Dossier /></Suspense>;
}

/** The whole visit on paper, entry to exit, with every proof (spec §2, R1). */
function Dossier() {
  const { id } = useParams<{ id: string }>();
  const d = useApi<Any>(`/api/visits/${id}/dossier`);
  const branch = useApi<{ name: string; address: string; phone: string }>("/api/branch");
  if (d.error) return <p className="p-8 text-error">{d.error}</p>;
  if (!d.data || !branch.data) return <p className="p-8">Loading</p>;
  const { visit: v, job_card: jc, quotations, repair_order: ro, invoices, payments, gate_pass: g, audit } = d.data;
  const urlsOf = (urls?: string[], url?: string | null) => urls?.length ? urls : url ? [url] : [];
  const proofs = [
    ...payments.flatMap((p: Any) => urlsOf(p.proof_urls, p.proof_url).map((url: string, i: number, all: string[]) => (
      { label: `${p.number}, ${money(p.amount)}${all.length > 1 ? ` (${i + 1})` : ""}`, url }))),
    ...quotations.flatMap((q: Any) => urlsOf(q.approval?.proof_urls, q.approval?.proof_url).map((url: string, i: number, all: string[]) => (
      { label: `Approval of ${q.number} rev ${q.revision}${all.length > 1 ? ` (${i + 1})` : ""}`, url }))),
  ];

  return (
    <div className="mx-auto max-w-[210mm] px-4 py-4 sm:px-[12mm] sm:py-[10mm] text-[11px] leading-snug print:p-0">
      <PrintBar back={{ href: `/visits/${v.id}`, label: "Back to the visit" }} name={`Visit-record-${v.number}`}><p className="text-muted">Internal record: includes notes the customer doesn&apos;t see.</p></PrintBar>
      <Letterhead branch={branch.data} title="VISIT RECORD" right={<><p>Visit <b>{v.number}</b></p><p>In {when(v.checked_in_at)}</p>{g && <p>Out {when(g.at)}</p>}</>} />

      <section className="mb-4 grid grid-cols-2 gap-6">
        <div><p className="font-bold">Customer</p><p>{v.customer.name}, {phone(v.customer.phone)}</p><p className="text-muted">{v.customer.number}</p>
          {v.buyer && <p>Buyer: {v.buyer.name}, {phone(v.buyer.phone)}</p>}</div>
        <div><p className="font-bold">Vehicle</p><p>{v.car.plate || "No plate"}, {[v.car.year, v.car.make, v.car.model].filter(Boolean).join(" ")}</p></div>
      </section>

      <Section title="1. Check-in">
        <Grid head={["Checked in", "Odometer", "Fuel", "Complaint"]} rows={[[when(v.checked_in_at), v.odometer_in != null ? `${v.odometer_in.toLocaleString("en-PK")} km` : "", v.fuel_eighths != null ? `${v.fuel_eighths}/8` : "", v.complaint]]} />
        <Grid head={["Existing damage", "Valuables left in the car"]} rows={[[v.condition_notes || "None", v.items_left || "None"]]} />
        {v.photos.length > 0 && (
          <div className="mb-2 grid grid-cols-6 gap-1">
            {/* eslint-disable-next-line @next/next/no-img-element -- authenticated API files */}
            {v.photos.map((p: Any) => <img key={p.id} src={p.url} alt={p.name} className="aspect-square w-full border border-rule object-cover" />)}
          </div>
        )}
        {/* eslint-disable-next-line @next/next/no-img-element -- authenticated API files */}
        {v.signature && <p>Customer&apos;s signature at check-in: <img src={v.signature.url} alt="" className="inline h-10 align-middle" /></p>}
      </Section>

      <Section title="2. Inspections">
        <Grid head={["Report", "Kind", "Status"]} rows={v.inspections.map((i: Any) => [i.number, KIND[i.kind], i.status === "signed" ? `Signed ${when(i.signed_at)}` : "Draft"])} />
        <p className="text-muted">Each signed report prints in full from its own page.</p>
      </Section>

      <Section title="3. Job card">
        {jc ? <Grid head={["Work or part", "Code", "Qty", "Note"]} right={[2]}
                    rows={jc.lines.map((l: Any) => [l.labour_code?.name ?? l.item?.name, l.labour_code?.code ?? l.item?.number, qty(l.qty), l.note])} />
          : <p className="text-muted">No job card.</p>}
      </Section>

      <Section title="4. Quotations">
        {quotations.length ? quotations.map((q: Any) => (
          <div key={q.id} className="mb-3 break-inside-avoid">
            <p className="font-bold">{q.number}, revision {q.revision}: {QSTATUS[q.status]}{q.sent_at ? `, sent ${when(q.sent_at)}` : ""}</p>
            <Grid head={["Line", "Qty", "Price", "Amount"]} right={[1, 2, 3]}
                  rows={q.lines.map((l: Any) => [`${l.description}${l.declined ? " (declined)" : ""}`, qty(l.qty), money(l.unit_price), money(l.amount)])} />
            <p>Total {money(q.totals.total)}{q.include_tax ? `, including ${Number(q.tax_rate)}% tax` : ""}.
              {q.approval && (() => {
                const n = urlsOf(q.approval.proof_urls, q.approval.proof_url).length;
                const proof = n ? (n > 1 ? `${n} proofs attached.` : "Proof attached.") : `No proof: ${q.approval.no_proof_reason}.`;
                return ` Approved ${METHOD[q.approval.method]} ${when(q.approval.at)}${q.approval.by ? ` (recorded by ${q.approval.by})` : ""}. ${proof}`;
              })()}
              {q.rejected_reason && ` Rejected: ${q.rejected_reason}.`}</p>
          </div>
        )) : <p className="text-muted">No quotation.</p>}
      </Section>

      <Section title="5. Repair order">
        {ro ? (
          <>
            <p className="mb-1 font-bold">{ro.number}: {STAGE[ro.status as keyof typeof STAGE]}</p>
            <Grid head={["Line", "Qty", "Issued", "Technician", "Result"]} right={[1, 2]}
                  rows={ro.lines.map((l: Any) => [`${l.description}${l.in_quote ? "" : " (added after the quotation)"}`, qty(l.qty), l.kind === "part" ? qty(l.issued_qty) : "",
                                                  l.technician ?? "", l.state === "done" ? "Done" : l.state === "not_done" ? "Not done" : "To do"])} />
            <p className="mb-1 font-bold">Activity</p>
            <Grid head={["When", "Who", "What", "Customer sees"]}
                  rows={[...ro.activity].reverse().map((a: Any) => [when(a.at), a.by ?? "",
                    `${a.kind === "status" ? (a.from_status ? `${STAGE[a.from_status as keyof typeof STAGE]} to ${STAGE[a.to_status as keyof typeof STAGE]}` : "Opened") : ACTIVITY[a.kind] ?? a.kind}${a.body ? `: ${a.body}` : ""}${a.photos.length ? ` (${a.photos.length} photo${a.photos.length > 1 ? "s" : ""})` : ""}`,
                    a.customer_visible ? "Yes" : ""])} />
          </>
        ) : <p className="text-muted">No repair order.</p>}
      </Section>

      <Section title="6. Invoice">
        {invoices.length ? invoices.map((inv: Any) => (
          <div key={inv.id} className="mb-2 break-inside-avoid">
            <p className="font-bold">{inv.number}: {inv.status === "void" ? "Voided draft" : inv.status === "draft" ? "Draft" : `Issued ${when(inv.issued_at)}${inv.issued_by ? ` by ${inv.issued_by}` : ""}`}</p>
            {inv.status !== "void" && <>
              <Grid head={["Line", "Qty", "Price", "Amount"]} right={[1, 2, 3]} rows={inv.lines.map((l: Any) => [l.description, qty(l.qty), money(l.unit_price), money(l.amount)])} />
              <p>Total {money(inv.totals.total)}, paid {money(inv.totals.paid)}, balance {money(inv.totals.balance)}.
                {inv.credit_release && ` Released on credit by ${inv.credit_release.by}: ${inv.credit_release.reason}.`}</p>
            </>}
          </div>
        )) : <p className="text-muted">No invoice.</p>}
      </Section>

      <Section title="7. Money received">
        <Grid head={["Receipt", "Date", "Kind", "Method", "Reference", "Proof", "Amount"]} right={[6]}
              rows={payments.map((p: Any) => {
                const n = urlsOf(p.proof_urls, p.proof_url).length;
                return [p.number, day(p.received_at), p.kind === "advance" ? "Advance" : "Payment", ACCOUNT[p.account], p.reference,
                        n ? (n > 1 ? `${n} attached` : "Attached") : `None: ${p.no_proof_reason}`, money(p.amount)];
              })} />
      </Section>

      <Section title="8. Gate pass">
        {g ? <Grid head={["Released", "By", "Handed to", "Odometer out", "Note"]}
                   rows={[[when(g.at), g.by ?? "", g.handed_to || v.customer.name, g.odometer_out != null ? `${g.odometer_out.toLocaleString("en-PK")} km` : "", [g.note, g.credit && `On credit (${g.credit.by}): ${g.credit.reason}`].filter(Boolean).join(". ")]]} />
          : <p className="text-muted">The car hasn&apos;t left yet.</p>}
      </Section>

      <Section title="9. Audit trail">
        <Grid head={["When", "Who", "Action", "Record", "Fields"]}
              rows={audit.map((a: Any) => [when(a.at), a.by ?? "System", a.action, a.entity_type.replace(/_/g, " "),
                a.action === "create" ? "" : a.fields.filter((f: string) => !NOISE.has(f)).join(", ").replace(/_/g, " ")])} />
      </Section>

      {proofs.length > 0 && (
        <Section title="Proofs">
          <div className="grid grid-cols-3 gap-2">
            {proofs.map((p) => (
              <figure key={p.url} className="break-inside-avoid border border-rule p-1">
                {/* eslint-disable-next-line @next/next/no-img-element -- authenticated API files */}
                <img src={p.url} alt="" className="max-h-48 w-full object-contain" />
                <figcaption className="mt-1">{p.label}</figcaption>
              </figure>
            ))}
          </div>
        </Section>
      )}
    </div>
  );
}
