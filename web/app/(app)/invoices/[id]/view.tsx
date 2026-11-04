"use client";

import { VisitProgress } from "@/components/job-progress";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { Suspense, useEffect, useState, type ReactNode } from "react";
import { type CreditNote, type Invoice, PayBadge, previewTotals } from "@/components/billing";
import { lineCode, linkButton } from "@/components/estimates";
import { NextStep } from "@/components/next-step";
import { type Payment, type PaymentBody, PaymentForm, PaymentList, RefundForm } from "@/components/payments";
import { RequirePermission } from "@/components/shell";
import { Badge, Button, Card, Checkbox, ErrorState, Field, Input, Notice, SkeletonRows } from "@/components/ui";
import { VehiclePanel } from "@/components/vehicle-panel";
import { api, useApi } from "@/lib/api";
import { money, phone, qty, when } from "@/lib/format";
import { linePrice } from "@/lib/schemas";
import { useSession } from "@/lib/session";

/** How much of a held advance still applies, how much is left to pay, and any excess. */
function advanceSplit(total: number, held: number) {
  const applied = Math.min(Math.max(held, 0), Math.max(total, 0));
  return { applied, balanceDue: Math.max(0, total - held), excess: Math.max(0, held - total) };
}

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

type LiveTotals = ReturnType<typeof previewTotals> & { includeTax: boolean };

function View({ inv, reload }: { inv: Invoice; reload: () => void }) {
  const router = useRouter();
  const { can } = useSession();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [paying, setPaying] = useState(false);
  const [voiding, setVoiding] = useState(false);
  const [returning, setReturning] = useState(false);
  const [refunding, setRefunding] = useState(false);
  const [refundingExcess, setRefundingExcess] = useState(false);
  const [live, setLive] = useState<LiveTotals | null>(null);
  const draft = inv.status === "draft";
  const counter = inv.kind === "counter_sale";
  const previewTotal = live?.total ?? Number(inv.totals.total);
  const { balanceDue, excess } = advanceSplit(previewTotal, Number(inv.totals.advance_held));

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
      {inv.visit && <VisitProgress visitId={inv.visit.id} />}
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1>{counter ? "Counter sale" : "Invoice"} {inv.number}</h1>
          <p className="text-ink-2">{who}</p>
          {inv.visit && <p className="text-muted">For <Link href={`/visits/${inv.visit.id}`} className="underline">{inv.visit.number}</Link>, {inv.kind === "inspection" ? ", the pre-purchase inspection fee" : <>, from <Link href={`/repair-orders/${inv.repair_order_id}`} className="underline">the repair order</Link></>}</p>}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <PayBadge status={inv.pay_status} />
          {inv.status === "issued" && <Link href={`/print/invoices/${inv.id}`} target="_blank" className={linkButton}>Print</Link>}
        </div>
      </div>

      {!paying && !returning && !refunding && !refundingExcess && !voiding && (inv.status === "draft"
        ? (excess > 0
          ? <NextStep who="Administrator" target="act-excess" open={false} label={can("advance-refund") ? "Refund the excess" : undefined} onClick={can("advance-refund") ? () => setRefundingExcess(true) : undefined}>
              The advances ({money(inv.totals.advance_held)}) are more than this invoice ({money(previewTotal)}). Refund the excess ({money(excess)}) before issuing.
            </NextStep>
          : <NextStep who={counter ? "Cashier" : "Cashier or manager"} target={counter ? undefined : "act-issue"} open={false} label={counter ? undefined : "Review and issue"}>{counter ? "Finish the sale, then take the payment." : "Check the prices, then press Issue the invoice. After that the prices are locked."}</NextStep>)
        : inv.status === "issued" && inv.pay_status !== "paid"
          ? <NextStep who="Cashier" label={can("payments-in") ? "Take a payment" : undefined} onClick={() => setPaying(true)}>The invoice is issued. Take the customer&apos;s payment ({money(inv.totals.balance)} still to pay).</NextStep>
          : inv.status === "issued" && inv.kind === "inspection"
            ? <NextStep who="Inspector or front desk" href={`/visits/${inv.visit!.id}`} label="Open the visit">Paid in full. Hand the signed report to the buyer from the visit.</NextStep>
          : inv.status === "issued" && inv.kind === "workshop"
            ? <NextStep who="Guard" href="/gate" label="Cars ready to leave">Paid in full. The car can now leave: release it with the gate pass.</NextStep>
            : inv.status === "issued" && inv.kind === "counter_sale"
              ? <NextStep who="Cashier" href={`/print/invoices/${inv.id}`} label="Print the invoice">Sale complete. Print the A4 invoice for the customer.</NextStep>
              : null)}

      <div className="grid gap-4 shell:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        <div className="space-y-4">
          {draft && !counter ? <WorkshopDraft inv={inv} busy={busy} call={call} onLive={setLive} />
            : <Lines inv={inv} />}
          {draft && counter && <Link href={`/counter-sales/${inv.id}`} className={`${linkButton} w-fit`}>Continue the sale</Link>}

          {inv.credit_release && <Notice tone="warning">Released on credit by {inv.credit_release.by}: {inv.credit_release.reason}</Notice>}
          {paying && (
            <PaymentForm title="Take a payment" hint={`Balance ${money(inv.totals.balance)}.`} suggested={String(Number(inv.totals.balance))} busy={busy}
                         max={Number(inv.totals.balance)}
                         maxError={`That is more than the balance of ${money(inv.totals.balance)}`}
                         onCancel={() => setPaying(false)} onSubmit={async (b: PaymentBody) => {
                           setBusy(true);
                           try {
                             await api(`/api/invoices/${inv.id}/payments`, { method: "POST", json: b });
                             setPaying(false);
                             reload();
                           } finally {
                             setBusy(false);
                           }
                         }} />
          )}
          {returning && <ReturnForm inv={inv} busy={busy} onCancel={() => setReturning(false)}
                                   onSubmit={async (b) => { if (await call("/credit-notes", b)) setReturning(false); }} />}
          {refunding && (
            <RefundForm title="Give money back" hint={`Owed back to the customer: ${money(inv.totals.refundable)}.`} amount={String(Number(inv.totals.refundable))} busy={busy}
                        onCancel={() => setRefunding(false)} onSubmit={async (b) => {
                          setBusy(true);
                          try {
                            await api(`/api/invoices/${inv.id}/refund`, { method: "POST", json: { ...b, reason: undefined } });
                            setRefunding(false);
                            reload();
                          } finally {
                            setBusy(false);
                          }
                        }} />
          )}
          {refundingExcess && (
            <ExcessAdvanceRefund excess={excess} advances={inv.held_advances ?? []} busy={busy}
                                 onCancel={() => setRefundingExcess(false)}
                                 onDone={() => { setRefundingExcess(false); reload(); }}
                                 onBusy={setBusy} onError={setError} />
          )}
          {voiding && <VoidForm busy={busy} onCancel={() => setVoiding(false)} onSubmit={async (reason) => { if (await call("/void", { reason })) router.push("/invoices"); }} />}
          <Notice>{error}</Notice>
          {!paying && !voiding && !returning && !refunding && !refundingExcess && (
            <div className="flex flex-wrap gap-2">
              {inv.status === "issued" && can("credit-notes") && <Button variant="secondary" onClick={() => setReturning(true)}>Correct this invoice</Button>}
              {Number(inv.totals.refundable) > 0 && can("credit-notes") && <Button onClick={() => setRefunding(true)}>Give money back</Button>}
              {inv.status === "issued" && Number(inv.totals.balance) > 0 && can("payments-in") && <Button onClick={() => setPaying(true)}>Take a payment</Button>}
              {draft && !counter && can("invoice-issue") && (
                <Button id="act-issue" disabled={busy || excess > 0} onClick={() => call("/issue", { version: inv.version })}>Issue the invoice</Button>
              )}
              {draft && !counter && inv.kind === "workshop" && <Button variant="secondary" disabled={busy} onClick={() => call("/refresh")}>Refresh from the repair order</Button>}
              {draft && <Button variant="danger" onClick={() => setVoiding(true)}>Void this draft</Button>}
            </div>
          )}
          {draft && !counter && excess > 0 && (
            <p className="text-sm text-muted">Issue is blocked until the excess advance ({money(excess)}) is given back. Use the Total card or Refund the excess above.</p>
          )}
          {draft && !counter && excess <= 0 && (
            <p className="text-sm text-muted">
              Issuing locks the prices and applies the advances held on this visit
              {Number(inv.totals.advance_held) > 0 ? ` (${money(advanceSplit(previewTotal, Number(inv.totals.advance_held)).applied)} of ${money(inv.totals.advance_held)}; balance due ${money(balanceDue)})` : ""}.
              After that, corrections need a credit note.
            </p>
          )}
        </div>

        <div className="space-y-4">
          <Totals inv={inv} live={draft && !counter ? live : null}
                  canRefundExcess={can("advance-refund")}
                  refundingExcess={refundingExcess}
                  onRefundExcess={() => setRefundingExcess(true)} />
          {inv.payments.length > 0 && <PaymentList title="Payments" payments={inv.payments} />}
          {inv.credit_notes.length > 0 && <CreditNotes notes={inv.credit_notes} />}
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
                  {!l.in_quote && <Badge tone="warning">Added after the quotation{l.approval ? `, agreed ${l.approval.method === "in_person" ? "in person" : l.approval.method === "whatsapp" ? "on WhatsApp" : "by phone"}` : ""}</Badge>}</span>
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

function WorkshopDraft({ inv, busy, call, onLive }:
  { inv: Invoice; busy: boolean; call: (path: string, json?: object, method?: string) => Promise<boolean>; onLive: (t: LiveTotals) => void }) {
  const [prices, setPrices] = useState<Record<string, string>>(() => Object.fromEntries(inv.lines.map((l) => [l.id, String(Number(l.unit_price))])));
  const [includeTax, setIncludeTax] = useState(inv.include_tax);
  const [discount, setDiscount] = useState(Number(inv.discount) ? String(Number(inv.discount)) : "");
  const [notes, setNotes] = useState(inv.notes);
  const [dirty, setDirty] = useState(false);
  const bad = inv.lines.filter((l) => !linePrice.safeParse(prices[l.id]).success).map((l) => l.id);
  const preview = previewTotals(inv.lines.map((l) => ({ kind: l.kind, qty: l.qty, unit_price: prices[l.id] })), discount, includeTax, Number(inv.tax_rate));
  useEffect(() => { onLive({ ...preview, includeTax }); }, [preview.labour, preview.parts, preview.discount, preview.tax, preview.total, includeTax, onLive]);

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
                  {!l.in_quote && <Badge tone="warning">Added after the quotation{l.approval ? `, agreed ${l.approval.method === "in_person" ? "in person" : l.approval.method === "whatsapp" ? "on WhatsApp" : "by phone"}` : ""}</Badge>}
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
      {(inv.unused_lines?.length ?? 0) > 0 && (
        <Card title="Not used on this invoice" flush>
          <ul>
            {inv.unused_lines!.map((l, i) => (
              <li key={`${l.description}-${i}`} className="flex flex-wrap items-start justify-between gap-3 border-t border-rule px-4 py-3 first:border-t-0 shell:px-5">
                <div className="min-w-0">
                  <p className="font-medium">{l.description}</p>
                  <p className="flex flex-wrap gap-3 text-sm text-muted">
                    <span>{l.kind === "labour" ? "Labour" : "Part"}</span>
                    <span className="num">Qty {qty(l.qty)}</span>
                    <Badge tone="neutral">{l.why}</Badge>
                  </p>
                </div>
                <span className="num text-sm text-muted">{money(Number(l.qty) * Number(l.unit_price))}</span>
              </li>
            ))}
          </ul>
          <p className="border-t border-rule px-4 py-3 text-sm text-muted shell:px-5">
            These stay off the bill. To change what was used, go back to the repair order (return unused parts or mark lines) and press Refresh from the repair order.
          </p>
        </Card>
      )}
      <Card title="Terms">
        <div className="grid gap-5 sm:grid-cols-2">
          <Field label="Discount (Rs)"><Input type="number" inputMode="decimal" min="0" step="any" value={discount} onChange={(e) => { setDiscount(e.target.value); setDirty(true); }} /></Field>
          <div className="self-end"><Checkbox checked={includeTax} onChange={(e) => { setIncludeTax(e.target.checked); setDirty(true); }} label={`Add ${Number(inv.tax_rate)}% sales tax`} /></div>
          <div className="sm:col-span-2">
            <Field label="Notes on the invoice (optional)">
              <textarea rows={2} maxLength={3000} value={notes} onChange={(e) => { setNotes(e.target.value); setDirty(true); }}
                        className="w-full rounded-control border border-rule-strong bg-surface px-3 py-2.5 text-base focus-visible:border-ink" />
            </Field>
          </div>
        </div>
      </Card>
      {dirty && (
        <div className="flex flex-wrap items-center gap-3">
          <Button variant="success" disabled={busy || bad.length > 0}
                  onClick={async () => { if (await call("", { prices, include_tax: includeTax, discount: discount || "0", notes, version: inv.version }, "PUT")) setDirty(false); }}>
            Save changes
          </Button>
          <span className="text-sm text-muted">Unsaved. The total on the right updates as you type.</span>
        </div>
      )}
    </>
  );
}

function Totals({ inv, live, canRefundExcess, refundingExcess, onRefundExcess }: {
  inv: Invoice; live?: LiveTotals | null; canRefundExcess?: boolean; refundingExcess?: boolean; onRefundExcess?: () => void;
}) {
  const t = live
    ? { labour: live.labour, parts: live.parts, subtotal: live.subtotal, discount: live.discount, tax: live.tax, total: live.total,
        advance_held: Number(inv.totals.advance_held), credited: Number(inv.totals.credited), paid: Number(inv.totals.paid), balance: Number(inv.totals.balance) }
    : { labour: Number(inv.totals.labour), parts: Number(inv.totals.parts), subtotal: Number(inv.totals.subtotal),
        discount: Number(inv.totals.discount), tax: Number(inv.totals.tax), total: Number(inv.totals.total),
        advance_held: Number(inv.totals.advance_held), credited: Number(inv.totals.credited), paid: Number(inv.totals.paid),
        balance: Number(inv.totals.balance) };
  const includeTax = live?.includeTax ?? inv.include_tax;
  const { applied, balanceDue, excess } = advanceSplit(t.total, t.advance_held);
  const row = (label: ReactNode, v: number, strong = false) => (
    <div className={`flex justify-between gap-4 py-1.5 ${strong ? "font-medium" : ""}`}><dt>{label}</dt><dd className="num">{money(v)}</dd></div>
  );
  const rule = <div className="my-1 border-t border-rule" aria-hidden />;
  const draftAdvances = inv.status === "draft" && t.advance_held > 0;
  return (
    <Card title="Total" actions={includeTax ? <Badge tone="neutral">Tax ON</Badge> : undefined}>
      <dl id="act-excess">
        {t.labour > 0 && row("Labour", t.labour)}
        {row("Parts", t.parts)}
        {t.discount > 0 && row("Discount", -t.discount)}
        {includeTax ? (
          <>
            {rule}
            {row("Subtotal", t.subtotal)}
            {row(`Sales tax (${Number(inv.tax_rate)}%)`, t.tax)}
            {rule}
            {row("Total", t.total, true)}
            {draftAdvances && row("Advance applied", -applied)}
            {draftAdvances && rule}
            {draftAdvances && row("Balance due", balanceDue, true)}
            {draftAdvances && excess > 0 && row("Excess advance", excess)}
          </>
        ) : (
          <>
            {rule}
            {row("Total", t.total, true)}
            {draftAdvances && (
              <>
                {row("Advance applied", -applied)}
                {rule}
                {row("Balance due", balanceDue, true)}
                {excess > 0 && row("Excess advance", excess)}
              </>
            )}
          </>
        )}
        {inv.status === "issued" && t.credited > 0 && row("Credited (returns)", -t.credited)}
        {inv.status === "issued" && <>{row("Paid so far", t.paid)}{rule}{t.balance < 0 ? row("Owed back to the customer", -t.balance, true) : row("Balance due", t.balance, true)}</>}
      </dl>
      {inv.status === "draft" && excess > 0 && !refundingExcess && (
        <div className="mt-4 space-y-3 border-t border-rule pt-4">
          <p className="text-sm font-medium text-ink-2">Excess advance action</p>
          <label className="flex min-h-11 cursor-pointer items-center gap-3 rounded-control px-1 py-2 hover:bg-paper-2">
            <input type="radio" name="excess-advance" className="size-5 accent-accent" checked readOnly />
            <span>Refund to customer</span>
          </label>
          {canRefundExcess
            ? <Button type="button" variant="secondary" onClick={onRefundExcess}>Confirm</Button>
            : <p className="text-sm text-muted">An administrator with advance-refund permission must give the excess back before this invoice can be issued.</p>}
        </div>
      )}
    </Card>
  );
}

/** Give back the excess held advance so the invoice can be issued. */
function ExcessAdvanceRefund({ excess, advances, busy, onCancel, onDone, onBusy, onError }:
  { excess: number; advances: Payment[]; busy: boolean; onCancel: () => void; onDone: () => void;
    onBusy: (b: boolean) => void; onError: (m: string | null) => void }) {
  const pick = [...advances].sort((a, b) => Number(b.held ?? b.amount) - Number(a.held ?? a.amount))
    .find((p) => Number(p.held ?? p.amount) > 0);
  const maxOnPick = pick ? Number(pick.held ?? pick.amount) : 0;
  const amount = Math.min(excess, maxOnPick);
  if (!pick || amount <= 0) {
    return (
      <Card title="Refund excess advance">
        <p className="text-sm text-muted">No held advance is left to refund. Reload the page.</p>
        <Button type="button" variant="secondary" className="mt-3" onClick={onCancel}>Close</Button>
      </Card>
    );
  }
  return (
    <RefundForm title="Refund excess advance" needsReason
                hint={`Refund ${money(amount)} of advance ${pick.number} so the held money matches this invoice.${amount < excess ? ` ${money(excess - amount)} will still be excess — confirm again after this.` : ""}`}
                amount={String(amount)} fixedAmount busy={busy} onCancel={onCancel}
                onSubmit={async (b) => {
                  onBusy(true);
                  onError(null);
                  try {
                    await api(`/api/advances/${pick.id}/refund`, { method: "POST", json: b });
                    onDone();
                  } catch (err) {
                    onError((err as Error).message);
                    throw err;
                  } finally {
                    onBusy(false);
                  }
                }} />
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

function CreditNotes({ notes }: { notes: CreditNote[] }) {
  return (
    <Card title="Credit notes" flush>
      <ul>
        {notes.map((n) => (
          <li key={n.id} className="space-y-1 border-t border-rule px-4 py-3 first:border-t-0 shell:px-5">
            <div className="flex justify-between gap-3"><span className="font-medium">{n.number}</span><span className="num">-{money(n.total)}</span></div>
            <p className="text-sm text-muted">{when(n.created_at)}. {n.reason}</p>
            <ul className="text-sm text-ink-2">{n.lines.map((l) => <li key={l.invoice_line_id}>{qty(l.qty)} x {l.description}{l.restocked ? ", back in stock" : ""}</li>)}</ul>
          </li>
        ))}
      </ul>
    </Card>
  );
}

/** Pick what came back, and how much of each line. Parts can go back on the shelf at the cost they left at. */
function ReturnForm({ inv, busy, onSubmit, onCancel }: { inv: Invoice; busy: boolean; onSubmit: (b: object) => void; onCancel: () => void }) {
  const credited: Record<string, number> = {};
  inv.credit_notes.forEach((n) => n.lines.forEach((l) => { credited[l.invoice_line_id] = (credited[l.invoice_line_id] ?? 0) + Number(l.qty); }));
  const left = (id: string, total: string) => Math.max(Number(total) - (credited[id] ?? 0), 0);
  const [qtys, setQtys] = useState<Record<string, string>>({});
  const [restock, setRestock] = useState<Record<string, boolean>>({});
  const [reason, setReason] = useState("");
  const [tried, setTried] = useState(false);
  const picked = inv.lines.filter((l) => Number(qtys[l.id]) > 0);
  const badQty = (id: string, total: string) => Number(qtys[id]) > left(id, total);
  const preview = previewTotals(
    picked.map((l) => ({ kind: l.kind, qty: qtys[l.id], unit_price: l.unit_price })),
    "0",
    inv.include_tax,
    Number(inv.tax_rate),
  );

  return (
    <Card title="Return or correct">
      <form noValidate className="space-y-5" onBlurCapture={() => setTried(true)} onSubmit={(e) => {
        e.preventDefault();
        setTried(true);
        if (!picked.length || reason.trim().length < 3 || picked.some((l) => badQty(l.id, l.qty))) return;
        onSubmit({ reason: reason.trim(), lines: picked.map((l) => ({ invoice_line_id: l.id, qty: qtys[l.id], restock: l.kind === "part" && !!restock[l.id] })) });
      }}>
        <p className="text-sm text-muted">The invoice stays as it was. A credit note reverses the part you choose, and the customer&apos;s balance changes with it.</p>
        <ul className="space-y-4">
          {inv.lines.map((l) => {
            const max = left(l.id, l.qty);
            return (
              <li key={l.id} className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_7rem] sm:items-end">
                <div className="min-w-0">
                  <p className="font-medium">{l.description}</p>
                  <p className="text-sm text-muted">{l.kind === "labour" ? "Labour" : "Part"}, {qty(l.qty)} at {money(l.unit_price)}{max < Number(l.qty) ? `, ${qty(max)} left to credit` : ""}</p>
                  {l.kind === "part" && max > 0 && <Checkbox checked={!!restock[l.id]} onChange={(e) => setRestock((r) => ({ ...r, [l.id]: e.target.checked }))} label="Put it back in stock" />}
                </div>
                <Field label="Credit qty" error={tried && badQty(l.id, l.qty) ? `At most ${qty(max)}` : undefined}>
                  <Input type="number" inputMode="decimal" min="0" max={max} step="any" disabled={max <= 0} value={qtys[l.id] ?? ""} onChange={(e) => setQtys((q) => ({ ...q, [l.id]: e.target.value }))} />
                </Field>
              </li>
            );
          })}
        </ul>
        <Field label="Reason" error={tried && reason.trim().length < 3 ? "Say why" : undefined}><Input value={reason} onChange={(e) => setReason(e.target.value)} maxLength={500} /></Field>
        {picked.length > 0 && (
          <p className="num text-sm font-medium">
            Credit note {money(preview.total)}
            {inv.include_tax ? ` (includes ${money(preview.tax)} tax)` : ""}
          </p>
        )}
        {tried && !picked.length && <p role="alert" className="text-sm text-error">Enter a quantity on at least one line.</p>}
        <div className="flex flex-wrap gap-2">
          <Button type="submit" disabled={busy}>{busy ? "Recording" : "Issue the credit note"}</Button>
          <Button type="button" variant="danger" onClick={onCancel}>Cancel</Button>
        </div>
      </form>
    </Card>
  );
}
