"use client";

import { useEffect, useState, type FormEvent } from "react";
import { type Uploaded } from "@/components/capture";
import { ACCOUNT, ProofInput, ProofLinks } from "@/components/payments";
import { ReasonForm } from "@/components/purchasing";
import { SearchInput, useQueryParam } from "@/components/search";
import { SortTh, sortRows, useTableSort } from "@/components/sort";
import { Badge, Button, Card, EmptyState, ErrorState, Field, Input, Notice, Select, SkeletonRows } from "@/components/ui";
import { api, useApi } from "@/lib/api";
import { day, money, today } from "@/lib/format";
import { useLiveErrors } from "@/lib/form";
import { entrySchema, issuesToFieldErrors } from "@/lib/schemas";
import { useSession } from "@/lib/session";
import Link from "next/link";

type Row = {
  id: string; number: string; date: string; source: string; party: string; detail: string; account: string; reference: string; amount: string;
  proof_url: string | null; proof_urls?: string[]; no_proof_reason: string; missing_proof: boolean; status: "posted" | "voided"; link: string | null; by: string | null;
  entry_id?: string; note?: string;
};
type Page = { rows: Row[]; count: number; total: string; by_account: Record<string, string>; by_source: Record<string, string>; missing_proof: number };
type Category = { id: string; name: string };

export const SOURCE: Record<string, string> = {
  invoice_payment: "Invoice payment", advance: "Advance", other_income: "Other income", owner_capital: "Owner capital", transfer: "Transfer",
  vendor_payment: "Vendor payment", expense: "Expense", drawings: "Owner drawings", refund: "Refund to customer", salary: "Salary", salary_advance: "Salary advance",
};
const IN_SOURCES = ["invoice_payment", "advance", "other_income", "owner_capital", "transfer"];
const OUT_SOURCES = ["vendor_payment", "expense", "drawings", "transfer", "refund", "salary", "salary_advance"];
const IN_KINDS = ["invoice_payment", "other_income", "owner_capital", "transfer"];
const OUT_KINDS = ["expense", "drawings", "transfer"];

/** The one page for every payment in or out, whatever its source (spec R12, R13). */
export function MoneyBook({ direction }: { direction: "in" | "out" }) {
  const { can } = useSession();
  const [q, setQ] = useQueryParam("q");
  const [qText, setQText] = useState(q);
  const [source, setSource] = useQueryParam("source");
  const [account, setAccount] = useQueryParam("account");
  const [from, setFrom] = useQueryParam("from");
  const [to, setTo] = useQueryParam("to");
  const [missing, setMissing] = useQueryParam("missing");
  const [adding, setAdding] = useState<null | "expense" | "other">(null);
  const [voiding, setVoiding] = useState<Row | null>(null);
  const [error, setError] = useState<string | null>(null);
  const params = new URLSearchParams({ q, ...(source && { source }), ...(account && { account }), ...(from && { date_from: from }), ...(to && { date_to: to }), ...(missing && { missing_proof: "true" }) });
  const list = useApi<Page>(`/api/money-${direction}?${params}`);
  const sources = direction === "in" ? IN_SOURCES : OUT_SOURCES;
  const day0 = today();
  const todays = useApi<Page>(direction === "out" ? `/api/money-out?${new URLSearchParams({ source: "expense", date_from: day0, date_to: day0 })}` : null);
  const { sort, set } = useTableSort();
  const rows = sortRows(list.data?.rows ?? [], sort, {
    number: (r) => r.number,
    party: (r) => r.party || "",
    account: (r) => r.account,
    proof: (r) => (r.proof_url || r.proof_urls?.length ? "1" : r.no_proof_reason || ""),
    amount: (r) => Number(r.amount),
    date: (r) => r.date,
  });
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
        {canRecord && !adding && (
          <div className="flex flex-wrap gap-2">
            {direction === "out" && can("expenses") && <Button onClick={() => setAdding("expense")}>Add a daily expense</Button>}
            <Button variant={direction === "out" && can("expenses") ? "secondary" : "primary"} onClick={() => setAdding("other")}>{direction === "in" ? "Record money in" : "Record other money out"}</Button>
          </div>
        )}
      </div>

      {adding && <div className="mb-4"><EntryForm direction={direction} only={adding === "expense" ? "expense" : undefined} onCancel={() => setAdding(null)} onDone={() => { setAdding(null); list.reload(); todays.reload(); }} /></div>}
      {direction === "out" && todays.data && (
        <div className="mb-4 rounded-card bg-surface px-4 py-3 shell:px-5">
          <p><span className="font-medium">Today&apos;s expenses: </span><span className="num">{money(todays.data.total)}</span> <span className="text-sm text-muted">across {todays.data.count} {todays.data.count === 1 ? "record" : "records"}</span></p>
        </div>
      )}
      {voiding && <div className="mb-4"><ReasonForm title={`Void ${voiding.number}`} hint="It stays on record, struck through, and the books are corrected." confirm="Void it" busy={false} onCancel={() => setVoiding(null)} onSubmit={void_} /></div>}
      {error && <div className="mb-4"><Notice>{error}</Notice></div>}

      <Card title="Find">
        <div className="grid gap-4 sm:grid-cols-2 shell:grid-cols-4">
          <Field label="Search"><SearchInput value={qText} onChange={(v) => { setQText(v); setQ(v.trim()); }} placeholder="Name, number or reference" /></Field>
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
                <SortTh label="Record" k="number" sort={sort} onSort={set} className="px-4 py-2 font-normal shell:px-5" />
                <SortTh label="From or to" k="party" sort={sort} onSort={set} className="px-4 py-2 font-normal" />
                <SortTh label="Account" k="account" sort={sort} onSort={set} className="px-4 py-2 font-normal" />
                <SortTh label="Proof" k="proof" sort={sort} onSort={set} className="px-4 py-2 font-normal" />
                <SortTh label="Amount" k="amount" sort={sort} onSort={set} align="right" className="px-4 py-2 text-right font-normal shell:pr-5" />
              </tr></thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={`${r.source}-${r.id}`} className={`border-t border-rule ${r.status === "voided" ? "text-muted" : ""}`}>
                    <td className="px-4 py-3 shell:px-5 max-sm:px-0">
                      {r.link ? <Link href={r.link} className={`font-medium underline ${r.status === "voided" ? "line-through" : ""}`}>{r.number}</Link> : <span className={`font-medium ${r.status === "voided" ? "line-through" : ""}`}>{r.number}</span>}
                      <span className="block text-sm text-muted">{SOURCE[r.source]}, {day(r.date)}{r.by ? `, ${r.by}` : ""}</span>
                    </td>
                    <td data-label="From or to" className="px-4 py-3 max-sm:px-0">{r.party || <span className="text-muted">Not named</span>}{r.detail && <span className="block text-sm text-muted">{r.detail}</span>}</td>
                    <td data-label="Account" className="px-4 py-3 max-sm:px-0">{ACCOUNT[r.account]}{r.reference && <span className="block text-sm text-muted">Ref {r.reference}</span>}</td>
                    <td data-label="Proof" className="px-4 py-3 max-sm:px-0">
                      <ProofLinks urls={r.proof_urls} url={r.proof_url} reason={r.no_proof_reason} label="View" className="underline" />
                    </td>
                    <td data-label="Amount" className="px-4 py-3 text-right shell:pr-5 max-sm:px-0">
                      <span className={`num block ${r.status === "voided" ? "line-through" : ""}`}>{money(r.amount)}</span>
                      {r.status === "voided" && <Badge>Voided</Badge>}
                      {r.entry_id && r.status === "posted" && canRecord && <Button variant="danger" onClick={() => setVoiding(r)}>Void</Button>}
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

function EntryForm({ direction, only, onDone, onCancel }: { direction: "in" | "out"; only?: string; onDone: () => void; onCancel: () => void }) {
  const { can } = useSession();
  const kinds = (direction === "in" ? IN_KINDS : OUT_KINDS).filter((k) => (only ? k === only : direction === "out" && k === "expense" ? false : true))
    .filter((k) => (k === "expense" ? can("expenses") : k === "transfer" ? can("payments-out") : k === "drawings" ? can("payments-out") : can("payments-in")));
  const cats = useApi<Category[]>("/api/expense-categories");
  const owing = useApi<{ id: string; number: string; customer: string; balance: string }[]>(direction === "in" ? "/api/invoices?status=unpaid" : null);
  const [invoiceId, setInvoiceId] = useState("");
  const [invoiceError, setInvoiceError] = useState<string | undefined>();
  const [kind, setKind] = useState(kinds[0] ?? "other_income");
  const [v, setV] = useState({ amount: "", account: "cash", to_account: "", category_id: "", party: "", reference: "", note: "", occurred_on: today() });
  // Remount the uncontrolled amount box when an invoice pick fills it in.
  const [amountKey, setAmountKey] = useState(0);
  const [proof, setProof] = useState<Uploaded[]>([]);
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [postClosingWarn, setPostClosingWarn] = useState<string | null>(null);
  const transfer = kind === "transfer";
  const invoicePay = kind === "invoice_payment";
  const snapshot = { ...v, kind, proof, reason };
  const { errors, activate, live, applyApi, clearServer } = useLiveErrors(snapshot, (s) => {
    const r = entrySchema.safeParse(s);
    return r.success ? {} : issuesToFieldErrors(r.error.issues);
  });
  const set = (p: Partial<typeof v>) => { clearServer(); setError(null); setV((x) => ({ ...x, ...p })); };

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!v.occurred_on || !v.account) { setPostClosingWarn(null); return; }
      try {
        const r = await api<{ already_closed: boolean }>(`/api/cash-closes/expected?account=${v.account}&on=${v.occurred_on}`);
        if (cancelled) return;
        setPostClosingWarn(r.already_closed
          ? "This day is already signed for this account. Recording here is a post-closing transaction — the original close stays, and you must sign a post-closing count on Cash close afterwards."
          : null);
      } catch {
        if (!cancelled) setPostClosingWarn(null);
      }
    })();
    return () => { cancelled = true; };
  }, [v.occurred_on, v.account]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    activate();
    const r = entrySchema.safeParse({ ...snapshot, kind: invoicePay ? "other_income" : kind });
    if (!r.success) return;
    if (invoicePay && !invoiceId) { setInvoiceError("Choose the invoice this payment is for."); return; }
    setBusy(true);
    setError(null);
    clearServer();
    try {
      if (invoicePay) {
        await api(`/api/invoices/${invoiceId}/payments`, { method: "POST", json: { amount: v.amount.trim(), account: v.account, reference: v.reference, note: v.note,
          proof_id: proof[0]?.id ?? null, proof_ids: proof.map((p) => p.id), no_proof_reason: proof.length ? "" : reason } });
        onDone();
        return;
      }
      const res = await api<{ post_closing?: boolean; post_closing_message?: string }>("/api/money-entries", { method: "POST", json: { kind, amount: v.amount.trim(), account: v.account, to_account: transfer ? v.to_account : null,
        category_id: kind === "expense" ? v.category_id : null, party: v.party, reference: v.reference, note: v.note, occurred_on: v.occurred_on,
        proof_id: proof[0]?.id ?? null, proof_ids: proof.map((p) => p.id), no_proof_reason: proof.length ? "" : reason } });
      if (res.post_closing && res.post_closing_message) {
        // Keep the form message visible briefly via toast path is enough; still finish.
      }
      onDone();
    } catch (err) {
      setError(applyApi(err));
      setBusy(false);
    }
  }
  const LABEL: Record<string, string> = { invoice_payment: "Payment for an invoice", expense: "Daily expense", other_income: "Other income", owner_capital: "Owner puts money in", transfer: "Transfer between accounts", drawings: "Owner takes money out" };

  return (
    <Card title={only === "expense" ? "Add a daily expense" : direction === "in" ? "Record money in" : "Record money out"}>
      <form noValidate onSubmit={submit} className="grid gap-5 sm:grid-cols-2" {...live}>
        {kinds.length > 1 && <Field required label="What is it">
          <Select value={kind} onChange={(e) => setKind(e.target.value as typeof kind)}>
            {kinds.map((k) => <option key={k} value={k}>{LABEL[k]}</option>)}
          </Select>
        </Field>}
        {invoicePay && (
          <Field required label="Invoice" error={invoiceError}>
            <Select value={invoiceId} onChange={(e) => {
              const inv = owing.data?.find((i) => i.id === e.target.value);
              setInvoiceId(e.target.value);
              setInvoiceError(undefined);
              if (inv) {
                set({ amount: String(Number(inv.balance)) });
                setAmountKey((k) => k + 1);
              }
            }}>
              <option value="">{owing.data?.length === 0 ? "No invoice is waiting for payment" : "Choose an invoice"}</option>
              {owing.data?.map((i) => <option key={i.id} value={i.id}>{i.number}, {i.customer}, owes {money(i.balance)}</option>)}
            </Select>
          </Field>
        )}
        <Field required label="Amount (Rs)" error={errors.amount}>
          <Input key={amountKey} inputMode="decimal" autoComplete="off" name="amount" defaultValue={v.amount} onChange={(e) => set({ amount: e.target.value })} autoFocus />
        </Field>
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
          <Field required label="Category" error={errors.category_id}>
            <Select value={v.category_id} onChange={(e) => set({ category_id: e.target.value })}>
              <option value="">Choose a category</option>
              {cats.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </Select>
          </Field>
        )}
        {!transfer && <Field label={direction === "in" ? "Received from (optional)" : "Paid to (optional)"} error={errors.party}><Input value={v.party} onChange={(e) => set({ party: e.target.value })} maxLength={120} /></Field>}
        <Field required label="Date" error={errors.occurred_on}><Input type="date" max={today()} value={v.occurred_on} onChange={(e) => set({ occurred_on: e.target.value })} /></Field>
        <Field required={false} label="Transaction reference (bank or wallet)" error={errors.reference}><Input value={v.reference} onChange={(e) => set({ reference: e.target.value })} maxLength={60} /></Field>
        <div className="sm:col-span-2"><ProofInput proof={proof} setProof={(p) => { clearServer(); setError(null); setProof(p); }} reason={reason} setReason={(r) => { clearServer(); setError(null); setReason(r); }} error={errors.reason} /></div>
        <div className="flex flex-col gap-3 sm:col-span-2">
          {postClosingWarn && <Notice tone="warning">{postClosingWarn} <Link href="/cash-close" className="underline">Open Cash close</Link> after you save.</Notice>}
          <Notice>{error}</Notice>
          <div className="flex flex-wrap gap-2"><Button type="submit" disabled={busy}>{busy ? "Recording" : postClosingWarn ? "Record post-closing entry" : "Record it"}</Button><Button type="button" variant="danger" onClick={onCancel}>Cancel</Button></div>
        </div>
      </form>
    </Card>
  );
}
