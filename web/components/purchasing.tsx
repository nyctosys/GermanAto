"use client";

import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import { Badge, Button, Card, Field, Input, Notice } from "@/components/ui";
import { api } from "@/lib/api";
import { money, qty } from "@/lib/format";
import { useFormErrors } from "@/lib/form";
import { parseForm, vendorSchema } from "@/lib/schemas";
import { phone } from "@/lib/format";

// --- types mirroring app/routers/purchasing.py -----------------------------------------------------
export type Vendor = {
  id: string; number: string; name: string; contact_person: string; phone: string; email: string; address: string;
  terms_days: number; notes: string; is_active: boolean; version: number; owed?: string;
};
export type PoStatus = "draft" | "sent" | "partly_received" | "received" | "closed" | "cancelled";
export type PoLine = {
  id: string; item_id: string; number: string; name: string; unit: string; qty: string; unit_cost: string; amount: string;
  received: string; outstanding: string; avg_cost: string; sale_price: string; on_hand: string; codes: string[];
};
export type Receipt = {
  id: string; number: string; received_on: string; supplier_ref: string; notes: string; value: string;
  lines: { id: string; po_line_id: string; item_id: string; qty: string; unit_cost: string }[];
  bill: { id: string; number: string } | null;
};
export type Po = {
  id: string; number: string; status: PoStatus; version: number; expected_on: string | null; notes: string; sent_at: string | null;
  created_at: string; closed_reason: string; total: string;
  vendor: { id: string; number: string; name: string; phone: string; address: string; contact_person: string; terms_days: number };
  lines: PoLine[]; receipts: Receipt[]; warnings?: string[];
};
export type PickItem = { id: string; number: string; name: string; unit: string; avg_cost: string; sale_price: string; on_hand: string; reorder_qty: string; codes: string[] };

const PO: Record<PoStatus, [string, "neutral" | "success" | "warning" | "error" | "accent"]> = {
  draft: ["Draft", "warning"], sent: ["Sent, waiting for the goods", "accent"], partly_received: ["Part received", "accent"],
  received: ["Received", "success"], closed: ["Closed early", "neutral"], cancelled: ["Cancelled", "neutral"],
};
export const PoBadge = ({ status }: { status: PoStatus }) => <Badge tone={PO[status][1]}>{PO[status][0]}</Badge>;

export const BILL: Record<string, [string, "neutral" | "success" | "warning" | "error"]> = {
  unpaid: ["Unpaid", "error"], partly_paid: ["Partly paid", "warning"], paid: ["Paid", "success"], void: ["Voided", "neutral"],
};
export const BillBadge = ({ state }: { state: string }) => <Badge tone={BILL[state][1]}>{BILL[state][0]}</Badge>;

/** Margin after a cost change, as the owner reads it: (sale - cost) / sale. */
export const marginPct = (sale: number, cost: number) => (sale > 0 ? ((sale - cost) / sale) * 100 : null);

/** Search stock items by name or number, or scan a barcode or part number. Items only; no free text. */
export function ItemPicker({ onPick, onNotFound }: { onPick: (i: PickItem) => void; onNotFound?: (code: string) => void }) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<PickItem[]>([]);
  const [active, setActive] = useState(0);
  const [open, setOpen] = useState(false);
  const listId = useId();

  useEffect(() => {
    if (!q.trim()) return;
    const t = setTimeout(() => {
      api<PickItem[]>(`/api/purchase-catalog?${new URLSearchParams({ q: q.trim() })}`)
        .then((r) => { setResults(r); setActive(0); setOpen(true); })
        .catch(() => setResults([]));
    }, 180);
    return () => clearTimeout(t);
  }, [q]);

  const pick = (i: PickItem) => { onPick(i); setQ(""); setOpen(false); };
  return (
    <div className="relative">
      <input
        role="combobox" aria-expanded={open} aria-controls={listId} aria-autocomplete="list" aria-label="Add an item to the order"
        value={q}
        onChange={(e) => { setQ(e.target.value); if (!e.target.value.trim()) setOpen(false); }}
        onKeyDown={(e) => {
          if (e.key === "Enter") e.preventDefault();
          if (!open) return;
          if (e.key === "ArrowDown") { e.preventDefault(); setActive((a) => (results.length ? (a + 1) % results.length : 0)); }
          if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => (results.length ? (a - 1 + results.length) % results.length : 0)); }
          if (e.key === "Enter") { if (results.length) pick(results[active]); else onNotFound?.(q.trim()); }
          if (e.key === "Escape") setOpen(false);
        }}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        placeholder="Add an item: name, number, or scan a barcode or part number"
        enterKeyHint="search"
        className="min-h-11 w-full rounded-control border border-rule-strong bg-surface px-3 text-base placeholder:text-muted focus-visible:border-accent"
      />
      {open && (
        <ul id={listId} role="listbox" className="absolute z-20 mt-1 max-h-80 w-full overflow-auto rounded-control border border-rule-strong bg-surface py-1">
          {results.length ? results.map((i, n) => (
            <li key={i.id} role="option" aria-selected={n === active} onMouseDown={(e) => { e.preventDefault(); pick(i); }}
                className={`flex min-h-11 cursor-pointer items-center justify-between gap-3 px-3 py-1.5 ${n === active ? "bg-accent-soft" : ""}`}>
              <span className="min-w-0">
                <span className="block font-medium">{i.name}</span>
                <span className="block text-sm text-muted">{i.number}{i.codes[0] ? `, ${i.codes[0]}` : ""}</span>
              </span>
              <span className="num shrink-0 text-right text-sm text-muted">
                <span className="block">Cost {money(i.avg_cost)}</span>
                <span className="block">{qty(i.on_hand)} {i.unit} in stock</span>
              </span>
            </li>
          )) : (
            <li className="flex flex-wrap items-center justify-between gap-2 px-3 py-3 text-muted">
              <span>Nothing matches “{q}”.</span>
              {onNotFound && <Button type="button" variant="secondary" onMouseDown={(e) => { e.preventDefault(); onNotFound(q.trim()); setOpen(false); }}>Create this item</Button>}
            </li>
          )}
        </ul>
      )}
    </div>
  );
}

/** Add or edit a vendor. A name already on file is refused by the server. */
export function VendorForm({ vendor, onSaved, onCancel }: { vendor?: Vendor; onSaved: (v: Vendor) => void; onCancel: () => void }) {
  const [error, setError] = useState<string | null>(null);
  const { errors, setErrors, live, applyApi } = useFormErrors(vendorSchema);
  const [busy, setBusy] = useState(false);
  const form = useRef<HTMLFormElement>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    const { data, errors } = parseForm(vendorSchema, form.current!);
    setErrors(errors ?? {});
    if (!data) return;
    setBusy(true);
    setError(null);
    try {
      onSaved(vendor
        ? await api<Vendor>(`/api/vendors/${vendor.id}`, { method: "PUT", json: { ...data, version: vendor.version, is_active: new FormData(form.current!).get("is_active") === "on" } })
        : await api<Vendor>("/api/vendors", { method: "POST", json: data }));
    } catch (err) {
      setError(applyApi(err));
      setBusy(false);
    }
  }
  return (
    <form ref={form} noValidate onSubmit={submit} className="grid gap-5 sm:grid-cols-2" {...live}>
      <Field error={errors.name} label="Vendor name"><Input name="name" defaultValue={vendor?.name} required maxLength={120} autoComplete="off" autoFocus /></Field>
      <Field error={errors.contact_person} label="Contact person (optional)"><Input name="contact_person" defaultValue={vendor?.contact_person} maxLength={120} /></Field>
      <Field error={errors.phone} label="Phone (optional)"><Input name="phone" defaultValue={vendor ? phone(vendor.phone) : ""} inputMode="tel" /></Field>
      <Field error={errors.email} label="Email (optional)"><Input name="email" type="email" defaultValue={vendor?.email} /></Field>
      <div className="sm:col-span-2"><Field error={errors.address} label="Address (optional)"><Input name="address" defaultValue={vendor?.address} maxLength={300} /></Field></div>
      <Field error={errors.terms_days} label="Days to pay a bill" hint="Sets the due date on each bill. 0 means due at once.">
        <Input name="terms_days" type="number" inputMode="numeric" min={0} max={365} defaultValue={vendor?.terms_days ?? 0} />
      </Field>
      <Field error={errors.notes} label="Notes (optional)"><Input name="notes" defaultValue={vendor?.notes} /></Field>
      {vendor && (
        <label className="flex min-h-11 items-center gap-3 sm:col-span-2">
          <input type="checkbox" name="is_active" defaultChecked={vendor.is_active} className="size-5 accent-accent" />
          <span>Active <span className="text-sm text-muted">(an inactive vendor cannot be put on new orders)</span></span>
        </label>
      )}
      <div className="flex flex-col gap-3 sm:col-span-2">
        <Notice>{error}</Notice>
        <div className="flex flex-wrap gap-2">
          <Button type="submit" variant={vendor ? "success" : "primary"} disabled={busy}>{busy ? "Saving" : vendor ? "Save changes" : "Add vendor"}</Button>
          <Button type="button" variant="secondary" onClick={onCancel}>Cancel</Button>
        </div>
      </div>
    </form>
  );
}

/** A short form that asks why before a cancel, close or void. */
export function ReasonForm({ title, hint, confirm, busy, onSubmit, onCancel }:
  { title: string; hint: string; confirm: string; busy: boolean; onSubmit: (reason: string) => void; onCancel: () => void }) {
  const [reason, setReason] = useState("");
  return (
    <Card title={title}>
      <form onSubmit={(e) => { e.preventDefault(); onSubmit(reason); }} className="space-y-4">
        <Field label="Reason" hint={hint}><Input value={reason} onChange={(e) => setReason(e.target.value)} required minLength={3} autoFocus /></Field>
        <div className="flex flex-wrap gap-2">
          <Button type="submit" variant="danger" disabled={busy}>{confirm}</Button>
          <Button type="button" variant="secondary" onClick={onCancel}>Keep it</Button>
        </div>
      </form>
    </Card>
  );
}
