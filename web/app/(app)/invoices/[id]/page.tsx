"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { Suspense, useState, type ReactNode } from "react";
import { type Invoice, PayBadge, previewTotals } from "@/components/billing";
import { lineCode, linkButton } from "@/components/estimates";
import { type PaymentBody, PaymentForm, PaymentList } from "@/components/payments";
import { RequirePermission } from "@/components/shell";
import { Badge, Button, Card, Checkbox, ErrorState, Field, Input, Notice, SkeletonRows } from "@/components/ui";
import { VehiclePanel } from "@/components/vehicle-panel";
import { api, useApi } from "@/lib/api";
import { money, phone, qty, when } from "@/lib/format";
import { linePrice } from "@/lib/schemas";
import { useSession } from "@/lib/session";

export default function InvoicePage() {
  return (
    <RequirePermission permission="invoices">
      <Suspense fallback={<Card flush><SkeletonRows rows={8} /></Card>}>
        <Loader />
      </Suspense>
    </RequirePermission>
  );
}

function Loader() {
  const { id } = useParams<{ id: string }>();
  const inv = useApi<Invoice>(`/api/invoices/${id}`);
  if (inv.error) return <Card flush><ErrorState message={inv.error} onRetry={inv.reload} /></Card>;
  if (!inv.data) return <Card flush><SkeletonRows rows={8} /></Card>;
  return <View key={`${inv.data.id}-${inv.data.version}-${inv.data.payments.length}`} inv={inv.data} reload={inv.reload} />;
}

function View({ inv, reload }: { inv: Invoice; reload: () => void }) {
  const router = useRouter();
  const { can } = useSession();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [paying, setPaying] = useState(false);
  const [voiding, setVoiding] = useState(false);
  const draft = inv.status === "draft";
  const counter = inv.kind === "counter_sale";

  async function call(path: string, json?: object, method = "POST") {
    setBusy(true);
    setError(null);
    try {
      await api(`/api/invoices/${inv.id}${path}`, { method, json });
      reload();
      return true;
    } catch (err) {
      setError((err as Error).message);
      return false;
    } finally {
      setBusy(false);
    }
  }

  const who = inv.customer ? (
    <><Link href={`/customers/${inv.customer.id}`} className="underline">{inv.customer.name}</Link> <span className="num text-muted">{phone(inv.customer.phone)}</span></>
  ) : <>{inv.walk_in_name || "Walk-in customer"} {inv.walk_in_phone && <span className="num text-muted">{phone(inv.walk_in_phone)}</span>}</>;

  return (
    <>
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1>{counter ? "Counter sale" : "Invoice"} {inv.number}</h1>
          <p className="text-ink-2">{who}</p>
          {inv.visit && <p className="text-muted">For <Link href={`/visits/${inv.visit.id}`} className="underline">{inv.visit.number}</Link>, from <Link href={`/repair-orders/${inv.repair_order_id}`} className="underline">the repair order</Link></p>}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <PayBadge status={inv.pay_status} />
          {inv.status === "issued" && <Link href={`/print/invoices/${inv.id}`} target="_blank" className={linkButton}>Print</Link>}
        </div>
      </div>

      <div className="grid gap-4 shell:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        <div className="space-y-4">
          {draft && !counter ? <WorkshopDraft inv={inv} busy={busy} call={call} />
            : <Lines inv={inv} />}
          {draft && counter && <Link href={`/counter-sales/${inv.id}`} className={`${linkButton} w-fit`}>Continue the sale</Link>}

          {inv.credit_release && <Notice tone="warning">Released on credit by {inv.credit_release.by}: {inv.credit_release.reason}</Notice>}
          {paying && (
            <PaymentForm title="Take a payment" hint={`Balance ${money(inv.totals.balance)}.`} suggested={String(Number(inv.totals.balance))} busy={busy}
                         onCancel={() => setPaying(false)} onSubmit={async (b: PaymentBody) => { if (await call("/payments", b)) setPaying(false); }} />
          )}
          {voiding && <VoidForm busy={busy} onCancel={() => setVoiding(false)} onSubmit={async (reason) => { if (await call("/void", { reason })) router.push("/invoices"); }} />}
          <Notice>{error}</Notice>
          {!paying && !voiding && (
            <div className="flex flex-wrap gap-2">
              {inv.status === "issued" && Number(inv.totals.balance) > 0 && can("payments-in") && <Button onClick={() => setPaying(true)}>Take a payment</Button>}
              {draft && !counter && can("invoice-issue") && (
                <Button disabled={busy} onClick={() => call("/issue", { version: inv.version })}>Issue the invoice</Button>
              )}
              {draft && !counter && <Button variant="secondary" disabled={busy} onClick={() => call("/refresh")}>Refresh from the repair order</Button>}
              {draft && <Button variant="ghost" onClick={() => setVoiding(true)}>Void this draft</Button>}
            </div>
          )}
          {draft && !counter && <p className="text-sm text-muted">Issuing locks the prices and applies the advances held on this visit. After that, corrections need a credit note.</p>}
        </div>

        <div className="space-y-4">
          <Totals inv={inv} />
          {inv.payments.length > 0 && <PaymentList title="Payments" payments={inv.payments} />}
          {inv.visit ? <VehiclePanel carId={inv.visit.car_id} ownerId={inv.visit.customer_id} buyerId={inv.visit.buyer_id} />
            : inv.car && <Card title="Car"><p>{[inv.car.year, inv.car.make, inv.car.model].filter(Boolean).join(" ")}</p><p className="text-muted">{inv.car.plate}</p></Card>}
        </div>
      </div>
    </>
  );
}

function Lines({ inv }: { inv: Invoice }) {
  return (
    <Card title="Work and parts" flush>
      <table className="table-stack w-full">
        <thead><tr className="text-left text-sm text-muted">
          <th className="px-4 py-2 font-normal shell:px-5">Item</th><th className="px-4 py-2 text-right font-normal">Qty</th>
          <th className="px-4 py-2 text-right font-normal">Price</th><th className="px-4 py-2 text-right font-normal shell:pr-5">Amount</th>
        </tr></thead>
        <tbody>
          {inv.lines.map((l) => (
            <tr key={l.id} className="border-t border-rule">
              <td className="px-4 py-3 shell:px-5 max-sm:px-0">
                <span className="block font-medium">{l.description}</span>
                <span className="flex flex-wrap gap-3 text-sm text-muted"><span>{l.kind === "labour" ? "Labour" : "Part"}</span><span>{lineCode(l)}</span>
                  {!l.in_quote && <Badge tone="warning">Added after the quotation</Badge>}</span>
              </td>
              <td data-label="Qty" className="num px-4 py-3 text-right max-sm:px-0">{qty(l.qty)}</td>
              <td data-label="Price" className="num px-4 py-3 text-right max-sm:px-0">{money(l.unit_price)}</td>
              <td data-label="Amount" className="num px-4 py-3 text-right shell:pr-5 max-sm:px-0">{money(l.amount)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {inv.notes && <p className="whitespace-pre-line border-t border-rule px-4 py-3 text-ink-2 shell:px-5">{inv.notes}</p>}
      {inv.issued_at && <p className="border-t border-rule px-4 py-3 text-sm text-muted shell:px-5">Issued {when(inv.issued_at)}{inv.issued_by ? ` by ${inv.issued_by}` : ""}</p>}
    </Card>
  );
}

function WorkshopDraft({ inv, busy, call }: { inv: Invoice; busy: boolean; call: (path: string, json?: object, method?: string) => Promise<boolean> }) {
  const [prices, setPrices] = useState<Record<string, string>>(() => Object.fromEntries(inv.lines.map((l) => [l.id, String(Number(l.unit_price))])));
  const [includeTax, setIncludeTax] = useState(inv.include_tax);
  const [discount, setDiscount] = useState(Number(inv.discount) ? String(Number(inv.discount)) : "");
  const [notes, setNotes] = useState(inv.notes);
  const [dirty, setDirty] = useState(false);
  const bad = inv.lines.filter((l) => !linePrice.safeParse(prices[l.id]).success).map((l) => l.id);
  const preview = previewTotals(inv.lines.map((l) => ({ qty: l.qty, unit_price: prices[l.id] })), discount, includeTax, Number(inv.tax_rate));

  return (
    <>
      <Card title="Work and parts" flush>
        <ul>
          {inv.lines.map((l) => (
            <li key={l.id} className="grid gap-3 border-t border-rule px-4 py-3 first:border-t-0 sm:grid-cols-[minmax(0,1fr)_10rem] sm:items-end shell:px-5">
              <div className="min-w-0 self-center">
                <p className="font-medium">{l.description}</p>
                <p className="flex flex-wrap gap-3 text-sm text-muted">
                  <span>{l.kind === "labour" ? "Labour" : "Part"}</span><span>{lineCode(l)}</span><span className="num">Qty {qty(l.qty)}</span>
                  {!l.in_quote && <Badge tone="warning">Added after the quotation</Badge>}
                </p>
              </div>
              <Field label="Price (Rs)" error={bad.includes(l.id) ? "Enter the price" : undefined}>
                <Input type="number" inputMode="decimal" min="0" step="any" value={prices[l.id]}
                       onChange={(e) => { setPrices((p) => ({ ...p, [l.id]: e.target.value })); setDirty(true); }} />
              </Field>
            </li>
          ))}
        </ul>
        <p className="border-t border-rule px-4 py-3 text-sm text-muted shell:px-5">Lines come from the repair order: labour marked done and parts as issued. Prices start at the quotation&apos;s.</p>
      </Card>
      <Card title="Terms">
        <div className="grid gap-5 sm:grid-cols-2">
          <Field label="Discount (Rs)"><Input type="number" inputMode="decimal" min="0" step="any" value={discount} onChange={(e) => { setDiscount(e.target.value); setDirty(true); }} /></Field>
          <div className="self-end"><Checkbox checked={includeTax} onChange={(e) => { setIncludeTax(e.target.checked); setDirty(true); }} label={`Add ${Number(inv.tax_rate)}% sales tax`} /></div>
          <div className="sm:col-span-2">
            <Field label="Notes on the invoice (optional)">
              <textarea rows={2} maxLength={3000} value={notes} onChange={(e) => { setNotes(e.target.value); setDirty(true); }}
                        className="w-full rounded-control border border-rule-strong bg-surface px-3 py-2.5 text-base focus-visible:border-accent" />
            </Field>
          </div>
        </div>
      </Card>
      {dirty && (
        <div className="flex flex-wrap items-center gap-3">
          <Button variant="secondary" disabled={busy || bad.length > 0}
                  onClick={async () => { if (await call("", { prices, include_tax: includeTax, discount: discount || "0", notes, version: inv.version }, "PUT")) setDirty(false); }}>
            Save changes
          </Button>
          <span className="num text-sm text-muted">New total {money(preview.total)}. Save before issuing.</span>
        </div>
      )}
    </>
  );
}

function Totals({ inv }: { inv: Invoice }) {
  const t = inv.totals;
  const row = (label: ReactNode, v: string, strong = false) => (
    <div className={`flex justify-between gap-4 py-1.5 ${strong ? "font-medium" : ""}`}><dt>{label}</dt><dd className="num">{money(v)}</dd></div>
  );
  return (
    <Card title="Total">
      <dl>
        {Number(t.labour) > 0 && row("Labour", t.labour)}
        {row("Parts", t.parts)}
        {Number(t.discount) > 0 && row("Discount", `-${t.discount}`)}
        {inv.include_tax && row(`Sales tax ${Number(inv.tax_rate)}%`, t.tax)}
        <div className="mt-1 border-t border-rule pt-1">{row("Total", t.total, true)}</div>
        {inv.status === "draft" && Number(t.advance_held) > 0 && row("Advance to apply", `-${t.advance_held}`)}
        {inv.status === "issued" && <>{row("Paid", `-${t.paid}`)}{row("Balance", t.balance, true)}</>}
      </dl>
    </Card>
  );
}

function VoidForm({ busy, onSubmit, onCancel }: { busy: boolean; onSubmit: (reason: string) => void; onCancel: () => void }) {
  const [reason, setReason] = useState("");
  return (
    <Card title="Void this draft">
      <form onSubmit={(e) => { e.preventDefault(); onSubmit(reason); }} className="space-y-4">
        <Field label="Reason" hint="The number stays on record, marked void."><Input value={reason} onChange={(e) => setReason(e.target.value)} required minLength={3} autoFocus /></Field>
        <div className="flex flex-wrap gap-2">
          <Button type="submit" variant="danger" disabled={busy}>Void</Button>
          <Button type="button" variant="secondary" onClick={onCancel}>Keep it</Button>
        </div>
      </form>
    </Card>
  );
}
