"use client";

import { NextStep } from "@/components/next-step";
import { useParams, useRouter } from "next/navigation";
import { Suspense, useState } from "react";
import { type Invoice, previewTotals } from "@/components/billing";
import { type Customer, CustomerPicker } from "@/components/customers";
import { CatalogPicker } from "@/components/estimates";
import { PartsToOrder, type StockNeedLine } from "@/components/parts-to-order";
import { newRow, type PaymentRow, splitBodies, SplitPayments, splitValid } from "@/components/payments";
import { Segments } from "@/components/search";
import { RequirePermission } from "@/components/shell";
import { Button, Card, Checkbox, ErrorState, Field, Input, Notice, PageHeader, QtyInput, Select, SkeletonRows } from "@/components/ui";
import { WorkshopNtnPick, ntnOptionsFrom } from "@/components/workshop-ntn";
import { api, useApi } from "@/lib/api";
import { money, qty } from "@/lib/format";
import { linePrice, lineQtyFor } from "@/lib/schemas";
import { useSession } from "@/lib/session";

type Line = { key: string; item_id: string; name: string; code: string; unit: string; on_hand: string; qty: string; unit_price: string; avg_cost?: string; reorder_level?: string };
type CustomerWithCars = Customer & { cars: { id: string; plate: string; make: string; model: string; until: string | null }[] };

export default function CounterSalePage() {
  return (
    <RequirePermission permission="invoices">
      <PageHeader title="Counter sale" description="Parts sold over the counter, paid on the spot. Work on a car goes through a visit instead." />
      <Suspense fallback={<Card flush><SkeletonRows rows={6} /></Card>}>
        <Loader />
      </Suspense>
    </RequirePermission>
  );
}

function Loader() {
  const { id } = useParams<{ id: string }>();
  const fresh = id === "new";
  const inv = useApi<Invoice>(fresh ? null : `/api/invoices/${id}`);
  const branch = useApi<{ tax_rate: string; ntn: string; ntn_options: string }>("/api/branch");
  if (inv.error || branch.error) return <Card flush><ErrorState message={(inv.error ?? branch.error)!} onRetry={() => { inv.reload(); branch.reload(); }} /></Card>;
  if ((!fresh && !inv.data) || !branch.data) return <Card flush><SkeletonRows rows={6} /></Card>;
  return <Editor initial={inv.data} rate={Number(inv.data?.tax_rate ?? branch.data.tax_rate)} branch={branch.data} />;
}

function Editor({ initial, rate, branch }: { initial: Invoice | null; rate: number; branch: { ntn: string; ntn_options: string } }) {
  const router = useRouter();
  const { can } = useSession();
  const ntnOptions = ntnOptionsFrom(branch);
  const [workshopNtn, setWorkshopNtn] = useState(initial?.workshop_ntn || branch.ntn || ntnOptions[0] || "");
  const [who, setWho] = useState<"customer" | "walk_in">(initial?.customer || !initial ? (initial?.customer ? "customer" : "walk_in") : "walk_in");
  const [customer, setCustomer] = useState<Customer | null>(initial?.customer as Customer | null ?? null);
  const [carId, setCarId] = useState(initial?.car?.id ?? "");
  const [walkName, setWalkName] = useState(initial?.walk_in_name ?? "");
  const [walkPhone, setWalkPhone] = useState(initial?.walk_in_phone ?? "");
  const [lines, setLines] = useState<Line[]>(() => (initial?.lines ?? []).map((l) => ({
    key: l.id, item_id: l.item_id!, name: l.description, code: l.item!.number, unit: l.item!.unit, on_hand: l.item!.on_hand,
    qty: String(Number(l.qty)), unit_price: String(Number(l.unit_price)),
    avg_cost: l.item!.avg_cost, reorder_level: l.item!.reorder_level,
  })));
  const [includeTax, setIncludeTax] = useState(initial?.include_tax ?? true);
  const [discount, setDiscount] = useState(initial && Number(initial.discount) ? String(Number(initial.discount)) : "");
  const [rows, setRows] = useState<PaymentRow[]>([newRow()]);
  const [tried, setTried] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const cars = useApi<CustomerWithCars>(customer ? `/api/customers/${customer.id}` : null);

  const t = previewTotals(lines, discount, includeTax, rate);
  // A single payment left blank means the whole total; the common case is one tap.
  const payRows = rows.length === 1 && !rows[0].amount.trim() ? [{ ...rows[0], amount: String(t.total) }] : rows;
  const lineBad = (l: Line) => !lineQtyFor(l.unit).safeParse(l.qty).success || !linePrice.safeParse(l.unit_price).success;
  const edit = (key: string, patch: Partial<Line>) => setLines((ls) => ls.map((l) => (l.key === key ? { ...l, ...patch } : l)));
  const stockLines: StockNeedLine[] = lines.map((l) => ({
    id: l.key, kind: "part", item_id: l.item_id, qty: l.qty, description: l.name,
    item: {
      number: l.code, name: l.name, unit: l.unit, on_hand: l.on_hand,
      short: String(Math.max(Number(l.qty) - Number(l.on_hand), 0)),
      avg_cost: l.avg_cost, reorder_level: l.reorder_level,
    },
  }));

  async function save(issue: boolean) {
    setTried(true);
    setError(null);
    if (!lines.length) { setError("Add at least one part."); return; }
    if (lines.some(lineBad)) { setError("Every part needs a quantity and a price."); return; }
    if (who === "customer" && !customer) { setError("Pick the customer, or switch to walk-in."); return; }
    if (issue && !splitValid(payRows, t.total)) { setError(`The payments must add up to ${money(t.total)}, each with proof or a reason.`); return; }
    setBusy(true);
    try {
      const body = {
        customer_id: who === "customer" ? customer!.id : null, car_id: who === "customer" && carId ? carId : null,
        walk_in_name: who === "walk_in" ? walkName : "", walk_in_phone: who === "walk_in" ? walkPhone : "",
        include_tax: includeTax, discount: discount || "0", notes: "",
        lines: lines.map((l) => ({ kind: "part", item_id: l.item_id, qty: l.qty, unit_price: l.unit_price })),
      };
      const saved = initial
        ? await api<Invoice>(`/api/counter-sales/${initial.id}`, { method: "PUT", json: { ...body, version: initial.version } })
        : await api<Invoice>("/api/counter-sales", { method: "POST", json: body });
      if (issue) await api(`/api/invoices/${saved.id}/issue`, { method: "POST", json: { version: saved.version, payments: splitBodies(payRows), workshop_ntn: workshopNtn } });
      router.push(issue ? `/invoices/${saved.id}` : `/counter-sales/${saved.id}`);
      if (!issue) setBusy(false);
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  return (
    <>
    <NextStep who="Cashier" target={lines.length ? "act-finish-sale" : "act-add-work"} open={false} label={lines.length ? "Take the payment" : "Add a part"}>{lines.length ? "Check the parts and the total, then take the payment to finish the sale." : "Add the parts the customer is buying, then take the payment."}</NextStep>
    <div className="grid gap-4 shell:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)]" onBlurCapture={() => setTried(true)}>
      <div className="space-y-4">
        <Card title="Customer">
          <div className="space-y-4">
            <Segments value={who} onChange={(v) => setWho(v as typeof who)} options={[{ value: "walk_in", label: "Walk-in" }, { value: "customer", label: "Customer on file" }]} />
            {who === "customer" ? (
              <>
                <CustomerPicker value={customer} onChange={(c) => { setCustomer(c); setCarId(""); }} />
                {customer && cars.data && cars.data.cars.some((c) => !c.until) && (
                  <Field label="For one of their cars? (optional)" hint="The sale then shows in that car's history.">
                    <Select value={carId} onChange={(e) => setCarId(e.target.value)}>
                      <option value="">No car</option>
                      {cars.data.cars.filter((c) => !c.until).map((c) => <option key={c.id} value={c.id}>{[c.plate, c.make, c.model].filter(Boolean).join(" ")}</option>)}
                    </Select>
                  </Field>
                )}
              </>
            ) : (
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Name (optional)"><Input value={walkName} onChange={(e) => setWalkName(e.target.value)} maxLength={120} /></Field>
                <Field label="Mobile (optional)" hint="For a WhatsApp receipt later."><Input value={walkPhone} onChange={(e) => setWalkPhone(e.target.value)} inputMode="tel" placeholder="+92 300 1234567" /></Field>
              </div>
            )}
          </div>
        </Card>

        <Card title="Parts" flush>
          <div className="border-b border-rule p-4 shell:px-5">
            <CatalogPicker partsOnly onPick={(p) => {
              if (p.kind !== "part") { setError("A counter sale sells parts only. Labour goes through a visit."); return; }
              setError(null);
              setLines((ls) => [...ls, { key: crypto.randomUUID(), item_id: p.id, name: p.name, code: p.code, unit: p.unit!, on_hand: p.on_hand!,
                                         qty: "1", unit_price: Number(p.sale_price) ? String(Number(p.sale_price)) : "" }]);
            }} />
          </div>
          <ul>
            {lines.map((l) => (
              <li key={l.key} className="grid gap-3 border-t border-rule px-4 py-3 first:border-t-0 sm:grid-cols-[minmax(0,1fr)_6rem_9rem_auto] sm:items-end shell:px-5">
                <div className="min-w-0 self-center">
                  <p className="font-medium">{l.name}</p>
                  <p className="flex flex-wrap gap-3 text-sm text-muted"><span>{l.code}</span>
                    <span className={Number(l.qty) > Number(l.on_hand) ? "text-error" : ""}>{qty(l.on_hand)} {l.unit} in stock</span></p>
                </div>
                <Field label="Qty" error={tried && !lineQtyFor(l.unit).safeParse(l.qty).success ? "Enter a whole number" : undefined}>
                  <QtyInput unit={l.unit} value={l.qty} onChange={(qty) => edit(l.key, { qty })} />
                </Field>
                <Field label="Price (Rs)" error={tried && !linePrice.safeParse(l.unit_price).success ? "Enter the price" : undefined}>
                  <Input type="number" inputMode="decimal" min="0" step="any" value={l.unit_price} onChange={(e) => edit(l.key, { unit_price: e.target.value })} />
                </Field>
                <Button variant="danger" onClick={() => setLines((ls) => ls.filter((x) => x.key !== l.key))}>Remove</Button>
              </li>
            ))}
          </ul>
          {!lines.length && <p className="px-4 py-6 text-muted shell:px-5">Scan a barcode or search for the part above.</p>}
        </Card>
        <PartsToOrder
          mode="counter"
          lines={stockLines}
          hint="The customer wants more than you have in stock. Save a draft, then send it from Purchase orders."
        />

        <div className="shell:hidden">        <Card title="Total">
          <dl>
            <div className="flex justify-between py-1.5"><dt>Parts</dt><dd className="num">{money(t.subtotal)}</dd></div>
            <div className="flex items-center justify-between gap-4 py-1.5">
              <dt><label htmlFor="cs-discount-m">Discount (Rs)</label></dt>
              <dd className="w-32"><Input id="cs-discount-m" type="number" inputMode="decimal" min="0" step="any" value={discount} onChange={(e) => setDiscount(e.target.value)} /></dd>
            </div>
            <Checkbox checked={includeTax} onChange={(e) => setIncludeTax(e.target.checked)} label={`Add ${rate}% sales tax`} />
            {includeTax && <div className="flex justify-between py-1.5"><dt>Sales tax</dt><dd className="num">{money(t.tax)}</dd></div>}
            <div className="mt-1 flex justify-between border-t border-rule py-1.5 pt-2 font-medium"><dt>Total</dt><dd className="num">{money(t.total)}</dd></div>
          </dl>
        </Card></div>
        {can("invoice-issue") && can("payments-in") && lines.length > 0 && (
          <Card title="Payment">
            <SplitPayments total={t.total} rows={payRows} setRows={(fn) => setRows(() => fn(payRows))} tried={tried} />
            {ntnOptions.length > 0 && <div className="mt-4"><WorkshopNtnPick options={ntnOptions} value={workshopNtn} onChange={setWorkshopNtn} /></div>}
          </Card>
        )}
        <Notice>{error}</Notice>
        <div className="flex flex-wrap gap-2">
          {can("invoice-issue") && can("payments-in") && <Button id="act-finish-sale" variant="success" disabled={busy || !lines.length} onClick={() => save(true)}>{busy ? "Working" : `Take ${money(t.total)} and finish`}</Button>}
          <Button variant="success" disabled={busy || !lines.length} onClick={() => save(false)}>Save as draft</Button>
        </div>
      </div>

      <div className="space-y-4">
<div className="hidden shell:block">        <Card title="Total">
          <dl>
            <div className="flex justify-between py-1.5"><dt>Parts</dt><dd className="num">{money(t.subtotal)}</dd></div>
            <div className="flex items-center justify-between gap-4 py-1.5">
              <dt><label htmlFor="cs-discount">Discount (Rs)</label></dt>
              <dd className="w-32"><Input id="cs-discount" type="number" inputMode="decimal" min="0" step="any" value={discount} onChange={(e) => setDiscount(e.target.value)} /></dd>
            </div>
            <Checkbox checked={includeTax} onChange={(e) => setIncludeTax(e.target.checked)} label={`Add ${rate}% sales tax`} />
            {includeTax && <div className="flex justify-between py-1.5"><dt>Sales tax</dt><dd className="num">{money(t.tax)}</dd></div>}
            <div className="mt-1 flex justify-between border-t border-rule py-1.5 pt-2 font-medium"><dt>Total</dt><dd className="num">{money(t.total)}</dd></div>
          </dl>
        </Card></div>
        <p className="text-sm text-muted">Finishing takes the parts out of stock and records the payment in one step. A return later is made with a credit note.</p>
      </div>
    </div>
    </>
  );
}
