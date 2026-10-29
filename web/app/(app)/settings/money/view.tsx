"use client";

import { useState } from "react";
import { RequirePermission } from "@/components/shell";
import { Badge, Button, Card, EmptyState, ErrorState, Field, Input, Notice, PageHeader, SkeletonRows } from "@/components/ui";
import { api, useApi } from "@/lib/api";
import { day, money } from "@/lib/format";
import { fieldErrorsFromApi, liveForm } from "@/lib/form";
import { accountSchema, categorySchema, type FieldErrors, parseForm } from "@/lib/schemas";

type Account = { id: string; kind: string; name: string; opening_balance: string; opening_date: string; is_active: boolean; version: number; balance?: string };
type Category = { id: string; name: string; is_active: boolean; version: number };
const KIND: Record<string, string> = { cash: "Cash", bank: "Bank", wallet: "Mobile wallet" };

export default function MoneySettingsPage() {
  return (
    <RequirePermission permission="settings">
      <PageHeader title="Money settings" description="Where the money is kept, and the list of things money is spent on." />
      <div className="grid gap-4 shell:grid-cols-2">
        <Accounts />
        <Categories />
      </div>
    </RequirePermission>
  );
}

function Accounts() {
  const list = useApi<Account[]>("/api/accounts");
  const [editing, setEditing] = useState<string | null>(null);
  return (
    <Card title="Accounts" flush>
      {list.error ? <ErrorState message={list.error} onRetry={list.reload} /> : !list.data ? <SkeletonRows rows={3} /> : (
        <ul>
          {list.data.map((a) => (
            <li key={a.id} className="border-t border-rule px-4 py-4 first:border-t-0 shell:px-5">
              {editing === a.id ? <AccountForm a={a} onDone={() => { setEditing(null); list.reload(); }} onCancel={() => setEditing(null)} /> : (
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="font-medium">{a.name} <Badge>{KIND[a.kind]}</Badge></p>
                    <p className="text-sm text-muted">Started with {money(a.opening_balance)} on {day(a.opening_date)}</p>
                    {a.balance != null && <p className="num text-sm">In the account now: {money(a.balance)}</p>}
                  </div>
                  <Button variant="secondary" onClick={() => setEditing(a.id)}>Edit</Button>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
      <p className="border-t border-rule px-4 py-3 text-sm text-muted shell:px-5">The opening balance is what was in the account on the opening date. Every later change comes from money in and money out.</p>
    </Card>
  );
}

function AccountForm({ a, onDone, onCancel }: { a: Account; onDone: () => void; onCancel: () => void }) {
  const [errors, setErrors] = useState<FieldErrors>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const live = liveForm(accountSchema, errors, setErrors);
  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const { data, errors } = parseForm(accountSchema, e.currentTarget);
    setErrors(errors ?? {});
    if (!data) return;
    setBusy(true);
    setError(null);
    try {
      await api(`/api/accounts/${a.id}`, { method: "PUT", json: { ...data, is_active: true, version: a.version } });
      onDone();
    } catch (err) {
      const mapped = fieldErrorsFromApi(err);
      if (Object.keys(mapped.fields).length) setErrors((p) => ({ ...p, ...mapped.fields }));
      setError(mapped.banner);
      setBusy(false);
    }
  }
  return (
    <form noValidate onSubmit={submit} className="grid gap-4 sm:grid-cols-2" {...live}>
      <Field label="Name" error={errors.name}><Input name="name" defaultValue={a.name} maxLength={60} /></Field>
      <Field label="Opening balance (Rs)" error={errors.opening_balance}><Input name="opening_balance" inputMode="decimal" defaultValue={String(Number(a.opening_balance))} /></Field>
      <Field label="As of" error={errors.opening_date}><Input name="opening_date" type="date" defaultValue={a.opening_date} /></Field>
      <div className="flex flex-col gap-3 sm:col-span-2">
        <Notice>{error}</Notice>
        <div className="flex flex-wrap gap-2"><Button type="submit" variant="success" disabled={busy}>{busy ? "Saving" : "Save"}</Button><Button type="button" variant="secondary" onClick={onCancel}>Cancel</Button></div>
      </div>
    </form>
  );
}

function Categories() {
  const list = useApi<Category[]>("/api/expense-categories?include_inactive=true");
  const [editing, setEditing] = useState<string | null>(null);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [error, setError] = useState<string | null>(null);

  async function save(e: React.FormEvent<HTMLFormElement>, c?: Category) {
    e.preventDefault();
    const form = e.currentTarget;
    const { data, errors } = parseForm(categorySchema, form);
    setErrors(errors ?? {});
    if (!data) return;
    setError(null);
    try {
      if (c) await api(`/api/expense-categories/${c.id}`, { method: "PUT", json: { name: data.name, is_active: c.is_active, version: c.version } });
      else await api("/api/expense-categories", { method: "POST", json: data });
      form.reset();
      setEditing(null);
      list.reload();
    } catch (err) {
      setError((err as Error).message);
    }
  }
  async function toggle(c: Category) {
    setError(null);
    try { await api(`/api/expense-categories/${c.id}`, { method: "PUT", json: { name: c.name, is_active: !c.is_active, version: c.version } }); list.reload(); }
    catch (err) { setError((err as Error).message); }
  }

  return (
    <Card title="Expense categories" flush>
      <form noValidate onSubmit={(e) => save(e)} className="flex flex-wrap items-start gap-3 border-b border-rule p-4 shell:px-5" {...liveForm(categorySchema, errors, setErrors)}>
        <div className="min-w-48 flex-1"><Field label="New category" error={errors.name}><Input name="name" maxLength={80} placeholder="e.g. Garbage collection" /></Field></div>
        <Button type="submit" className="mt-7">Add</Button>
      </form>
      {error && <div className="p-4"><Notice>{error}</Notice></div>}
      {list.error ? <ErrorState message={list.error} onRetry={list.reload} /> : !list.data ? <SkeletonRows rows={5} />
        : !list.data.length ? <EmptyState title="No categories" />
        : (
          <ul>
            {list.data.map((c) => (
              <li key={c.id} className="flex flex-wrap items-center justify-between gap-3 border-t border-rule px-4 py-2.5 first:border-t-0 shell:px-5">
                {editing === c.id ? (
                  <form noValidate onSubmit={(e) => save(e, c)} className="flex flex-1 flex-wrap items-center gap-2">
                    <div className="min-w-40 flex-1"><Input name="name" defaultValue={c.name} maxLength={80} aria-label="Category name" autoFocus /></div>
                    <Button type="submit" variant="success">Save</Button><Button type="button" variant="secondary" onClick={() => setEditing(null)}>Cancel</Button>
                  </form>
                ) : (
                  <>
                    <span className={c.is_active ? "" : "text-muted line-through"}>{c.name}</span>
                    <span className="flex gap-2">
                      <Button variant="ghost" onClick={() => setEditing(c.id)}>Rename</Button>
                      <Button variant={c.is_active ? "danger" : "secondary"} onClick={() => toggle(c)}>{c.is_active ? "Retire" : "Restore"}</Button>
                    </span>
                  </>
                )}
              </li>
            ))}
          </ul>
        )}
      <p className="border-t border-rule px-4 py-3 text-sm text-muted shell:px-5">A retired category cannot be picked for new expenses but stays on the ones already recorded.</p>
    </Card>
  );
}
