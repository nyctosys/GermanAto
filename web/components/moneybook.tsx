"use client";

import { useState, type FormEvent } from "react";
import { type Uploaded } from "@/components/capture";
import { ACCOUNT, ProofInput } from "@/components/payments";
import { ReasonForm } from "@/components/purchasing";
import { useQueryParam } from "@/components/search";
import { Badge, Button, Card, EmptyState, ErrorState, Field, Input, Notice, Select, SkeletonRows } from "@/components/ui";
import { api, useApi } from "@/lib/api";
import { day, money, today } from "@/lib/format";
import { entrySchema, type FieldErrors } from "@/lib/schemas";
import { useSession } from "@/lib/session";
import Link from "next/link";

type Row = {
  id: string; number: string; date: string; source: string; party: string; detail: string; account: string; reference: string; amount: string;
  proof_url: string | null; no_proof_reason: string; missing_proof: boolean; status: "posted" | "voided"; link: string | null; by: string | null;
  entry_id?: string; note?: string;
};
type Page = { rows: Row[]; count: number; total: string; by_account: Record<string, string>; by_source: Record<string, string>; missing_proof: number };
type Category = { id: string; name: string };

export const SOURCE: Record<string, string> = {
  invoice_payment: "Invoice payment", advance: "Advance", other_income: "Other income", owner_capital: "Owner capital", transfer: "Transfer",
  vendor_payment: "Vendor payment", expense: "Expense", drawings: "Owner drawings",
};
const IN_SOURCES = ["invoice_payment", "advance", "other_income", "owner_capital", "transfer"];
const OUT_SOURCES = ["vendor_payment", "expense", "drawings", "transfer"];
const IN_KINDS = ["other_income", "owner_capital", "transfer"];
const OUT_KINDS = ["expense", "drawings", "transfer"];

/** The one page for every payment in or out, whatever its source (spec R12, R13). */
export function MoneyBook({ direction }: { direction: "in" | "out" }) {
  const { can } = useSession();
  const [q, setQ] = useQueryParam("q");
  const [source, setSource] = useQueryParam("source");
  const [account, setAccount] = useQueryParam("account");
  const [from, setFrom] = useQueryParam("from");
  const [to, setTo] = useQueryParam("to");
  const [missing, setMissing] = useQueryParam("missing");
  const [adding, setAdding] = useState(false);
  const [voiding, setVoiding] = useState<Row | null>(null);
  const [error, setError] = useState<string | null>(null);
  const params = new URLSearchParams({ q, ...(source && { source }), ...(account && { account }), ...(from && { date_from: from }), ...(to && { date_to: to }), ...(missing && { missing_proof: "true" }) });
  const list = useApi<Page>(`/api/money-${direction}?${params}`);
  const sources = direction === "in" ? IN_SOURCES : OUT_SOURCES;
  const canRecord = direction === "in" ? can("payments-in") : can("expenses") || can("payments-out");

  async function void_(reason: string) {
    try {
      await api(`/api/money-entries/${voiding!.entry_id}/void`, { method: "POST", json: { reason } });
      setVoiding(null);
      list.reload();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1>{direction === "in" ? "Money in" : "Money out"}</h1>
          <p className="max-w-[60ch] text-muted">
            {direction === "in" ? "Every payment received, from every source, in one place." : "Every payment made, from every source, in one place."}
          </p>
        </div>
        {canRecord && !adding && <Button onClick={() => setAdding(true)}>{direction === "in" ? "Record money in" : "Record money out"}</Button>}
      </div>

      {adding && <div className="mb-4"><EntryForm direction={direction} onCancel={() => setAdding(false)} onDone={() => { setAdding(false); list.reload(); }} /></div>}
      {voiding && <div className="mb-4"><ReasonForm title={`Void ${voiding.number}`} hint="It stays on record, struck through, and the books are corrected." confirm="Void it" busy={false} onCancel={() => setVoiding(null)} onSubmit={void_} /></div>}
      {error && <div className="mb-4"><Notice>{error}</Notice></div>}

      <Card title="Find">
        <div className="grid gap-4 sm:grid-cols-2 shell:grid-cols-4">
          <Field label="Search"><Input type="search" defaultValue={q} onChange={(e) => setQ(e.target.value.trim())} placeholder="Name, number or reference" /></Field>
          <Field label="Source">
            <Select value={source} onChange={(e) => setSource(e.target.value)}>
              <option value="">All sources</option>
              {sources.map((s) => <option key={s} value={s}>{SOURCE[s]}</option>)}
            </Select>
          </Field>
          <Field label="Account">
            <Select value={account} onChange={(e) => setAccount(e.target.value)}>
              <option value="">All accounts</option>
              {Object.entries(ACCOUNT).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </Select>
          </Field>
          <label className="flex min-h-11 cursor-pointer items-center gap-3 self-end">
            <input type="checkbox" checked={!!missing} onChange={(e) => setMissing(e.target.checked ? "1" : "")} className="size-5 accent-accent" />
            <span>Only those with no proof</span>
          </label>
          <Field label="From"><Input type="date" value={from} max={to || today()} onChange={(e) => setFrom(e.target.value)} /></Field>
          <Field label="To"><Input type="date" value={to} min={from} max={today()} onChange={(e) => setTo(e.target.value)} /></Field>
        </div>
      </Card>

      {list.data && (
        <div className="my-4 grid gap-4 sm:grid-cols-2 shell:grid-cols-3">
          <Card title="Total"><p className="num text-xl">{money(list.data.total)}</p><p className="text-sm text-muted">{list.data.count} {list.data.count === 1 ? "record" : "records"}. Transfers between accounts are not counted.</p></Card>
          <Card title="By account">
            <dl className="space-y-1">
              {Object.entries(list.data.by_account).map(([k, v]) => <div key={k} className="flex justify-between gap-3"><dt>{ACCOUNT[k]}</dt><dd className="num">{money(v)}</dd></div>)}
              {!Object.keys(list.data.by_account).length && <p className="text-muted">None</p>}
            </dl>
          </Card>
          <Card title="By source">
            <dl className="space-y-1">
              {Object.entries(list.data.by_source).map(([k, v]) => <div key={k} className="flex justify-between gap-3"><dt>{SOURCE[k]}</dt><dd className="num">{money(v)}</dd></div>)}
              {!Object.keys(list.data.by_source).length && <p className="text-muted">None</p>}
            </dl>
          </Card>
        </div>
      )}
      {list.data && list.data.missing_proof > 0 && <div className="mb-4"><Notice tone="warning">{list.data.missing_proof} {list.data.missing_proof === 1 ? "record has" : "records have"} no proof, only a reason.</Notice></div>}

      <Card flush>
        {list.error ? <ErrorState message={list.error} onRetry={list.reload} /> : !list.data ? <SkeletonRows />
          : !list.data.rows.length ? <EmptyState title="Nothing here">No records match. Loosen the filters or record something.</EmptyState>
          : (
            <table className="table-stack w-full">
              <thead><tr className="text-left text-sm text-muted">
                <th className="px-4 py-2 font-normal shell:px-5">Record</th><th className="px-4 py-2 font-normal">From or to</th><th className="px-4 py-2 font-normal">Account</th>
                <th className="px-4 py-2 font-normal">Proof</th><th className="px-4 py-2 text-right font-normal shell:pr-5">Amount</th>
              </tr></thead>
              <tbody>
                {list.data.rows.map((r) => (
                  <tr key={`${r.source}-${r.id}`} className={`border-t border-rule ${r.status === "voided" ? "text-muted" : ""}`}>
                    <td className="px-4 py-3 shell:px-5 max-sm:px-0">
                      {r.link ? <Link href={r.link} className={`font-medium underline ${r.status === "voided" ? "line-through" : ""}`}>{r.number}</Link> : <span className={`font-medium ${r.status === "voided" ? "line-through" : ""}`}>{r.number}</span>}
                      <span className="block text-sm text-muted">{SOURCE[r.source]}, {day(r.date)}{r.by ? `, ${r.by}` : ""}</span>
                    </td>
                    <td data-label="From or to" className="px-4 py-3 max-sm:px-0">{r.party || <span className="text-muted">Not named</span>}{r.detail && <span className="block text-sm text-muted">{r.detail}</span>}</td>
                    <td data-label="Account" className="px-4 py-3 max-sm:px-0">{ACCOUNT[r.account]}{r.reference && <span className="block text-sm text-muted">Ref {r.reference}</span>}</td>
                    <td data-label="Proof" className="px-4 py-3 max-sm:px-0">
                      {r.proof_url ? <a href={r.proof_url} target="_blank" rel="noreferrer" className="underline">View</a>
                        : <span className="text-sm text-warning">No proof: {r.no_proof_reason}</span>}
                    </td>
                    <td data-label="Amount" className="px-4 py-3 text-right shell:pr-5 max-sm:px-0">
                      <span className={`num block ${r.status === "voided" ? "line-through" : ""}`}>{money(r.amount)}</span>
                      {r.status === "voided" && <Badge>Voided</Badge>}
                      {r.entry_id && r.status === "posted" && canRecord && <Button variant="ghost" onClick={() => setVoiding(r)}>Void</Button>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
      </Card>
    </>
  );
}

function EntryForm({ direction, onDone, onCancel }: { direction: "in" | "out"; onDone: () => void; onCancel: () => void }) {
  const { can } = useSession();
  const kinds = (direction === "in" ? IN_KINDS : OUT_KINDS).filter((k) => (k === "expense" ? can("expenses") : k === "transfer" ? can("payments-out") : k === "drawings" ? can("payments-out") : can("payments-in")));
  const cats = useApi<Category[]>("/api/expense-categories");
  const [kind, setKind] = useState(kinds[0] ?? "other_income");
  const [v, setV] = useState({ amount: "", account: "cash", to_account: "", category_id: "", party: "", reference: "", note: "", occurred_on: today() });
  const [proof, setProof] = useState<Uploaded[]>([]);
  const [reason, setReason] = useState("");
  const [errors, setErrors] = useState<FieldErrors>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const set = (p: Partial<typeof v>) => setV((x) => ({ ...x, ...p }));
  const transfer = kind === "transfer";

  async function submit(e: FormEvent) {
    e.preventDefault();
    const r = entrySchema.safeParse({ ...v, kind, proof, reason });
    const found: FieldErrors = {};
    if (!r.success) for (const i of r.error.issues) found[String(i.path[0])] ??= i.message;
    setErrors(found);
    if (!r.success) return;
    setBusy(true);
    setError(null);
    try {
      await api("/api/money-entries", { method: "POST", json: { kind, amount: v.amount.trim(), account: v.account, to_account: transfer ? v.to_account : null,
        category_id: kind === "expense" ? v.category_id : null, party: v.party, reference: v.reference, note: v.note, occurred_on: v.occurred_on,
        proof_id: proof[0]?.id ?? null, no_proof_reason: proof.length ? "" : reason } });
      onDone();
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }
  const LABEL: Record<string, string> = { other_income: "Other income", owner_capital: "Owner puts money in", transfer: "Transfer between accounts", expense: "Expense", drawings: "Owner takes money out" };

  return (
    <Card title={direction === "in" ? "Record money in" : "Record money out"}>
      <form noValidate onSubmit={submit} className="grid gap-5 sm:grid-cols-2">
        <Field label="What is it">
          <Select value={kind} onChange={(e) => setKind(e.target.value as typeof kind)}>
            {kinds.map((k) => <option key={k} value={k}>{LABEL[k]}</option>)}
          </Select>
        </Field>
        <Field label="Amount (Rs)" error={errors.amount}><Input inputMode="decimal" value={v.amount} onChange={(e) => set({ amount: e.target.value })} autoFocus /></Field>
        <Field label={transfer ? "From" : direction === "in" ? "Received into" : "Paid from"}>
          <Select value={v.account} onChange={(e) => set({ account: e.target.value })}>
            {Object.entries(ACCOUNT).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
          </Select>
        </Field>
        {transfer && (
          <Field label="To" error={errors.to_account}>
            <Select value={v.to_account} onChange={(e) => set({ to_account: e.target.value })}>
              <option value="">Choose an account</option>
              {Object.entries(ACCOUNT).filter(([k]) => k !== v.account).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
            </Select>
          </Field>
        )}
        {kind === "expense" && (
          <Field label="Category" error={errors.category_id}>
            <Select value={v.category_id} onChange={(e) => set({ category_id: e.target.value })}>
              <option value="">Choose a category</option>
              {cats.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </Select>
          </Field>
        )}
        {!transfer && <Field label={direction === "in" ? "Received from (optional)" : "Paid to (optional)"} error={errors.party}><Input value={v.party} onChange={(e) => set({ party: e.target.value })} maxLength={120} /></Field>}
        <Field label="Date" error={errors.occurred_on}><Input type="date" max={today()} value={v.occurred_on} onChange={(e) => set({ occurred_on: e.target.value })} /></Field>
        <Field label="Transaction reference (bank or wallet)" error={errors.reference}><Input value={v.reference} onChange={(e) => set({ reference: e.target.value })} maxLength={60} /></Field>
        <div className="sm:col-span-2"><ProofInput proof={proof} setProof={setProof} reason={reason} setReason={setReason} error={errors.reason} /></div>
        <div className="flex flex-col gap-3 sm:col-span-2">
          <Notice>{error}</Notice>
          <div className="flex flex-wrap gap-2"><Button type="submit" disabled={busy}>{busy ? "Recording" : "Record it"}</Button><Button type="button" variant="secondary" onClick={onCancel}>Cancel</Button></div>
        </div>
      </form>
    </Card>
  );
}
