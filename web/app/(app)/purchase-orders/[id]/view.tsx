"use client";

import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState, type FormEvent } from "react";
import { linkButton } from "@/components/estimates";
import { type Item, ItemForm } from "@/components/inventory";
import { ItemPicker, marginPct, type Po, ReasonForm, type PoLine, PoBadge, type Receipt, type Vendor } from "@/components/purchasing";
import { PURCHASING, RequirePermission } from "@/components/shell";
import { Badge, Button, Card, ErrorState, Field, Input, Notice, Select, SkeletonRows } from "@/components/ui";
import { api, useApi } from "@/lib/api";
import { day, money, qty, today, qtyStep } from "@/lib/format";
import { liveForm } from "@/lib/form";
import { billSchema, type FieldErrors, lineQty, parseForm, unitCost } from "@/lib/schemas";
import { useSession } from "@/lib/session";

export default function PurchaseOrderPage() {
  return (
    <RequirePermission permission={PURCHASING}>
      <Suspense fallback={<Card flush><SkeletonRows rows={8} /></Card>}>
        <Loader />
      </Suspense>
    </RequirePermission>
  );
}

function Loader() {
  const { id } = useParams<{ id: string }>();
  const fresh = id === "new";
  const po = useApi<Po>(fresh ? null : `/api/purchase-orders/${id}`);
  const [latest, setLatest] = useState<Po | null>(null);
  if (po.error) return <Card flush><ErrorState message={po.error} onRetry={po.reload} /></Card>;
  if (!fresh && !po.data) return <Card flush><SkeletonRows rows={8} /></Card>;
  const current = latest && po.data && latest.id === po.data.id && latest.version >= po.data.version ? latest : po.data;
  if (!current) return <Editor initial={null} />;
  return current.status === "draft" ? <Editor key={`${current.id}-${current.version}`} initial={current} onSaved={setLatest} /> : <View po={current} onChange={setLatest} reload={po.reload} />;
}

// --- draft ---------------------------------------------------------------------------------------

type Line = { key: string; item_id: string; name: string; number: string; unit: string; qty: string; unit_cost: string; avg_cost: string; on_hand: string };

function Editor({ initial, onSaved }: { initial: Po | null; onSaved?: (p: Po) => void }) {
  const router = useRouter();
  const { can } = useSession();
  const preset = useSearchParams().get("vendor") ?? "";
  const vendors = useApi<Vendor[]>("/api/vendors");
  const [vendorId, setVendorId] = useState(initial?.vendor.id ?? preset);
  const [expectedOn, setExpectedOn] = useState(initial?.expected_on ?? "");
  const [notes, setNotes] = useState(initial?.notes ?? "");
  const [lines, setLines] = useState<Line[]>(() => (initial?.lines ?? []).map((l) => ({
    key: l.id, item_id: l.item_id, name: l.name, number: l.number, unit: l.unit, qty: String(Number(l.qty)), unit_cost: String(Number(l.unit_cost)),
    avg_cost: l.avg_cost, on_hand: l.on_hand,
  })));
  const [creating, setCreating] = useState<string | null>(null);
  const [dirty, setDirty] = useState(false);
  const [tried, setTried] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!dirty) return;
    const block = (e: BeforeUnloadEvent) => e.preventDefault();
    window.addEventListener("beforeunload", block);
    return () => window.removeEventListener("beforeunload", block);
  }, [dirty]);

  const addLine = (i: { id: string; name: string; number: string; unit: string; avg_cost: string; on_hand: string; reorder_qty?: string }) => {
    setLines((ls) => (ls.some((l) => l.item_id === i.id)
      ? ls
      : [...ls, { key: crypto.randomUUID(), item_id: i.id, name: i.name, number: i.number, unit: i.unit, avg_cost: i.avg_cost, on_hand: i.on_hand,
                  qty: Number(i.reorder_qty) > 0 ? String(Number(i.reorder_qty)) : "1", unit_cost: Number(i.avg_cost) > 0 ? String(Number(i.avg_cost)) : "" }]));
    setDirty(true);
  };
  const edit = (key: string, patch: Partial<Line>) => { setLines((ls) => ls.map((l) => (l.key === key ? { ...l, ...patch } : l))); setDirty(true); };
  const qtyBad = (l: Line) => !lineQty.safeParse(l.qty).success;
  const costBad = (l: Line) => !unitCost.safeParse(l.unit_cost).success;
  const total = lines.reduce((s, l) => s + (Number(l.qty) || 0) * (Number(l.unit_cost) || 0), 0);

  /** Everything under its reorder level that this vendor supplies (or that has no vendor set), at the vendor's last price. */
  async function addLowStock() {
    if (!vendorId) { setError("Choose the vendor first. Only the items they supply are added."); return; }
    setError(null);
    const low = await api<(Item & { vendor_cost: string | null })[]>(`/api/items?${new URLSearchParams({ stock: "low", limit: "100", vendor_id: vendorId })}`);
    low.forEach((i) => addLine({ ...i, avg_cost: i.vendor_cost ?? i.avg_cost, reorder_qty: String(Math.max(Number(i.reorder_level) * 2 - Number(i.on_hand), 1)) }));
    if (!low.length) setError("Nothing is below its reorder level for this vendor.");
  }

  async function save(send: boolean) {
    setTried(true);
    setError(null);
    if (!vendorId) { setError("Choose the vendor."); return; }
    if (!lines.length) { setError("Add at least one item."); return; }
    if (lines.some((l) => qtyBad(l) || costBad(l))) { setError("Every item needs a quantity and a cost."); return; }
    setBusy(true);
    try {
      const body = { vendor_id: vendorId, expected_on: expectedOn || null, notes, version: initial?.version,
                     lines: lines.map((l) => ({ item_id: l.item_id, qty: l.qty, unit_cost: l.unit_cost })) };
      const saved = initial ? await api<Po>(`/api/purchase-orders/${initial.id}`, { method: "PUT", json: body })
        : await api<Po>("/api/purchase-orders", { method: "POST", json: body });
      setDirty(false);
      const done = send ? await api<Po>(`/api/purchase-orders/${saved.id}/send`, { method: "POST", json: { version: saved.version } }) : saved;
      if (initial && onSaved) { onSaved(done); setBusy(false); } // the page shows the saved order (or the sent one) in place
      else router.push(`/purchase-orders/${done.id}`);
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  return (
    <div onBlurCapture={() => setTried(true)}>
      <div className="mb-6">
        <h1>{initial ? `Purchase order ${initial.number}` : "New purchase order"}</h1>
        <p className="text-muted">{initial ? <PoBadge status="draft" /> : "Choose the vendor, add what you need, then send it."}</p>
      </div>
      <div className="grid gap-4 shell:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        <div className="space-y-4">
          <Card title="Items" flush>
            <div className="space-y-3 border-b border-rule p-4 shell:px-5">
              <ItemPicker onPick={addLine} onNotFound={can("inventory") ? setCreating : undefined} />
              {can("inventory") && <Button variant="ghost" onClick={addLowStock}>Add everything below its reorder level</Button>}
            </div>
            {creating !== null && (
              <div className="border-b border-rule p-4 shell:px-5">
                <p className="mb-3 font-medium">New item</p>
                <ItemForm presetCode={creating} onCancel={() => setCreating(null)}
                          onSaved={(i) => { addLine(i); setCreating(null); }} />
              </div>
            )}
            <ul>
              {lines.map((l) => (
                <li key={l.key} className="grid gap-3 border-t border-rule px-4 py-3 first:border-t-0 sm:grid-cols-[minmax(0,1fr)_6rem_9rem_auto] sm:items-end shell:px-5">
                  <div className="min-w-0 self-center">
                    <p className="font-medium">{l.name}</p>
                    <p className="flex flex-wrap gap-3 text-sm text-muted"><span>{l.number}</span><span>{qty(l.on_hand)} {l.unit} in stock</span>
                      {Number(l.avg_cost) > 0 && <span className="num">Average cost {money(l.avg_cost)}</span>}</p>
                  </div>
                  <Field label="Qty" error={tried && qtyBad(l) ? "More than 0" : undefined}>
                    <Input type="number" inputMode="decimal" min="0" step={qtyStep(l.unit)} value={l.qty} onChange={(e) => edit(l.key, { qty: e.target.value })} />
                  </Field>
                  <Field label="Cost each (Rs)" error={tried && costBad(l) ? "Enter the cost" : undefined}>
                    <Input type="number" inputMode="decimal" min="0" step="any" value={l.unit_cost} onChange={(e) => edit(l.key, { unit_cost: e.target.value })} />
                  </Field>
                  <Button variant="danger" onClick={() => { setLines((ls) => ls.filter((x) => x.key !== l.key)); setDirty(true); }}>Remove</Button>
                </li>
              ))}
            </ul>
            {!lines.length && <p className="px-4 py-6 text-muted shell:px-5">Scan a barcode or search for an item above. Only items already in Inventory can be ordered, so every purchase is costed the same way.</p>}
          </Card>
          <Notice>{error}</Notice>
          <div className="flex flex-wrap gap-2">
            <Button onClick={() => save(true)} disabled={busy}>{busy ? "Working" : "Send to the vendor"}</Button>
            <Button variant="success" onClick={() => save(false)} disabled={busy || (!!initial && !dirty)}>Save draft</Button>
          </div>
          <p className="text-sm text-muted">Sending locks the order. Print it to hand or send to the vendor; WhatsApp comes with the messaging stage.</p>
        </div>
        <div className="space-y-4">
          <Card title="Order">
            <div className="space-y-5">
              <Field label="Vendor" error={tried && !vendorId ? "Choose the vendor" : undefined} hint={can("vendors") ? undefined : "Ask someone with the vendors permission to add a new vendor."}>
                <Select value={vendorId} onChange={(e) => { setVendorId(e.target.value); setDirty(true); }}>
                  <option value="">Choose a vendor</option>
                  {vendors.data?.map((v) => <option key={v.id} value={v.id}>{v.name}</option>)}
                </Select>
              </Field>
              <Field label="Expected on (optional)"><Input type="date" min={today()} value={expectedOn} onChange={(e) => { setExpectedOn(e.target.value); setDirty(true); }} /></Field>
              <Field label="Notes for the vendor (optional)">
                <textarea rows={3} maxLength={3000} value={notes} onChange={(e) => { setNotes(e.target.value); setDirty(true); }}
                          className="w-full rounded-control border border-rule-strong bg-surface px-3 py-2.5 text-base focus-visible:border-accent" />
              </Field>
            </div>
          </Card>
          <Card title="Total"><p className="num text-xl">{money(total)}</p><p className="text-sm text-muted">{lines.length} {lines.length === 1 ? "item" : "items"}</p></Card>
        </div>
      </div>
    </div>
  );
}

// --- sent and after --------------------------------------------------------------------------------

function View({ po, onChange, reload }: { po: Po; onChange: (p: Po) => void; reload: () => void }) {
  const { can } = useSession();
  const [panel, setPanel] = useState<"close" | "cancel" | null>(null);
  const [billing, setBilling] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const receiving = ["sent", "partly_received"].includes(po.status);

  async function act(path: string, json: object) {
    setBusy(true);
    setError(null);
    try {
      onChange(await api<Po>(`/api/purchase-orders/${po.id}/${path}`, { method: "POST", json }));
      setPanel(null);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1>Purchase order {po.number}</h1>
          <p className="text-muted">
            To <Link href={`/vendors/${po.vendor.id}`} className="underline">{po.vendor.name}</Link>, {day(po.created_at)}{po.expected_on ? `, expected ${day(po.expected_on)}` : ""}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <PoBadge status={po.status} />
          <Link href={`/print/purchase-orders/${po.id}`} target="_blank" className={linkButton}>Print</Link>
        </div>
      </div>
      {po.closed_reason && <div className="mb-4"><Notice tone="warning">{po.status === "cancelled" ? "Cancelled" : "Closed early"}: {po.closed_reason}</Notice></div>}
      {po.warnings && po.warnings.length > 0 && <div className="mb-4 space-y-2">{po.warnings.map((w) => <Notice key={w} tone="warning">{w}</Notice>)}</div>}

      <div className="grid gap-4 shell:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        <div className="space-y-4">
          {receiving && can("goods-receipt")
            ? <ReceiveForm key={po.receipts.length} po={po} onDone={(p) => { onChange(p); const r = p.receipts.at(-1); if (r && can("purchasing")) setBilling(r.id); }} />
            : <Lines po={po} />}

          <Card title="Goods received" flush>
            {!po.receipts.length ? <p className="px-4 py-4 text-muted shell:px-5">Nothing has arrived yet.</p> : (
              <ul>
                {po.receipts.map((r) => <ReceiptRow key={r.id} r={r} po={po} billing={billing === r.id} onBill={() => setBilling(r.id)}
                                                      onCancel={() => setBilling(null)} canBill={can("purchasing")} reload={reload} />)}
              </ul>
            )}
          </Card>

          {panel && <ReasonForm title={panel === "cancel" ? "Cancel this order" : "Close this order early"}
                                hint={panel === "cancel" ? "Nothing was received. The order stays on record." : "What arrived stands. The order stops waiting for the rest."}
                                busy={busy} confirm={panel === "cancel" ? "Cancel the order" : "Close the order"} onCancel={() => setPanel(null)}
                                onSubmit={(reason) => act(panel, { reason })} />}
          <Notice>{error}</Notice>
          {!panel && can("purchasing") && (
            <div className="flex flex-wrap gap-2">
              {["sent"].includes(po.status) && <Button variant="danger" onClick={() => setPanel("cancel")}>Cancel the order</Button>}
              {po.status === "partly_received" && <Button variant="secondary" onClick={() => setPanel("close")}>The vendor won&apos;t send the rest</Button>}
            </div>
          )}
        </div>
        <div className="space-y-4">
          <Card title="Total"><p className="num text-xl">{money(po.total)}</p><p className="text-sm text-muted">Ordered. Bills use what actually arrived, at what it cost.</p></Card>
          <Card title="Vendor">
            <p className="font-medium">{po.vendor.name}</p>
            {po.vendor.contact_person && <p>{po.vendor.contact_person}</p>}
            <p className="text-muted">{po.vendor.address}</p>
            <p className="mt-2 text-sm text-muted">{po.vendor.terms_days ? `Pays within ${po.vendor.terms_days} days` : "Due at once"}</p>
          </Card>
          {po.notes && <Card title="Notes"><p className="whitespace-pre-line">{po.notes}</p></Card>}
        </div>
      </div>
    </>
  );
}

function Lines({ po }: { po: Po }) {
  return (
    <Card title="Items" flush>
      <table className="table-stack w-full">
        <thead><tr className="text-left text-sm text-muted">
          <th className="px-4 py-2 font-normal shell:px-5">Item</th><th className="px-4 py-2 text-right font-normal">Ordered</th>
          <th className="px-4 py-2 text-right font-normal">Received</th><th className="px-4 py-2 text-right font-normal">Cost</th>
          <th className="px-4 py-2 text-right font-normal shell:pr-5">Amount</th>
        </tr></thead>
        <tbody>
          {po.lines.map((l) => (
            <tr key={l.id} className="border-t border-rule">
              <td className="px-4 py-3 shell:px-5 max-sm:px-0"><span className="block font-medium">{l.name}</span><span className="block text-sm text-muted">{l.number}</span></td>
              <td data-label="Ordered" className="num px-4 py-3 text-right max-sm:px-0">{qty(l.qty)}</td>
              <td data-label="Received" className="num px-4 py-3 text-right max-sm:px-0">{qty(l.received)}</td>
              <td data-label="Cost" className="num px-4 py-3 text-right max-sm:px-0">{money(l.unit_cost)}</td>
              <td data-label="Amount" className="num px-4 py-3 text-right shell:pr-5 max-sm:px-0">{money(l.amount)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}

type Row = { qty: string; cost: string; sale: string };

/** Count the delivery in. Each line starts at what is still expected and the agreed cost. */
function ReceiveForm({ po, onDone }: { po: Po; onDone: (p: Po) => void }) {
  const open = po.lines.filter((l) => Number(l.outstanding) > 0);
  const [rows, setRows] = useState<Record<string, Row>>(() => Object.fromEntries(open.map((l) => [l.id, { qty: String(Number(l.outstanding)), cost: String(Number(l.unit_cost)), sale: "" }])));
  const [ref, setRef] = useState("");
  const [on, setOn] = useState(today());
  const [tried, setTried] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const set = (id: string, patch: Partial<Row>) => setRows((r) => ({ ...r, [id]: { ...r[id], ...patch } }));

  const qtyError = (l: PoLine) => {
    const q = Number(rows[l.id].qty);
    return rows[l.id].qty === "" || !Number.isFinite(q) || q < 0 ? "Enter the quantity" : q > Number(l.outstanding) ? `Only ${qty(l.outstanding)} expected` : undefined;
  };
  const costError = (l: PoLine) => (Number(rows[l.id].qty) > 0 && !unitCost.safeParse(rows[l.id].cost).success ? "Enter the cost" : undefined);
  const saleError = (l: PoLine) => (rows[l.id].sale && !/^\d{1,9}(\.\d{1,2})?$/.test(rows[l.id].sale) ? "Enter a price" : undefined);

  /** What the average cost and margin become if this line is received as typed. */
  function preview(l: PoLine) {
    const r = rows[l.id], q = Number(r.qty), c = Number(r.cost);
    if (!(q > 0) || !(c > 0)) return null;
    const have = Number(l.on_hand), avg = have > 0 ? (have * Number(l.avg_cost) + q * c) / (have + q) : c;
    const sale = r.sale ? Number(r.sale) : Number(l.sale_price);
    return { avg, margin: marginPct(sale, avg), sale };
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    setTried(true);
    setError(null);
    if (open.some((l) => qtyError(l) || costError(l) || saleError(l))) { setError("Fix the lines marked in red."); return; }
    if (!open.some((l) => Number(rows[l.id].qty) > 0)) { setError("Enter the quantity that arrived on at least one line."); return; }
    setBusy(true);
    try {
      onDone(await api<Po>(`/api/purchase-orders/${po.id}/receive`, { method: "POST", json: {
        received_on: on, supplier_ref: ref,
        lines: open.map((l) => ({ po_line_id: l.id, qty: rows[l.id].qty, unit_cost: rows[l.id].cost || String(Number(l.unit_cost)), sale_price: rows[l.id].sale || null })),
      } }));
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  return (
    <Card title="Count the goods in" flush>
      <form noValidate onSubmit={submit} onBlurCapture={() => setTried(true)}>
        <ul>
          {open.map((l) => {
            const p = preview(l);
            return (
              <li key={l.id} className="space-y-3 border-t border-rule px-4 py-4 first:border-t-0 shell:px-5">
                <div>
                  <p className="font-medium">{l.name}</p>
                  <p className="text-sm text-muted">{l.number}. Ordered {qty(l.qty)}, received {qty(l.received)}, {qty(l.outstanding)} still expected. {qty(l.on_hand)} {l.unit} in stock now.</p>
                </div>
                <div className="grid gap-4 sm:grid-cols-3">
                  <Field label="Arrived" error={tried ? qtyError(l) : undefined}>
                    <Input type="number" inputMode="decimal" min="0" step="any" value={rows[l.id].qty} onChange={(e) => set(l.id, { qty: e.target.value })} />
                  </Field>
                  <Field label="Cost each (Rs)" error={tried ? costError(l) : undefined} hint={`Ordered at ${money(l.unit_cost)}`}>
                    <Input type="number" inputMode="decimal" min="0" step="any" value={rows[l.id].cost} onChange={(e) => set(l.id, { cost: e.target.value })} />
                  </Field>
                  <Field label="New sale price (optional)" error={tried ? saleError(l) : undefined} hint={`Now ${money(l.sale_price)}`}>
                    <Input type="number" inputMode="decimal" min="0" step="any" value={rows[l.id].sale} onChange={(e) => set(l.id, { sale: e.target.value })} />
                  </Field>
                </div>
                {p && (
                  <p className={`num text-sm ${p.margin !== null && p.margin < 10 ? "text-warning" : "text-muted"}`}>
                    Average cost becomes {money(p.avg)}{p.margin !== null ? `, margin ${p.margin.toFixed(0)}% at the sale price of ${money(p.sale)}` : ", and no sale price is set"}.
                  </p>
                )}
              </li>
            );
          })}
        </ul>
        <div className="grid gap-4 border-t border-rule px-4 py-4 sm:grid-cols-2 shell:px-5">
          <Field label="Vendor's delivery note number (optional)"><Input value={ref} onChange={(e) => setRef(e.target.value)} maxLength={60} /></Field>
          <Field label="Received on"><Input type="date" max={today()} value={on} onChange={(e) => setOn(e.target.value)} /></Field>
          <div className="flex flex-col gap-3 sm:col-span-2">
            <Notice>{error}</Notice>
            <div><Button type="submit" disabled={busy}>{busy ? "Counting in" : "Put the stock in"}</Button></div>
            <p className="text-sm text-muted">Putting the stock in cannot be undone here. It adds to stock and updates the average cost. Count before you confirm.</p>
          </div>
        </div>
      </form>
    </Card>
  );
}

function ReceiptRow({ r, po, billing, onBill, onCancel, canBill, reload }:
  { r: Receipt; po: Po; billing: boolean; onBill: () => void; onCancel: () => void; canBill: boolean; reload: () => void }) {
  const names = Object.fromEntries(po.lines.map((l) => [l.id, l.name]));
  return (
    <li className="space-y-3 border-t border-rule px-4 py-4 first:border-t-0 shell:px-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="font-medium">{r.number}</p>
          <p className="text-sm text-muted">{day(r.received_on)}{r.supplier_ref ? `, delivery note ${r.supplier_ref}` : ""}</p>
        </div>
        <span className="num">{money(r.value)}</span>
      </div>
      <ul className="text-sm text-ink-2">
        {r.lines.map((l) => <li key={l.id}>{qty(l.qty)} x {names[l.po_line_id]} at {money(l.unit_cost)}</li>)}
      </ul>
      {r.bill ? <Link href={`/bills/${r.bill.id}`} className="text-sm underline">Bill {r.bill.number}</Link>
        : billing ? <BillForm receipt={r} po={po} onCancel={onCancel} onDone={reload} />
        : canBill ? <Button variant="secondary" onClick={onBill}>Record the vendor&apos;s bill</Button>
        : <Badge tone="warning">Not billed yet</Badge>}
    </li>
  );
}

/** What we owe for this delivery, as the vendor's invoice states it. */
function BillForm({ receipt, po, onCancel }: { receipt: Receipt; po: Po; onCancel: () => void; onDone: () => void }) {
  const router = useRouter();
  const [errors, setErrors] = useState<FieldErrors>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const live = liveForm(billSchema, errors, setErrors);

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const { data, errors } = parseForm(billSchema, e.currentTarget);
    setErrors(errors ?? {});
    if (!data) return;
    setBusy(true);
    setError(null);
    try {
      const b = await api<{ id: string }>(`/api/goods-receipts/${receipt.id}/bill`, { method: "POST", json: {
        ...data, due_on: data.due_on || null, adjustment: data.adjustment || "0" } });
      router.push(`/bills/${b.id}`);
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }
  return (
    <form noValidate onSubmit={submit} className="grid gap-4 rounded-control bg-paper-2 p-4 sm:grid-cols-2" {...live}>
      <p className="font-medium sm:col-span-2">Bill for {receipt.number}, goods {money(receipt.value)}</p>
      <Field label="Vendor's invoice number" error={errors.vendor_invoice_no} hint="Stops the same invoice being entered twice."><Input name="vendor_invoice_no" maxLength={60} /></Field>
      <Field label="Bill date" error={errors.bill_date}><Input name="bill_date" type="date" max={today()} defaultValue={today()} /></Field>
      <Field label="Due on (optional)" error={errors.due_on} hint={po.vendor.terms_days ? `Blank means ${po.vendor.terms_days} days from the bill date.` : "Blank means due at once."}><Input name="due_on" type="date" /></Field>
      <Field label="Freight or discount (Rs, optional)" error={errors.adjustment} hint="Freight as a plus, a discount as a minus."><Input name="adjustment" inputMode="decimal" placeholder="0" /></Field>
      <div className="sm:col-span-2"><Field label="What the adjustment is for" error={errors.adjustment_reason}><Input name="adjustment_reason" maxLength={200} /></Field></div>
      <div className="flex flex-col gap-3 sm:col-span-2">
        <Notice>{error}</Notice>
        <div className="flex flex-wrap gap-2">
          <Button type="submit" disabled={busy}>{busy ? "Recording" : "Record the bill"}</Button>
          <Button type="button" variant="secondary" onClick={onCancel}>Not now</Button>
        </div>
      </div>
    </form>
  );
}
