"use client";

import { createPortal } from "react-dom";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { type Po, type Vendor } from "@/components/purchasing";
import { Badge, Button, Card, Field, Input, Notice, Select } from "@/components/ui";
import { api, useApi } from "@/lib/api";
import { qty, qtyStep } from "@/lib/format";
import { lineQty, unitCost } from "@/lib/schemas";
import { useSession } from "@/lib/session";

/** Part lines that may need ordering (quotation or repair order). */
export type StockNeedLine = {
  id: string;
  kind: string;
  item_id: string | null;
  qty: string;
  description: string;
  declined?: boolean;
  item?: {
    number: string; name: string; unit: string; on_hand: string; short: string;
    reorder_level?: string; avg_cost?: string; low_stock?: boolean;
  };
};

/** Quotation: out / short / low. Repair: still-to-issue lines that are short or low on stock (already issued lines stay out). */
export function stockNeeds(lines: StockNeedLine[], mode: "quotation" | "repair" = "quotation") {
  return lines.filter((l) => {
    if (l.declined || l.kind !== "part" || !l.item) return false;
    const need = Number(l.qty);
    const onHand = Number(l.item.on_hand);
    if (mode === "repair") return need > 0 && (onHand < need || !!l.item.low_stock);
    return onHand <= 0 || Number(l.item.short) > 0 || !!l.item.low_stock;
  });
}

function stockTag(l: StockNeedLine, mode: "quotation" | "repair"): string {
  const onHand = Number(l.item!.on_hand);
  const short = mode === "repair" ? Math.max(Number(l.qty) - onHand, 0) : Number(l.item!.short);
  if (onHand <= 0) return "Out of stock";
  if (short > 0) return `Short by ${qty(short)}`;
  return "Low stock";
}

type DraftLine = { item_id: string; name: string; number: string; unit: string; qty: string; unit_cost: string };

function draftFromNeeds(lines: StockNeedLine[]): DraftLine[] {
  type Agg = { item_id: string; name: string; number: string; unit: string; need: number; on_hand: number; reorder_level: number; avg_cost: number };
  const byId = new Map<string, Agg>();
  for (const l of lines) {
    const id = l.item_id!;
    const have = byId.get(id);
    if (have) { have.need += Number(l.qty); continue; }
    byId.set(id, {
      item_id: id, name: l.description, number: l.item!.number, unit: l.item!.unit, need: Number(l.qty),
      on_hand: Number(l.item!.on_hand), reorder_level: Number(l.item!.reorder_level ?? 0),
      avg_cost: Number(l.item!.avg_cost ?? 0),
    });
  }
  return [...byId.values()].map((a) => {
    const short = Math.max(a.need - a.on_hand, 0);
    const reorder = a.reorder_level > 0 ? Math.max(a.reorder_level * 2 - a.on_hand, 0) : 0;
    return {
      item_id: a.item_id, name: a.name, number: a.number, unit: a.unit,
      qty: String(Math.max(short, reorder, 1)),
      unit_cost: a.avg_cost > 0 ? String(Math.round(a.avg_cost * 100) / 100) : "",
    };
  });
}

/** Parts that need ordering, with a purchase-order draft button. */
export function PartsToOrder({ lines, hint, mode = "quotation" }: {
  lines: StockNeedLine[]; hint?: string; mode?: "quotation" | "repair";
}) {
  const { can } = useSession();
  const [open, setOpen] = useState(false);
  const needs = stockNeeds(lines, mode);
  if (!needs.length) return null;
  return (
    <>
      <Card title="Parts to order" flush>
        <ul>
          {needs.map((l) => {
            const short = mode === "repair" ? Math.max(Number(l.qty) - Number(l.item!.on_hand), 0) : Number(l.item!.short);
            return (
              <li key={l.id} className="flex flex-wrap items-baseline justify-between gap-2 border-t border-rule px-4 py-3 first:border-t-0 shell:px-5">
                <div className="min-w-0">
                  <p className="font-medium">{l.description}</p>
                  <p className="flex flex-wrap gap-3 text-sm text-muted">
                    <span>{l.item!.number}</span>
                    <span>{qty(l.item!.on_hand)} {l.item!.unit} in stock</span>
                    <span>{mode === "repair" ? "Still to issue" : "Need"} {qty(l.qty)}</span>
                  </p>
                </div>
                <Badge tone={Number(l.item!.on_hand) <= 0 || short > 0 ? "error" : "warning"}>{stockTag(l, mode)}</Badge>
              </li>
            );
          })}
        </ul>
        {can("purchasing") && (
          <div className="border-t border-rule px-4 py-3 shell:px-5">
            <Button onClick={() => setOpen(true)}>Make a purchase order draft</Button>
          </div>
        )}
      </Card>
      {open && <PoDraftModal lines={needs} hint={hint} onClose={() => setOpen(false)} />}
    </>
  );
}

function PoDraftModal({ lines, hint, onClose }: {
  lines: StockNeedLine[]; hint?: string; onClose: () => void;
}) {
  const router = useRouter();
  const vendors = useApi<Vendor[]>("/api/vendors");
  const [vendorId, setVendorId] = useState("");
  const [rows, setRows] = useState<DraftLine[]>(() => draftFromNeeds(lines));
  const [tried, setTried] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const edit = (id: string, patch: Partial<DraftLine>) => setRows((rs) => rs.map((r) => (r.item_id === id ? { ...r, ...patch } : r)));
  const qtyBad = (r: DraftLine) => !lineQty.safeParse(r.qty).success;
  const costBad = (r: DraftLine) => !unitCost.safeParse(r.unit_cost).success;

  async function save() {
    setTried(true);
    setError(null);
    if (!vendorId) { setError("Choose the vendor."); return; }
    if (!rows.length) { setError("Add at least one item."); return; }
    if (rows.some((r) => qtyBad(r) || costBad(r))) { setError("Every item needs a quantity and a cost."); return; }
    setBusy(true);
    try {
      const saved = await api<Po>("/api/purchase-orders", {
        method: "POST",
        json: { vendor_id: vendorId, notes: "", expected_on: null,
                lines: rows.map((r) => ({ item_id: r.item_id, qty: r.qty, unit_cost: r.unit_cost })) },
      });
      onClose();
      router.push(`/purchase-orders/${saved.id}`);
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  if (typeof document === "undefined") return null;
  return createPortal(
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-auto bg-ink/40 p-4" role="dialog" aria-modal="true" aria-label="Purchase order draft">
      <div className="my-8 w-full max-w-2xl rounded-card bg-surface p-5">
        <h2 className="mb-1 text-lg font-semibold">Purchase order draft</h2>
        <p className="mb-4 text-sm text-muted">{hint ?? "Parts that are out of stock or low. Save a draft, then send it from Purchase orders."}</p>
        <div className="space-y-4">
          <Field required label="Vendor" error={tried && !vendorId ? "Choose the vendor" : undefined}>
            <Select value={vendorId} onChange={(e) => setVendorId(e.target.value)} required>
              <option value="">{vendors.data ? "Choose…" : "Loading vendors…"}</option>
              {(vendors.data ?? []).map((v) => <option key={v.id} value={v.id}>{v.name}</option>)}
            </Select>
          </Field>
          <ul className="rounded-card border border-rule">
            {rows.map((r) => (
              <li key={r.item_id} className="grid gap-3 border-t border-rule px-4 py-3 first:border-t-0 sm:grid-cols-[minmax(0,1fr)_6rem_9rem_auto] sm:items-end">
                <div className="min-w-0 self-center">
                  <p className="font-medium">{r.name}</p>
                  <p className="text-sm text-muted">{r.number}</p>
                </div>
                <Field required label="Qty" error={tried && qtyBad(r) ? "More than 0" : undefined}>
                  <Input type="number" inputMode="decimal" min="0" step={qtyStep(r.unit)} value={r.qty} onChange={(e) => edit(r.item_id, { qty: e.target.value })} />
                </Field>
                <Field required label="Cost each (Rs)" error={tried && costBad(r) ? "Enter the cost" : undefined}>
                  <Input type="number" inputMode="decimal" min="0" step="any" value={r.unit_cost} onChange={(e) => edit(r.item_id, { unit_cost: e.target.value })} />
                </Field>
                <Button variant="danger" onClick={() => setRows((rs) => rs.filter((x) => x.item_id !== r.item_id))}>Remove</Button>
              </li>
            ))}
          </ul>
          <Notice>{error}</Notice>
          <div className="flex flex-wrap gap-2">
            <Button onClick={save} disabled={busy || !rows.length}>{busy ? "Saving" : "Save draft"}</Button>
            <Button variant="danger" onClick={onClose}>Cancel</Button>
          </div>
        </div>
      </div>
    </div>,
    document.body,
  );
}
