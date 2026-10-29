"use client";

import { useParams } from "next/navigation";
import { Suspense, useState, type FormEvent } from "react";
import { type Item, ItemForm } from "@/components/inventory";
import { RequirePermission } from "@/components/shell";
import { Badge, Button, Card, EmptyState, ErrorState, Field, Input, Notice, PageHeader, SkeletonRows } from "@/components/ui";
import { api, useApi } from "@/lib/api";
import { money, qty, when } from "@/lib/format";
import { useSession } from "@/lib/session";

type Movement = { id: string; at: string; kind: string; qty: string; unit_cost: string; reason: string; user: string | null };
type Detail = Item & { movements: Movement[] };

const KINDS: Record<string, string> = {
  opening: "Opening stock", adjustment: "Adjustment", grn: "Received", issue: "Issued to repair",
  return: "Returned from repair", sale: "Sold", credit: "Customer return",
};

export default function ItemPage() {
  return (
    <RequirePermission permission="inventory">
      <Suspense fallback={<Card flush><SkeletonRows rows={6} /></Card>}>
        <ItemDetail />
      </Suspense>
    </RequirePermission>
  );
}

function ItemDetail() {
  const { id } = useParams<{ id: string }>();
  const { can } = useSession();
  const { data, error, reload } = useApi<Detail>(`/api/items/${id}`);
  const [mode, setMode] = useState<"view" | "edit" | "adjust">("view");

  if (error) return <Card flush><ErrorState message={error} onRetry={reload} /></Card>;
  if (!data) return <Card flush><SkeletonRows rows={6} /></Card>;
  const value = Number(data.on_hand) * Number(data.avg_cost);

  return (
    <>
      <PageHeader
        title={data.name}
        description={[data.brand, data.number].filter(Boolean).join(", ")}
        actions={mode === "view" && (
          <>
            <Button variant="secondary" onClick={() => setMode("edit")}>Edit item</Button>
            {can("stock-adjust") && <Button variant="secondary" onClick={() => setMode("adjust")}>Adjust stock</Button>}
          </>
        )}
      />
      {mode === "edit" && <div className="mb-6"><Card title="Edit item"><ItemForm item={data} onCancel={() => setMode("view")} onSaved={() => { setMode("view"); reload(); }} /></Card></div>}
      {mode === "adjust" && <div className="mb-6"><Adjust item={data} onDone={() => { setMode("view"); reload(); }} /></div>}

      <dl className="mb-4 grid grid-cols-2 gap-px overflow-hidden rounded-card bg-rule shell:grid-cols-4">
        {[
          ["In stock", <>{qty(data.on_hand)} {data.unit} {Number(data.on_hand) <= 0 ? <Badge tone="error">Out</Badge> : data.low_stock && <Badge tone="warning">Low</Badge>}</>],
          ["Sale price", money(data.sale_price)],
          ["Average cost", money(data.avg_cost)],
          ["Margin", data.margin_pct == null ? "Unknown" : `${data.margin_pct.toFixed(0)}%`],
        ].map(([label, v]) => (
          <div key={label as string} className="bg-surface p-4">
            <dt className="text-sm text-muted">{label}</dt>
            <dd className="num mt-1 flex flex-wrap items-center gap-2 text-xl font-semibold">{v}</dd>
          </div>
        ))}
      </dl>
      {data.margin_pct != null && data.margin_pct < 10 && (
        <div className="mb-4"><Notice tone="warning">The sale price is {data.margin_pct < 0 ? "below" : "close to"} what this item costs. Check the price.</Notice></div>
      )}

      <div className="grid gap-4 shell:grid-cols-[minmax(0,1fr)_minmax(0,1.6fr)]">
        <Card title="Details">
          <dl className="grid gap-4">
            <div><dt className="text-sm text-muted">Codes</dt>
              <dd>{data.codes.map((c) => <span key={c.code} className="num mr-3 inline-block">{c.code} <span className="text-sm text-muted">{c.kind === "mpn" ? "part number" : "barcode"}</span></span>)}</dd></div>
            {[["Category", data.category], ["Shelf or bin", data.location], ["Fits", data.fitment],
              ["Reorder at", `${qty(data.reorder_level)} ${data.unit}, order ${qty(data.reorder_qty)}`],
              ["Stock value at cost", money(value)]].map(([l, v]) => (
              <div key={l}><dt className="text-sm text-muted">{l}</dt><dd className={v ? "" : "text-muted"}>{v || "Not set"}</dd></div>
            ))}
          </dl>
        </Card>
        <Card title="Stock movements" flush>
          {!data.movements.length ? <EmptyState title="No movements yet">Opening stock, goods received, parts issued and adjustments appear here.</EmptyState> : (
            <table className="table-stack w-full text-left">
              <thead className="border-b border-rule text-sm text-muted">
                <tr><th className="px-5 py-3 font-medium">When</th><th className="px-3 py-3 font-medium">What</th>
                  <th className="px-3 py-3 text-right font-medium">Qty</th><th className="px-5 py-3 text-right font-medium">Cost each</th></tr>
              </thead>
              <tbody>
                {data.movements.map((m) => (
                  <tr key={m.id} className="border-t border-rule align-top first:border-t-0">
                    <td data-label="When" className="px-5 py-3 max-sm:px-0">{when(m.at)}<span className="block text-sm text-muted">{m.user ?? "System"}</span></td>
                    <td data-label="What" className="px-3 py-3 max-sm:px-0">{KINDS[m.kind] ?? m.kind}{m.reason && <span className="block text-sm text-muted">{m.reason}</span>}</td>
                    <td data-label="Qty" className={`num px-3 py-3 text-right font-medium max-sm:px-0 ${Number(m.qty) < 0 ? "text-error" : "text-success"}`}>{Number(m.qty) > 0 ? "+" : ""}{qty(m.qty)}</td>
                    <td data-label="Cost each" className="num px-5 py-3 text-right max-sm:px-0">{money(m.unit_cost)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
      </div>
    </>
  );
}

function Adjust({ item, onDone }: { item: Item; onDone: () => void }) {
  const [direction, setDirection] = useState<"in" | "out">("out");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const amount = Number(f.get("qty"));
    setBusy(true);
    setError(null);
    try {
      await api(`/api/items/${item.id}/adjust`, { method: "POST", json: {
        qty: String(direction === "out" ? -amount : amount), reason: f.get("reason"),
        unit_cost: direction === "in" && f.get("unit_cost") ? f.get("unit_cost") : null,
      } });
      onDone();
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  return (
    <Card title="Adjust stock">
      <form onSubmit={submit} className="grid gap-5 sm:grid-cols-2">
        <fieldset className="sm:col-span-2">
          <legend className="mb-1.5 text-sm font-medium text-ink-2">What happened</legend>
          <div className="flex flex-wrap gap-2">
            {([["out", "Remove stock (damaged, lost, count short)"], ["in", "Add stock (found, count over)"]] as const).map(([v, l]) => (
              <Button key={v} type="button" variant={direction === v ? "primary" : "secondary"} aria-pressed={direction === v} onClick={() => setDirection(v)}>{l}</Button>
            ))}
          </div>
        </fieldset>
        <Field label={`Quantity (${item.unit})`}><Input name="qty" type="number" inputMode="decimal" min={0.001} step="0.001" required /></Field>
        {direction === "in" && <Field label="Cost per unit (PKR)" hint="Leave blank to use the average cost."><Input name="unit_cost" type="number" inputMode="decimal" min={0} step="0.01" /></Field>}
        <div className="sm:col-span-2"><Field label="Reason" hint="Kept in the stock history and the audit log."><Input name="reason" required minLength={3} maxLength={300} placeholder="Stock count on 28 Oct" /></Field></div>
        <div className="flex flex-col gap-3 sm:col-span-2">
          <Notice>{error}</Notice>
          <div className="flex flex-wrap gap-2">
            <Button type="submit" variant="success" disabled={busy}>{busy ? "Saving" : "Save adjustment"}</Button>
            <Button type="button" variant="danger" onClick={onDone}>Cancel</Button>
          </div>
        </div>
      </form>
    </Card>
  );
}
