"use client";

import { useState, type FormEvent } from "react";
import { Button, Field, Input, Notice, Select } from "@/components/ui";
import { ListMulti } from "@/components/list-multi";
import { ListSelect } from "@/components/list-select";
import { api } from "@/lib/api";
import { useSession } from "@/lib/session";

export type Item = {
  id: string; number: string; name: string; brand: string; category: string; unit: string; fitment: string;
  location: string; sale_price: string; avg_cost: string; reorder_level: string; reorder_qty: string;
  is_active: boolean; version: number; codes: { id?: string; kind: "barcode" | "mpn"; code: string }[];
  on_hand: string; low_stock: boolean; margin_pct: number | null;
};

export const UNITS = ["pcs", "set", "pair", "litre", "kg", "metre", "box"];

type CodeRow = { kind: "barcode" | "mpn"; code: string };

/** Add or edit a stock item. Every item needs at least one barcode or part number. */
export function ItemForm({ item, presetCode, presetName, onSaved, onCancel }:
  { item?: Item; presetCode?: string; presetName?: string; onSaved: (i: Item) => void; onCancel: () => void }) {
  const { can } = useSession();
  const [codes, setCodes] = useState<CodeRow[]>(item?.codes.map(({ kind, code }) => ({ kind, code })) ?? [{ kind: "barcode", code: presetCode ?? "" }]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const filled = codes.filter((c) => c.code.trim());
    if (!filled.length) { setError("Add the barcode or the manufacturer part number."); return; }
    const body: Record<string, unknown> = {
      name: f.get("name"), brand: f.get("brand"), category: f.get("category"), unit: f.get("unit"),
      fitment: f.get("fitment"), location: f.get("location"), sale_price: f.get("sale_price") || "0",
      reorder_level: f.get("reorder_level") || "0", reorder_qty: item?.reorder_qty ?? "0", codes: filled,
    };
    if (!item && f.get("opening_qty")) {
      body.opening_qty = f.get("opening_qty");
      body.opening_cost = f.get("opening_cost") || "0";
    }
    setBusy(true);
    setError(null);
    try {
      const saved = item
        ? await api<Item>(`/api/items/${item.id}`, { method: "PUT", json: { ...body, version: item.version, is_active: item.is_active } })
        : await api<Item>("/api/items", { method: "POST", json: body });
      setBusy(false);
      onSaved(saved);
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="grid gap-5 sm:grid-cols-2 shell:grid-cols-3">
      <div className="sm:col-span-2"><Field required label="Name"><Input name="name" defaultValue={item?.name ?? presetName} required maxLength={160} placeholder="Oil filter" /></Field></div>
      <Field label="Brand (optional)"><ListSelect name="brand" kind="part_brand" defaultValue={item?.brand} placeholder="Choose a brand" /></Field>

      <fieldset className="space-y-2 sm:col-span-2 shell:col-span-3">
        <legend className="mb-1 text-sm font-medium text-ink-2">Barcode or manufacturer part number</legend>
        {codes.map((row, i) => (
          <div key={i} className="flex flex-wrap gap-2">
            <div className="w-40 shrink-0">
              <Select aria-label="Code type" value={row.kind} onChange={(e) => setCodes(codes.map((r, j) => (j === i ? { ...r, kind: e.target.value as CodeRow["kind"] } : r)))}>
                <option value="barcode">Barcode</option>
                <option value="mpn">Part number</option>
              </Select>
            </div>
            <div className="min-w-48 flex-1">
              <Input aria-label="Code" value={row.code} autoFocus={i === 0 && !presetCode && !item} spellCheck={false} autoCapitalize="characters"
                     onChange={(e) => setCodes(codes.map((r, j) => (j === i ? { ...r, code: e.target.value } : r)))}
                     placeholder={row.kind === "barcode" ? "Scan or type" : "e.g. 11 42 7 583 220"} />
            </div>
            {codes.length > 1 && <Button type="button" variant="danger" onClick={() => setCodes(codes.filter((_, j) => j !== i))}>Remove</Button>}
          </div>
        ))}
        {codes.length < 10 && (
          <Button type="button" variant="secondary" onClick={() => setCodes([...codes, { kind: "mpn", code: "" }])}>Add another code</Button>
        )}
      </fieldset>

      <Field required label="Category"><ListSelect name="category" kind="part_category" defaultValue={item?.category} placeholder="Choose a category" /></Field>
      <Field label="Unit">
        <Select name="unit" defaultValue={item?.unit ?? "pcs"}>{UNITS.map((u) => <option key={u}>{u}</option>)}</Select>
      </Field>
      <Field label="Shelf or bin"><Input name="location" defaultValue={item?.location} placeholder="A3" /></Field>
      <div className="sm:col-span-2"><Field label="Fits" hint="Type to narrow the list (e.g. BM for BMW). Tick every car this part fits; a name not listed yet is added with one click."><ListMulti name="fitment" kind="fitment" defaultValue={item?.fitment} /></Field></div>
      <Field required label="Sale price (PKR)"><Input name="sale_price" type="number" inputMode="decimal" min={0} step="0.01" defaultValue={item?.sale_price ?? ""} required /></Field>
      <Field label="Reorder when stock reaches" hint="How much to order is decided on the purchase order."><Input name="reorder_level" type="number" inputMode="decimal" min={0} step="0.001" defaultValue={item ? Number(item.reorder_level) : ""} /></Field>

      {!item && can("stock-adjust") && (
        <>
          <Field label="Opening stock" hint="What's on the shelf today."><Input name="opening_qty" type="number" inputMode="decimal" min={0} step="0.001" /></Field>
          <Field label="Cost per unit (PKR)" hint="What you paid, for the stock value."><Input name="opening_cost" type="number" inputMode="decimal" min={0} step="0.01" /></Field>
        </>
      )}

      {item && (
        <>
          <Field label="Stock now" hint="Changes through Adjust stock or goods received, so the history stays right.">
            <Input readOnly tabIndex={-1} value={`${Number(item.on_hand)} ${item.unit}`} className="bg-paper-3" />
          </Field>
          <Field label="Average cost per unit (PKR)" hint="Worked out from what you paid on each delivery.">
            <Input readOnly tabIndex={-1} value={Number(item.avg_cost).toLocaleString()} className="bg-paper-3" />
          </Field>
        </>
      )}

      <div className="flex flex-col gap-3 sm:col-span-2 shell:col-span-3">
        <Notice>{error}</Notice>
        <div className="flex flex-wrap gap-2">
          <Button type="submit" variant={item ? "success" : "primary"} disabled={busy}>{busy ? "Saving" : item ? "Save changes" : "Add item"}</Button>
          <Button type="button" variant="danger" onClick={onCancel}>Cancel</Button>
        </div>
      </div>
    </form>
  );
}
