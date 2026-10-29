"use client";

import { useState, type FormEvent, type ReactNode } from "react";
import { type Uploaded, PhotoCapture } from "@/components/capture";
import { Button, Card, Field, Input, Select } from "@/components/ui";
import { money, when } from "@/lib/format";
import { useLiveErrors } from "@/lib/form";
import { type FieldErrors, issuesToFieldErrors, paymentRowSchema } from "@/lib/schemas";

export type Payment = { id: string; number: string; kind?: string; refunded?: boolean; invoice_id?: string | null; status: string; account: string; reference: string; amount: string;
  received_at: string; received_by: string | null; proof_url: string | null; no_proof_reason: string };

export const ACCOUNT: Record<string, string> = { cash: "Cash", bank: "Bank transfer", wallet: "Mobile wallet" };

/** Proof is always asked for; with none, the person must say why (owner decision 4). */
export function ProofInput({ proof, setProof, reason, setReason, error }:
  { proof: Uploaded[]; setProof: (v: Uploaded[]) => void; reason: string; setReason: (v: string) => void; error?: string }) {
  return (
    <div className="space-y-3">
      <PhotoCapture value={proof} onChange={(v) => setProof(v.slice(-1))} label="Add proof: photo, screenshot or PDF" accept="image/*,application/pdf" note="Proof" />
      {!proof.length && (
        <Field label="No proof? Say why" hint="For example: cash at the counter, no slip." error={error}>
          <Input value={reason} onChange={(e) => setReason(e.target.value)} maxLength={500} />
        </Field>
      )}
    </div>
  );
}

export function PaymentList({ title, payments, footer, action }:
  { title: string; payments: Payment[]; footer?: ReactNode; action?: (p: Payment) => ReactNode }) {
  return (
    <Card title={title} flush>
      <ul>
        {payments.map((p) => (
          <li key={p.id} className="flex items-start justify-between gap-3 border-t border-rule px-4 py-3 first:border-t-0 shell:px-5">
            <span className="min-w-0">
              <span className="block font-medium">{p.number}{p.kind === "advance" ? ", advance" : ""}</span>
              <span className="block text-sm text-muted">{ACCOUNT[p.account]}{p.reference ? `, ref ${p.reference}` : ""}, {when(p.received_at)}{p.received_by ? `, ${p.received_by}` : ""}</span>
              {p.status === "voided" && <span className="block text-sm text-error">Voided</span>}
              {p.refunded && <span className="block text-sm text-warning">Refunded to the customer</span>}
              {p.proof_url ? <a href={p.proof_url} target="_blank" rel="noreferrer" className="text-sm underline">Proof</a>
                : <span className="block text-sm text-warning">No proof: {p.no_proof_reason}</span>}
            </span>
            <span className="flex shrink-0 flex-col items-end gap-1">
              <span className={`num ${p.status === "voided" ? "text-muted line-through" : ""}`}>{money(p.amount)}</span>
              {action?.(p)}
            </span>
          </li>
        ))}
      </ul>
      {footer}
    </Card>
  );
}

// --- taking money ----------------------------------------------------------------------------

export type PaymentBody = { amount: string; account: string; reference: string; note: string; proof_id: string | null; no_proof_reason: string };
type Row = { key: string; amount: string; account: string; reference: string; proof: Uploaded[]; reason: string };

const newRow = (amount = ""): Row => ({ key: crypto.randomUUID(), amount, account: "cash", reference: "", proof: [], reason: "" });

/** One row's problems, by field (lib/schemas paymentRowSchema). */
function rowErrors(r: Row): FieldErrors {
  const res = paymentRowSchema.safeParse(r);
  return res.success ? {} : issuesToFieldErrors(res.error.issues);
}

const toBody = (r: Row, note = ""): PaymentBody => ({
  amount: r.amount.trim(), account: r.account, reference: r.reference.trim(), note,
  proof_id: r.proof[0]?.id ?? null, no_proof_reason: r.proof.length ? "" : r.reason.trim(),
});

function RowFields({ r, set, errors }: { r: Row; set: (p: Partial<Row>) => void; errors: FieldErrors }) {
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <Field label="Amount (Rs)" error={errors.amount}>
        <Input type="number" inputMode="decimal" min="0" step="any" value={r.amount} onChange={(e) => set({ amount: e.target.value })} />
      </Field>
      <Field label="Received into">
        <Select value={r.account} onChange={(e) => set({ account: e.target.value })}>
          {Object.entries(ACCOUNT).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </Select>
      </Field>
      {r.account !== "cash" && (
        <Field label="Transaction reference" error={errors.reference}>
          <Input value={r.reference} onChange={(e) => set({ reference: e.target.value })} maxLength={60} />
        </Field>
      )}
      <div className="sm:col-span-2">
        <ProofInput proof={r.proof} setProof={(proof) => set({ proof })} reason={r.reason} setReason={(reason) => set({ reason })} error={errors.reason} />
      </div>
    </div>
  );
}

/** Record one payment (an advance, or a payment on an invoice). */
export function PaymentForm({ title, hint, suggested, busy, onSubmit, onCancel, note }:
  { title: string; hint?: string; suggested?: string; busy: boolean; note?: ReactNode;
    onSubmit: (b: PaymentBody) => void; onCancel: () => void }) {
  const [row, setRow] = useState<Row>(() => newRow(suggested ?? ""));
  const { errors, activate, live } = useLiveErrors(row, rowErrors);
  return (
    <Card title={title}>
      <form noValidate className="space-y-4" {...live} onSubmit={(e: FormEvent) => {
        e.preventDefault();
        activate();
        if (!Object.keys(rowErrors(row)).length) onSubmit(toBody(row));
      }}>
        {hint && <p className="text-sm text-muted">{hint}</p>}
        <RowFields r={row} set={(p) => setRow((r) => ({ ...r, ...p }))} errors={errors} />
        {note}
        <div className="flex flex-wrap gap-2">
          <Button type="submit" disabled={busy}>{busy ? "Recording" : "Record the payment"}</Button>
          <Button type="button" variant="danger" onClick={onCancel}>Cancel</Button>
        </div>
      </form>
    </Card>
  );
}

/** Payments taken at a counter sale: one or more rows (split cash and transfer) that must add up to the total. */
export function SplitPayments({ total, rows, setRows, tried }:
  { total: number; rows: Row[]; setRows: (fn: (rs: Row[]) => Row[]) => void; tried: boolean }) {
  const sum = rows.reduce((s, r) => s + (Number(r.amount) || 0), 0);
  return (
    <div className="space-y-5">
      {rows.map((r, i) => (
        <div key={r.key} className={i ? "border-t border-rule pt-5" : ""}>
          {rows.length > 1 && (
            <div className="mb-2 flex items-center justify-between">
              <p className="text-sm font-medium text-ink-2">Payment {i + 1}</p>
              <Button type="button" variant="danger" onClick={() => setRows((rs) => rs.filter((x) => x.key !== r.key))}>Remove</Button>
            </div>
          )}
          <RowFields r={r} set={(p) => setRows((rs) => rs.map((x) => (x.key === r.key ? { ...x, ...p } : x)))} errors={tried ? rowErrors(r) : {}} />
        </div>
      ))}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Button type="button" variant="ghost" onClick={() => setRows((rs) => [...rs, newRow(String(Math.max(total - sum, 0) || ""))])}>Split the payment</Button>
        <p className={`num text-sm ${Math.abs(sum - total) < 0.005 ? "text-success" : "text-error"}`}>
          {money(sum)} of {money(total)}{Math.abs(sum - total) < 0.005 ? ", paid in full" : ""}
        </p>
      </div>
    </div>
  );
}

export const splitValid = (rows: Row[], total: number) =>
  rows.every((r) => !Object.keys(rowErrors(r)).length) && Math.abs(rows.reduce((s, r) => s + Number(r.amount), 0) - total) < 0.005;
export const splitBodies = (rows: Row[]) => rows.map((r) => toBody(r));
export { newRow, type Row as PaymentRow };

/**
 * Give money back: an advance (the whole amount, with the admin's reason) or an overpayment.
 * Same proof rule as every other money record.
 */
export function RefundForm({ title, hint, amount, fixedAmount, needsReason, busy, onSubmit, onCancel }:
  { title: string; hint?: string; amount: string; fixedAmount?: boolean; needsReason?: boolean; busy: boolean;
    onSubmit: (b: PaymentBody & { reason: string }) => void; onCancel: () => void }) {
  const [row, setRow] = useState<Row>(() => newRow(amount));
  const [why, setWhy] = useState("");
  const { errors, active, activate, live } = useLiveErrors(row, rowErrors);
  const whyBad = needsReason && why.trim().length < 3;
  return (
    <Card title={title}>
      <form noValidate className="space-y-4" {...live} onSubmit={(e: FormEvent) => {
        e.preventDefault();
        activate();
        if (!Object.keys(rowErrors(row)).length && !whyBad) onSubmit({ ...toBody(row), reason: why.trim() });
      }}>
        {hint && <p className="text-sm text-muted">{hint}</p>}
        {needsReason && <Field label="Why is it being refunded?" error={active && whyBad ? "Say why" : undefined}><Input value={why} onChange={(e) => setWhy(e.target.value)} maxLength={500} /></Field>}
        <RowFields r={row} set={(p) => setRow((r) => ({ ...r, ...(fixedAmount ? { ...p, amount: r.amount } : p) }))} errors={errors} />
        <div className="flex flex-wrap gap-2">
          <Button type="submit" variant="danger" disabled={busy}>{busy ? "Recording" : "Give the money back"}</Button>
          <Button type="button" variant="danger" onClick={onCancel}>Cancel</Button>
        </div>
      </form>
    </Card>
  );
}
