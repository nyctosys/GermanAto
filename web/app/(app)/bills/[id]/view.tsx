"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { Suspense, useState } from "react";
import { type Payment, type PaymentBody, PaymentForm, PaymentList } from "@/components/payments";
import { BillBadge, ReasonForm } from "@/components/purchasing";
import { PURCHASING, RequirePermission } from "@/components/shell";
import { Badge, Button, Card, ErrorState, Notice, SkeletonRows } from "@/components/ui";
import { api, useApi } from "@/lib/api";
import { day, money, qty } from "@/lib/format";
import { useSession } from "@/lib/session";

type VPayment = { id: string; number: string; status: string; account: string; reference: string; amount: string; paid_at: string;
  paid_by: string | null; note: string; void_reason: string; proof_url: string | null; no_proof_reason: string };
type Bill = {
  id: string; number: string; status: "posted" | "void"; pay_state: string; version: number; vendor_invoice_no: string; bill_date: string;
  due_on: string; overdue: boolean; adjustment_reason: string; void_reason: string; created_at: string;
  goods_value: string; adjustment: string; total: string; paid: string; balance: string;
  vendor: { id: string; name: string }; receipt: { id: string; number: string; received_on: string; supplier_ref: string };
  purchase_order: { id: string; number: string };
  lines: { name: string; number: string; qty: string; unit_cost: string; amount: string }[];
  payments: VPayment[];
};

export default function BillPage() {
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
  const b = useApi<Bill>(`/api/bills/${id}`);
  const [fresh, setFresh] = useState<Bill | null>(null);
  if (b.error) return <Card flush><ErrorState message={b.error} onRetry={b.reload} /></Card>;
  if (!b.data) return <Card flush><SkeletonRows rows={8} /></Card>;
  return <View bill={fresh && fresh.id === b.data.id ? fresh : b.data} onChange={setFresh} />;
}

function View({ bill, onChange }: { bill: Bill; onChange: (b: Bill) => void }) {
  const { can } = useSession();
  const [panel, setPanel] = useState<"pay" | "void" | null>(null);
  const [voiding, setVoiding] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const live = bill.status === "posted";
  const owing = live && Number(bill.balance) > 0;

  async function call(path: string, json: object) {
    setBusy(true);
    setError(null);
    try {
      onChange(await api<Bill>(path, { method: "POST", json }));
      return true;
    } catch (err) {
      setError((err as Error).message);
      return false;
    } finally {
      setBusy(false);
    }
  }

  const payments: Payment[] = bill.payments.map((p) => ({ ...p, received_at: p.paid_at, received_by: p.paid_by }));
  const row = (label: string, v: string, strong = false) => (
    <div className={`flex justify-between gap-4 py-1.5 ${strong ? "font-medium" : ""}`}><dt>{label}</dt><dd className="num">{money(v)}</dd></div>
  );
  return (
    <>
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1>Bill {bill.number}</h1>
          <p className="text-muted">
            From <Link href={`/vendors/${bill.vendor.id}`} className="underline">{bill.vendor.name}</Link>
            {bill.vendor_invoice_no ? `, their invoice ${bill.vendor_invoice_no}` : ""}
          </p>
          <p className="text-muted">
            For <Link href={`/purchase-orders/${bill.purchase_order.id}`} className="underline">{bill.purchase_order.number}</Link>, delivery {bill.receipt.number}
            {bill.receipt.supplier_ref ? ` (note ${bill.receipt.supplier_ref})` : ""}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <BillBadge state={bill.pay_state} />
          {bill.overdue && <Badge tone="error">Overdue</Badge>}
        </div>
      </div>
      {bill.status === "void" && <div className="mb-4"><Notice tone="warning">Voided: {bill.void_reason}. The delivery can be billed again from its purchase order.</Notice></div>}

      <div className="grid gap-4 shell:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        <div className="space-y-4">
          <Card title="What was delivered" flush>
            <table className="table-stack w-full">
              <thead><tr className="text-left text-sm text-muted">
                <th className="px-4 py-2 font-normal shell:px-5">Item</th><th className="px-4 py-2 text-right font-normal">Qty</th>
                <th className="px-4 py-2 text-right font-normal">Cost</th><th className="px-4 py-2 text-right font-normal shell:pr-5">Amount</th>
              </tr></thead>
              <tbody>
                {bill.lines.map((l) => (
                  <tr key={l.number} className="border-t border-rule">
                    <td className="px-4 py-3 shell:px-5 max-sm:px-0"><span className="block font-medium">{l.name}</span><span className="block text-sm text-muted">{l.number}</span></td>
                    <td data-label="Qty" className="num px-4 py-3 text-right max-sm:px-0">{qty(l.qty)}</td>
                    <td data-label="Cost" className="num px-4 py-3 text-right max-sm:px-0">{money(l.unit_cost)}</td>
                    <td data-label="Amount" className="num px-4 py-3 text-right shell:pr-5 max-sm:px-0">{money(l.amount)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="border-t border-rule px-4 py-3 text-sm text-muted shell:px-5">Billed {day(bill.bill_date)}, due {day(bill.due_on)}.</p>
          </Card>

          {panel === "pay" && (
            <PaymentForm title="Pay this vendor" hint={`Still owed: ${money(bill.balance)}. A part payment is fine.`} suggested={String(Number(bill.balance))} busy={busy}
                         onCancel={() => setPanel(null)} onSubmit={async (b: PaymentBody) => { if (await call(`/api/bills/${bill.id}/payments`, b)) setPanel(null); }} />
          )}
          {panel === "void" && (
            <ReasonForm title="Void this bill" hint="Only possible while nothing is paid on it. The number stays on record." confirm="Void the bill" busy={busy}
                        onCancel={() => setPanel(null)} onSubmit={async (reason) => { if (await call(`/api/bills/${bill.id}/void`, { reason })) setPanel(null); }} />
          )}
          {voiding && (
            <ReasonForm title="Void this payment" hint="It stays on record, struck through, and the bill owes that money again." confirm="Void the payment" busy={busy}
                        onCancel={() => setVoiding(null)} onSubmit={async (reason) => { if (await call(`/api/vendor-payments/${voiding}/void`, { reason })) setVoiding(null); }} />
          )}
          <Notice>{error}</Notice>
          {!panel && !voiding && live && (
            <div className="flex flex-wrap gap-2">
              {owing && can("payments-out") && <Button onClick={() => setPanel("pay")}>Pay this bill</Button>}
              {can("purchasing") && Number(bill.paid) === 0 && <Button variant="danger" onClick={() => setPanel("void")}>Void the bill</Button>}
            </div>
          )}
        </div>

        <div className="space-y-4">
          <Card title="Total">
            <dl>
              {row("Goods", bill.goods_value)}
              {Number(bill.adjustment) !== 0 && row(bill.adjustment_reason || "Adjustment", bill.adjustment)}
              <div className="mt-1 border-t border-rule pt-1">{row("Bill total", bill.total, true)}</div>
              {live && <>{row("Paid", `-${bill.paid}`)}{row("Still owed", bill.balance, true)}</>}
            </dl>
          </Card>
          {payments.length > 0 && (
            <PaymentList title="Payments" payments={payments}
                         action={(p) => (p.status === "posted" && live && can("payments-out") ? <Button variant="danger" onClick={() => setVoiding(p.id)}>Void</Button> : null)} />
          )}
        </div>
      </div>
    </>
  );
}
