"use client";

import { PhoneInput } from "@/components/phone-input";
import Link from "next/link";
import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import { createPortal } from "react-dom";
import { Button, Checkbox, Field, Input, Notice, Select } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { phone } from "@/lib/format";
import { useRecords } from "@/lib/records";
import { useFormErrors } from "@/lib/form";
import { customerSchema, parseForm } from "@/lib/schemas";

export type Customer = {
  id: string; number: string; kind: "individual" | "company"; name: string; phone: string; phone_alt: string;
  email: string; cnic: string; ntn: string; address: string; notes: string; whatsapp_opt_out: boolean; is_active: boolean; version: number;
};

/** Search-as-you-type customer picker. Arrow keys and Enter work; every row is a 44px target. */
export function CustomerPicker({ value, onChange, exclude }:
  { value: Customer | null; onChange: (c: Customer | null) => void; exclude?: string }) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<Customer[]>([]);
  const [active, setActive] = useState(0);
  const [open, setOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const listId = useId();
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (q.trim().length < 2) return;
    const t = setTimeout(() => {
      api<Customer[]>(`/api/customers?${new URLSearchParams({ q, limit: "8" })}`)
        .then((r) => { setResults(r.filter((c) => c.id !== exclude)); setActive(0); setOpen(true); })
        .catch(() => setResults([]));
    }, 200);
    return () => clearTimeout(t);
  }, [q, exclude]);

  if (value) {
    return (
      <div className="flex min-h-11 items-center justify-between gap-3 rounded-control border border-rule-strong bg-surface px-3 py-2">
        <span className="min-w-0">
          <span className="block font-medium">{value.name}</span>
          <span className="flex gap-3 text-sm text-muted"><span>{value.number}</span><span className="num">{phone(value.phone)}</span></span>
        </span>
        <Button type="button" variant="ghost" onClick={() => { onChange(null); setQ(""); setTimeout(() => input.current?.focus()); }}>
          Change
        </Button>
      </div>
    );
  }

  const pick = (c: Customer) => { onChange(c); setOpen(false); };
  return (
    <div className="flex items-start gap-2">
    <div className="relative min-w-0 flex-1">
      <input
        ref={input}
        role="combobox"
        aria-expanded={open}
        aria-controls={listId}
        aria-autocomplete="list"
        value={q}
        onChange={(e) => { setQ(e.target.value); if (e.target.value.trim().length < 2) setOpen(false); }}
        onKeyDown={(e) => {
          if (!open || !results.length) return;
          if (e.key === "ArrowDown") { e.preventDefault(); setActive((a) => (a + 1) % results.length); }
          if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => (a - 1 + results.length) % results.length); }
          if (e.key === "Enter") { e.preventDefault(); pick(results[active]); }
          if (e.key === "Escape") setOpen(false);
        }}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        placeholder="Name, phone, customer number or plate"
        className="min-h-11 w-full rounded-control border border-rule-strong bg-surface px-3 text-base placeholder:text-muted focus-visible:border-ink"
      />
      {open && (
        <ul id={listId} role="listbox" className="absolute z-20 mt-1 max-h-80 w-full overflow-auto rounded-control border border-rule-strong bg-surface py-1">
          {results.length ? results.map((c, i) => (
            <li key={c.id} role="option" aria-selected={i === active}
                onMouseDown={(e) => { e.preventDefault(); pick(c); }}
                className={`flex min-h-11 cursor-pointer flex-col justify-center px-3 py-1.5 ${i === active ? "bg-accent-soft" : ""}`}>
              <span className="font-medium">{c.name}</span>
              <span className="flex gap-3 text-sm text-muted"><span>{c.number}</span><span className="num">{phone(c.phone)}</span></span>
            </li>
          )) : <li className="px-3 py-3 text-muted">No customer matches “{q}”.</li>}
        </ul>
      )}
    </div>
    <Button type="button" variant="secondary" aria-label="New customer" onClick={() => setCreating(true)}>+ New customer</Button>
    {creating && createPortal(
      <div className="fixed inset-0 z-50 flex items-start justify-center overflow-auto bg-ink/40 p-4" role="dialog" aria-modal="true" aria-label="New customer">
        <div className="my-8 w-full max-w-2xl rounded-card bg-surface p-5">
          <h2 className="mb-4 text-lg font-semibold">New customer</h2>
          <CustomerForm onSaved={(c) => { setCreating(false); onChange(c); }} onCancel={() => setCreating(false)} />
        </div>
      </div>, document.body)}
    </div>
  );
}

/** Create or edit a customer. A phone already on file asks before creating a second record. */
export function CustomerForm({ customer, onSaved, onCancel }:
  { customer?: Customer; onSaved: (c: Customer) => void; onCancel: () => void }) {
  const [error, setError] = useState<string | null>(null);
  const { errors, setErrors, live, applyApi } = useFormErrors(customerSchema);
  const [matches, setMatches] = useState<Customer[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [kind, setKind] = useState<"individual" | "company">(customer?.kind ?? "individual");
  const form = useRef<HTMLFormElement>(null);

  async function save(allowDuplicate = false) {
    const { data, errors } = parseForm(customerSchema, form.current!);
    setErrors(errors ?? {});
    if (!data) return;
    const { is_active, ...fields } = data;
    const body = { ...fields, allow_duplicate_phone: allowDuplicate };
    setBusy(true);
    setError(null);
    try {
      const saved = customer
        ? await api<Customer>(`/api/customers/${customer.id}`, { method: "PUT", json: { ...body, version: customer.version, is_active } })
        : await api<Customer>("/api/customers", { method: "POST", json: body });
      useRecords.getState().put("customers", saved);
      setBusy(false);
      onSaved(saved);
    } catch (err) {
      const detail = err instanceof ApiError ? (err.detail as { code?: string; matches?: Customer[] }) : undefined;
      if (detail?.code === "duplicate_phone") setMatches(detail.matches ?? []);
      else setError(applyApi(err));
      setBusy(false);
    }
  }

  return (
    <form ref={form} noValidate onSubmit={(e: FormEvent) => { e.preventDefault(); e.stopPropagation(); save(); }} className="grid gap-5 sm:grid-cols-2" {...live}>
      <Field error={errors.name} label="Name"><Input name="name" defaultValue={customer?.name} required maxLength={120} autoComplete="off" /></Field>
      <Field error={errors.kind} label="Type">
        <Select name="kind" value={kind} onChange={(e) => setKind(e.target.value as "individual" | "company")}>
          <option value="individual">Individual</option>
          <option value="company">Company or fleet</option>
        </Select>
      </Field>
      <Field error={errors.phone} label="Mobile" hint="Used for WhatsApp updates."><PhoneInput name="phone" defaultValue={customer?.phone} required /></Field>
      <Field error={errors.phone_alt} label="Other phone (optional)"><PhoneInput name="phone_alt" defaultValue={customer?.phone_alt} /></Field>
      <Field error={errors.email} label="Email (optional)"><Input name="email" type="email" defaultValue={customer?.email} /></Field>
      {kind === "individual"
        ? <Field error={errors.cnic} label="CNIC (optional)" hint="13 digits, e.g. 35202-1234567-1"><Input name="cnic" defaultValue={customer?.cnic} inputMode="numeric" /></Field>
        : <Field error={errors.ntn} label="NTN (optional)" hint="7 digits, e.g. 1234567-8"><Input name="ntn" defaultValue={customer?.ntn} inputMode="numeric" /></Field>}
      {kind === "company" && <input type="hidden" name="cnic" value="" />}
      {kind === "individual" && <input type="hidden" name="ntn" value="" />}
      <div className="sm:col-span-2"><Field error={errors.address} label="Address (optional)"><Input name="address" defaultValue={customer?.address} maxLength={300} /></Field></div>
      <div className="sm:col-span-2"><Field error={errors.notes} label="Notes (optional)"><Input name="notes" defaultValue={customer?.notes} /></Field></div>
      <div className="sm:col-span-2">
        <Checkbox name="whatsapp_opt_out" defaultChecked={customer?.whatsapp_opt_out} label="Don't send WhatsApp messages" hint="The customer asked not to be messaged." />
        {customer && <Checkbox name="is_active" defaultChecked={customer.is_active} label="Active" hint="Inactive customers are hidden from searches but keep their history." />}
      </div>

      {matches && (
        <div className="space-y-3 rounded-control border border-warning/30 bg-warning-soft p-4 sm:col-span-2">
          <p className="font-medium text-warning">This phone number is already on file</p>
          <ul className="space-y-1">
            {matches.map((m) => (
              <li key={m.id}><Link href={`/customers/${m.id}`} className="underline">{m.name}</Link> <span className="text-muted">{m.number}</span></li>
            ))}
          </ul>
          <p className="text-sm text-ink-2">Use the existing customer, or create a second record if this really is someone else (a family member sharing a phone).</p>
          <Button type="button" variant="secondary" disabled={busy} onClick={() => save(true)}>Create a separate customer</Button>
        </div>
      )}

      <div className="flex flex-col gap-3 sm:col-span-2">
        <Notice>{error}</Notice>
        <div className="flex flex-wrap gap-2">
          <Button type="submit" variant={customer ? "success" : "primary"} disabled={busy}>{busy ? "Saving" : customer ? "Save changes" : "Add customer"}</Button>
          <Button type="button" variant="danger" onClick={onCancel}>Cancel</Button>
        </div>
      </div>
    </form>
  );
}
