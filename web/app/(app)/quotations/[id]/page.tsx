"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { Suspense, useEffect, useState, type FormEvent, type ReactNode } from "react";
import { type Uploaded, PhotoCapture } from "@/components/capture";
import { CatalogPicker, lineCode, lineName, linkButton, type Pick, QuoteBadge, type QuoteLine, type QuoteStatus } from "@/components/estimates";
import { Segments } from "@/components/search";
import { RequirePermission } from "@/components/shell";
import { Badge, Button, Card, Checkbox, ErrorState, Field, Input, Notice, Select, SkeletonRows } from "@/components/ui";
import { VehiclePanel } from "@/components/vehicle-panel";
import { api, useApi } from "@/lib/api";
import { day, money, qty, when } from "@/lib/format";
import { advanceSchema, type FieldErrors, linePrice, lineQty, parseForm } from "@/lib/schemas";
import { useSession } from "@/lib/session";

type Payment = { id: string; number: string; status: string; account: string; reference: string; amount: string; received_at: string;
  received_by: string | null; proof_url: string | null; no_proof_reason: string };
type Quotation = {
  id: string; number: string; revision: number; status: QuoteStatus; version: number; include_tax: boolean; tax_rate: string;
  discount: string; valid_until: string; notes: string; sent_at: string | null; created_at: string; job_card_id: string;
  approval: { at: string; by: string | null; method: string; note: string; no_proof_reason: string; proof_url: string | null } | null;
  rejected_reason: string;
  visit: { id: string; number: string; status: string; car_id: string; customer_id: string; buyer_id: string | null };
  lines: QuoteLine[];
  totals: Record<"labour" | "parts" | "subtotal" | "discount" | "tax" | "total" | "advance" | "balance", string>;
  revisions: { id: string; revision: number; status: QuoteStatus }[];
  advances: Payment[];
  repair_order: { id: string; number: string } | null;
};

const METHOD: Record<string, string> = { in_person: "In person", whatsapp: "WhatsApp reply", phone: "Phone call" };
const ACCOUNT: Record<string, string> = { cash: "Cash", bank: "Bank transfer", wallet: "Mobile wallet" };

export default function QuotationPage() {
  return (
    <RequirePermission permission="quotations">
      <Suspense fallback={<Card flush><SkeletonRows rows={8} /></Card>}>
        <Loader />
      </Suspense>
    </RequirePermission>
  );
}

function Loader() {
  const { id } = useParams<{ id: string }>();
  const q = useApi<Quotation>(`/api/quotations/${id}`);
  if (q.error) return <Card flush><ErrorState message={q.error} onRetry={q.reload} /></Card>;
  if (!q.data) return <Card flush><SkeletonRows rows={8} /></Card>;
  return <QuotationView key={`${q.data.id}-${q.data.version}`} q={q.data} reload={q.reload} />;
}

function QuotationView({ q, reload }: { q: Quotation; reload: () => void }) {
  const router = useRouter();
  const { can } = useSession();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [panel, setPanel] = useState<"approve" | "reject" | "advance" | null>(null);
  const open = q.visit.status === "open";
  const draft = q.status === "draft" && open;

  async function act(path: string, json?: object) {
    setBusy(true);
    setError(null);
    try {
      const r = await api<{ id: string }>(`/api/quotations/${q.id}/${path}`, { method: "POST", json });
      if (r.id !== q.id) router.push(`/quotations/${r.id}`);
      else reload();
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  return (
    <>
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1>Quotation {q.number}{q.revision > 1 ? `, revision ${q.revision}` : ""}</h1>
          <p className="text-muted">
            For <Link href={`/visits/${q.visit.id}`} className="underline">{q.visit.number}</Link>, from <Link href={`/job-cards/${q.job_card_id}`} className="underline">the job card</Link>
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <QuoteBadge status={q.status} />
          <Link href={`/print/quotations/${q.id}`} target="_blank" className={linkButton}>Print</Link>
        </div>
      </div>

      {q.revisions.length > 1 && (
        <nav aria-label="Revisions" className="mb-4 flex flex-wrap items-center gap-2 text-sm">
          <span className="text-muted">Revisions</span>
          {q.revisions.map((r) => r.id === q.id
            ? <span key={r.id} className="rounded-control bg-ink px-3 py-1.5 text-surface">{r.revision}</span>
            : <Link key={r.id} href={`/quotations/${r.id}`} className="rounded-control border border-rule-strong bg-surface px-3 py-1.5 hover:bg-paper-2">{r.revision}</Link>)}
        </nav>
      )}

      <div className="grid gap-4 shell:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        <div className="space-y-4">
          {draft ? <DraftEditor q={q} onSaved={reload} onSend={(v) => act("send", { version: v })} busy={busy} />
            : <LinesTable q={q} />}
          {q.status === "approved" && q.approval && (
            <Card title="Approval">
              <dl className="grid gap-4 sm:grid-cols-2">
                <Fact label="Approved">{when(q.approval.at)}{q.approval.by ? ` by ${q.approval.by}` : ""}</Fact>
                <Fact label="How">{METHOD[q.approval.method]}</Fact>
                {q.approval.note && <Fact label="Note" wide>{q.approval.note}</Fact>}
                <Fact label="Proof" wide>
                  {q.approval.proof_url ? <a href={q.approval.proof_url} target="_blank" rel="noreferrer" className="underline">Open the proof</a>
                    : <span>No proof: {q.approval.no_proof_reason}</span>}
                </Fact>
              </dl>
            </Card>
          )}
          {q.status === "rejected" && <Notice tone="warning">Rejected: {q.rejected_reason}</Notice>}

          {panel === "approve" && <ApproveForm q={q} busy={busy} onCancel={() => setPanel(null)} onSubmit={(b) => act("approve", { ...b, version: q.version })} />}
          {panel === "reject" && <RejectForm busy={busy} onCancel={() => setPanel(null)} onSubmit={(reason) => act("reject", { reason, version: q.version })} />}
          {panel === "advance" && <AdvanceForm q={q} onCancel={() => setPanel(null)} onDone={() => { setPanel(null); reload(); }} />}

          <Notice>{error}</Notice>
          {open && !panel && q.status !== "draft" && (
            <div className="flex flex-wrap gap-2">
              {q.status === "sent" && <Button onClick={() => setPanel("approve")}>Record approval</Button>}
              {q.status === "sent" && <Button variant="secondary" onClick={() => setPanel("reject")}>Customer said no</Button>}
              {["sent", "approved", "converted"].includes(q.status) && can("payments-in") && <Button variant="secondary" onClick={() => setPanel("advance")}>Take an advance</Button>}
              {["sent", "approved", "rejected", "expired"].includes(q.status) && (
                <Button variant="ghost" disabled={busy} onClick={() => act("revise")}>Revise</Button>
              )}
            </div>
          )}
          {q.status === "expired" && <Notice tone="warning">This quotation passed its validity date ({day(q.valid_until)}). Revise it to send updated prices.</Notice>}
          {q.status === "approved" && open && can("repair-orders") && !panel && (
            <Button disabled={busy} onClick={async () => {
              setBusy(true);
              setError(null);
              try { router.push(`/repair-orders/${(await api<{ id: string }>(`/api/quotations/${q.id}/repair-order`, { method: "POST" })).id}`); }
              catch (err) { setError((err as Error).message); setBusy(false); }
            }}>Make the repair order</Button>
          )}
          {q.repair_order && <Link href={`/repair-orders/${q.repair_order.id}`} className={`${linkButton} w-fit`}>Open repair order {q.repair_order.number}</Link>}
        </div>

        <div className="space-y-4">
          <Totals q={q} />
          {q.advances.length > 0 && <Advances advances={q.advances} />}
          <VehiclePanel carId={q.visit.car_id} ownerId={q.visit.customer_id} buyerId={q.visit.buyer_id} />
        </div>
      </div>
    </>
  );
}

const Fact = ({ label, wide, children }: { label: string; wide?: boolean; children: ReactNode }) => (
  <div className={wide ? "sm:col-span-2" : ""}><dt className="text-sm text-muted">{label}</dt><dd>{children}</dd></div>
);

function LinesTable({ q }: { q: Quotation }) {
  return (
    <Card title="Work and parts" flush>
      <table className="table-stack w-full">
        <thead><tr className="text-left text-sm text-muted">
          <th className="px-4 py-2 font-normal shell:px-5">Item</th><th className="px-4 py-2 text-right font-normal">Qty</th>
          <th className="px-4 py-2 text-right font-normal">Price</th><th className="px-4 py-2 text-right font-normal shell:pr-5">Amount</th>
        </tr></thead>
        <tbody>
          {q.lines.map((l) => (
            <tr key={l.id} className={`border-t border-rule ${l.declined ? "text-muted" : ""}`}>
              <td className="px-4 py-3 shell:px-5 max-sm:px-0">
                <span className={`block font-medium ${l.declined ? "line-through" : ""}`}>{l.description}</span>
                <span className="flex flex-wrap gap-3 text-sm text-muted"><span>{l.kind === "labour" ? "Labour" : "Part"}</span><span>{lineCode(l)}</span>
                  {l.declined && <Badge>Declined by the customer</Badge>}</span>
              </td>
              <td data-label="Qty" className="num px-4 py-3 text-right max-sm:px-0">{qty(l.qty)}</td>
              <td data-label="Price" className="num px-4 py-3 text-right max-sm:px-0">{money(l.unit_price)}</td>
              <td data-label="Amount" className="num px-4 py-3 text-right shell:pr-5 max-sm:px-0">{money(l.amount)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {q.notes && <p className="whitespace-pre-line border-t border-rule px-4 py-3 text-ink-2 shell:px-5">{q.notes}</p>}
      <p className="border-t border-rule px-4 py-3 text-sm text-muted shell:px-5">
        Valid until {day(q.valid_until)}{q.sent_at ? `. Sent ${when(q.sent_at)}` : ""}
      </p>
    </Card>
  );
}

type Draft = { id: string; kind: "labour" | "part"; labour_code_id: string | null; item_id: string | null; name: string; code: string; qty: string; unit_price: string };

function DraftEditor({ q, onSaved, onSend, busy }: { q: Quotation; onSaved: () => void; onSend: (version: number) => void; busy: boolean }) {
  const [lines, setLines] = useState<Draft[]>(() => q.lines.map((l) => ({
    id: l.id, kind: l.kind, labour_code_id: l.labour_code_id, item_id: l.item_id, name: lineName(l), code: lineCode(l),
    qty: String(Number(l.qty)), unit_price: Number(l.unit_price) ? String(Number(l.unit_price)) : "",
  })));
  const [includeTax, setIncludeTax] = useState(q.include_tax);
  const [discount, setDiscount] = useState(Number(q.discount) ? String(Number(q.discount)) : "");
  const [validUntil, setValidUntil] = useState(q.valid_until);
  const [notes, setNotes] = useState(q.notes);
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [showErrors, setShowErrors] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!dirty) return;
    const block = (e: BeforeUnloadEvent) => e.preventDefault();
    window.addEventListener("beforeunload", block);
    return () => window.removeEventListener("beforeunload", block);
  }, [dirty]);

  const edit = (id: string, patch: Partial<Draft>) => { setLines((ls) => ls.map((l) => (l.id === id ? { ...l, ...patch } : l))); setDirty(true); };
  const add = (p: Pick) => {
    setLines((ls) => [...ls, { id: crypto.randomUUID(), kind: p.kind, labour_code_id: p.kind === "labour" ? p.id : null, item_id: p.kind === "part" ? p.id : null,
      name: p.name, code: p.code, qty: "1", unit_price: p.kind === "part" && Number(p.sale_price) ? String(Number(p.sale_price)) : "" }]);
    setDirty(true);
  };
  const priceBad = (l: Draft) => !linePrice.safeParse(l.unit_price).success;
  const qtyBad = (l: Draft) => !lineQty.safeParse(l.qty).success;
  const preview = lines.reduce((s, l) => s + (Number(l.qty) || 0) * (Number(l.unit_price) || 0), 0);

  /** Saves; when sending, every line must be priced first. */
  async function save(send: boolean) {
    setShowErrors(true);
    if (lines.some(qtyBad) || (send && lines.some(priceBad))) { setError(send ? "Every line needs a price and quantity before sending." : "Fix the quantities marked in red."); return; }
    if (!lines.length) { setError("A quotation needs at least one line."); return; }
    setSaving(true);
    setError(null);
    try {
      const saved = await api<Quotation>(`/api/quotations/${q.id}`, { method: "PUT", json: {
        include_tax: includeTax, discount: discount || "0", valid_until: validUntil, notes, version: q.version,
        lines: lines.map((l) => ({ kind: l.kind, labour_code_id: l.labour_code_id, item_id: l.item_id, qty: l.qty, unit_price: l.unit_price || "0" })),
      } });
      setDirty(false);
      if (send) onSend(saved.version); else onSaved();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <Card title="Work and parts" flush>
        <div className="border-b border-rule p-4 shell:px-5"><CatalogPicker onPick={add} /></div>
        <ul>
          {lines.map((l) => (
            <li key={l.id} className="grid gap-3 border-t border-rule px-4 py-3 first:border-t-0 sm:grid-cols-[minmax(0,1fr)_6rem_9rem_auto] sm:items-end shell:px-5">
              <div className="min-w-0 self-center">
                <p className="font-medium">{l.name}</p>
                <p className="flex gap-3 text-sm text-muted"><span>{l.kind === "labour" ? "Labour" : "Part"}</span><span>{l.code}</span></p>
              </div>
              <Field label="Qty" error={showErrors && qtyBad(l) ? "More than 0" : undefined}>
                <Input type="number" inputMode="decimal" min="0" step="any" value={l.qty} onChange={(e) => edit(l.id, { qty: e.target.value })} />
              </Field>
              <Field label="Price (Rs)" error={showErrors && priceBad(l) ? "Enter the price" : undefined}>
                <Input type="number" inputMode="decimal" min="0" step="any" value={l.unit_price} placeholder={l.kind === "labour" ? "Labour price" : ""}
                       onChange={(e) => edit(l.id, { unit_price: e.target.value })} />
              </Field>
              <Button variant="ghost" onClick={() => { setLines((ls) => ls.filter((x) => x.id !== l.id)); setDirty(true); }}>Remove</Button>
            </li>
          ))}
        </ul>
      </Card>

      <Card title="Terms">
        <div className="grid gap-5 sm:grid-cols-2">
          <Field label="Discount (Rs)"><Input type="number" inputMode="decimal" min="0" step="any" value={discount} onChange={(e) => { setDiscount(e.target.value); setDirty(true); }} /></Field>
          <Field label="Valid until"><Input type="date" value={validUntil} onChange={(e) => { setValidUntil(e.target.value); setDirty(true); }} /></Field>
          <div className="sm:col-span-2">
            <Checkbox checked={includeTax} onChange={(e) => { setIncludeTax(e.target.checked); setDirty(true); }}
                      label={`Add ${Number(q.tax_rate)}% sales tax`} hint="On parts and labour, after the discount." />
          </div>
          <div className="sm:col-span-2">
            <Field label="Notes for the customer (optional)">
              <textarea rows={3} maxLength={3000} value={notes} onChange={(e) => { setNotes(e.target.value); setDirty(true); }}
                        className="w-full rounded-control border border-rule-strong bg-surface px-3 py-2.5 text-base focus-visible:border-accent" />
            </Field>
          </div>
        </div>
      </Card>

      {dirty && <p className="text-sm text-muted">Lines before tax and discount come to {money(preview)}. Save to update the totals.</p>}
      <Notice>{error}</Notice>
      <div className="flex flex-wrap gap-2">
        <Button onClick={() => save(true)} disabled={saving || busy}>{busy ? "Sending" : "Send to the customer"}</Button>
        <Button variant="secondary" onClick={() => save(false)} disabled={saving || !dirty}>{saving ? "Saving" : "Save draft"}</Button>
      </div>
      <p className="text-sm text-muted">Sending locks the prices. WhatsApp delivery comes with the messaging stage; print it for now.</p>
    </>
  );
}

function Totals({ q }: { q: Quotation }) {
  const t = q.totals;
  const row = (label: string, v: string, strong = false) => (
    <div className={`flex justify-between gap-4 py-1.5 ${strong ? "font-medium" : ""}`}><dt>{label}</dt><dd className="num">{money(v)}</dd></div>
  );
  return (
    <Card title="Total">
      <dl>
        {row("Labour", t.labour)}
        {row("Parts", t.parts)}
        {Number(t.discount) > 0 && row("Discount", `-${t.discount}`)}
        {q.include_tax && row(`Sales tax ${Number(q.tax_rate)}%`, t.tax)}
        <div className="mt-1 border-t border-rule pt-1">{row("Total", t.total, true)}</div>
        {Number(t.advance) > 0 && <>{row("Advance received", `-${t.advance}`)}{row("Still to pay", t.balance, true)}</>}
      </dl>
    </Card>
  );
}

function Advances({ advances }: { advances: Payment[] }) {
  return (
    <Card title="Advances" flush>
      <ul>
        {advances.map((p) => (
          <li key={p.id} className="flex items-start justify-between gap-3 border-t border-rule px-4 py-3 first:border-t-0 shell:px-5">
            <span className="min-w-0">
              <span className="block font-medium">{p.number}</span>
              <span className="block text-sm text-muted">{ACCOUNT[p.account]}{p.reference ? `, ref ${p.reference}` : ""}, {when(p.received_at)}</span>
              {p.proof_url ? <a href={p.proof_url} target="_blank" rel="noreferrer" className="text-sm underline">Proof</a>
                : <span className="block text-sm text-muted">No proof: {p.no_proof_reason}</span>}
            </span>
            <span className={`num shrink-0 ${p.status === "voided" ? "text-muted line-through" : ""}`}>{money(p.amount)}</span>
          </li>
        ))}
      </ul>
    </Card>
  );
}

/** Proof is always asked for; with none, the person must say why (owner decision). */
function ProofInput({ proof, setProof, reason, setReason, error }:
  { proof: Uploaded[]; setProof: (v: Uploaded[]) => void; reason: string; setReason: (v: string) => void; error?: string }) {
  return (
    <div className="space-y-3">
      <PhotoCapture value={proof} onChange={(v) => setProof(v.slice(-1))} label="Add proof: photo, screenshot or PDF" accept="image/*,application/pdf" note="Proof" />
      {!proof.length && (
        <Field label="No proof? Say why" hint="For example: approved on a phone call." error={error}>
          <Input value={reason} onChange={(e) => setReason(e.target.value)} maxLength={500} />
        </Field>
      )}
    </div>
  );
}

function ApproveForm({ q, busy, onSubmit, onCancel }:
  { q: Quotation; busy: boolean; onSubmit: (b: object) => void; onCancel: () => void }) {
  const [method, setMethod] = useState("in_person");
  const [declined, setDeclined] = useState<string[]>([]);
  const [proof, setProof] = useState<Uploaded[]>([]);
  const [reason, setReason] = useState("");
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | undefined>();

  function submit(e: FormEvent) {
    e.preventDefault();
    if (!proof.length && reason.trim().length < 5) { setError("Attach proof, or explain why there is none"); return; }
    if (declined.length === q.lines.length) { setError(undefined); return; }
    onSubmit({ method, note, declined_line_ids: declined, proof_id: proof[0]?.id ?? null, no_proof_reason: proof.length ? "" : reason });
  }
  return (
    <Card title="Record the customer's approval">
      <form onSubmit={submit} className="space-y-5">
        <div>
          <p className="mb-1.5 text-sm font-medium text-ink-2">How did they approve?</p>
          <Segments value={method} onChange={setMethod} options={Object.entries(METHOD).map(([value, label]) => ({ value, label }))} />
        </div>
        {q.lines.length > 1 && (
          <fieldset>
            <legend className="mb-1 text-sm font-medium text-ink-2">Lines the customer approved</legend>
            {q.lines.map((l) => (
              <Checkbox key={l.id} checked={!declined.includes(l.id)} label={l.description} hint={money(l.amount)}
                        onChange={(e) => setDeclined((d) => (e.target.checked ? d.filter((x) => x !== l.id) : [...d, l.id]))} />
            ))}
            {declined.length === q.lines.length && <p role="alert" className="text-sm text-error">Nothing is approved. Use “Customer said no” instead.</p>}
          </fieldset>
        )}
        <ProofInput proof={proof} setProof={setProof} reason={reason} setReason={setReason} error={error} />
        <Field label="Note (optional)"><Input value={note} onChange={(e) => setNote(e.target.value)} maxLength={1000} /></Field>
        <div className="flex flex-wrap gap-2">
          <Button type="submit" disabled={busy}>Approve</Button>
          <Button type="button" variant="secondary" onClick={onCancel}>Cancel</Button>
        </div>
      </form>
    </Card>
  );
}

function RejectForm({ busy, onSubmit, onCancel }: { busy: boolean; onSubmit: (reason: string) => void; onCancel: () => void }) {
  const [reason, setReason] = useState("");
  return (
    <Card title="The customer said no">
      <form onSubmit={(e) => { e.preventDefault(); onSubmit(reason); }} className="space-y-4">
        <Field label="Reason" hint="Kept on the quotation; counts in the conversion report."><Input value={reason} onChange={(e) => setReason(e.target.value)} required minLength={3} autoFocus /></Field>
        <div className="flex flex-wrap gap-2">
          <Button type="submit" variant="danger" disabled={busy}>Mark rejected</Button>
          <Button type="button" variant="secondary" onClick={onCancel}>Cancel</Button>
        </div>
      </form>
    </Card>
  );
}

function AdvanceForm({ q, onDone, onCancel }: { q: Quotation; onDone: () => void; onCancel: () => void }) {
  const [account, setAccount] = useState("cash");
  const [proof, setProof] = useState<Uploaded[]>([]);
  const [reason, setReason] = useState("");
  const [errors, setErrors] = useState<FieldErrors>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const { data, errors } = parseForm(advanceSchema, e.currentTarget);
    const more: FieldErrors = {};
    if (!proof.length && reason.trim().length < 5) more.no_proof_reason = "Attach proof, or explain why there is none";
    if (data && data.account !== "cash" && !data.reference && !proof.length) more.reference = "Add the transaction reference or a screenshot";
    setErrors({ ...errors, ...more });
    if (!data || Object.keys(more).length) return;
    setBusy(true);
    setError(null);
    try {
      await api(`/api/quotations/${q.id}/advances`, { method: "POST", json: { ...data, proof_id: proof[0]?.id ?? null, no_proof_reason: proof.length ? "" : reason } });
      onDone();
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }
  return (
    <Card title="Take an advance">
      <form onSubmit={submit} noValidate className="grid gap-5 sm:grid-cols-2">
        <Field label="Amount (Rs)" error={errors.amount} hint={`Quotation total ${money(q.totals.total)}`}><Input name="amount" type="number" inputMode="decimal" min="0" step="any" autoFocus /></Field>
        <Field label="Received into" error={errors.account}>
          <Select name="account" value={account} onChange={(e) => setAccount(e.target.value)}>
            {Object.entries(ACCOUNT).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </Select>
        </Field>
        {account !== "cash" && <Field label="Transaction reference" error={errors.reference}><Input name="reference" maxLength={60} /></Field>}
        <Field label="Note (optional)" error={errors.note}><Input name="note" maxLength={500} /></Field>
        <div className="sm:col-span-2">
          <ProofInput proof={proof} setProof={setProof} reason={reason} setReason={setReason} error={errors.no_proof_reason} />
        </div>
        <p className="text-sm text-muted sm:col-span-2">An advance is the customer&apos;s money until the invoice uses it. A refund needs an admin&apos;s approval.</p>
        <div className="flex flex-col gap-3 sm:col-span-2">
          <Notice>{error}</Notice>
          <div className="flex flex-wrap gap-2">
            <Button type="submit" disabled={busy}>{busy ? "Recording" : "Record the advance"}</Button>
            <Button type="button" variant="secondary" onClick={onCancel}>Cancel</Button>
          </div>
        </div>
      </form>
    </Card>
  );
}
