"use client";

import { type Payment } from "@/components/payments";
import { Badge } from "@/components/ui";

export type InvoiceLine = {
  id: string; kind: "labour" | "part"; labour_code_id: string | null; item_id: string | null; qty: string;
  labour_code?: { code: string; name: string }; item?: { number: string; name: string; unit: string; sale_price: string; on_hand: string; short: string; reorder_level?: string; avg_cost?: string };
  description: string; unit_price: string; amount: string; in_quote: boolean; repair_order_line_id: string | null;
  approval?: { method: string; reason: string; proof_url: string | null; proof_urls?: string[] } | null;
};
export type PayStatus = "draft" | "void" | "unpaid" | "partly_paid" | "paid";
export type Invoice = {
  id: string; number: string; kind: "workshop" | "counter_sale" | "inspection"; status: "draft" | "issued" | "void"; pay_status: PayStatus;
  version: number; include_tax: boolean; tax_rate: string; discount: string; workshop_ntn: string; notes: string; created_at: string;
  issued_at: string | null; issued_by: string | null; repair_order_id: string | null;
  visit: { id: string; number: string; status: string; car_id: string; customer_id: string; buyer_id: string | null; odometer_in: number | null } | null;
  customer: { id: string; name: string; phone: string; number: string } | null; walk_in_name: string; walk_in_phone: string;
  car: { id: string; plate: string; make: string; model: string; year: number | null; vin: string } | null;
  lines: InvoiceLine[];
  /** Draft workshop only: repair-order lines (or leftover qty) that are not billed. */
  unused_lines?: { description: string; kind: "labour" | "part"; qty: string; unit_price: string; why: string }[];
  /** Draft workshop only: advances still held on the visit (for excess refund). */
  held_advances?: Payment[];
  totals: Record<"labour" | "parts" | "subtotal" | "discount" | "tax" | "total" | "paid" | "balance" | "advance_held" | "credited" | "refundable", string>;
  payments: Payment[];
  credit_notes: CreditNote[];
  credit_release: { by: string; reason: string } | null;
};

export type CreditNote = {
  id: string; number: string; reason: string; created_at: string; total: string; tax: string; discount: string;
  lines: { invoice_line_id: string; description: string; qty: string; unit_price: string; amount: string; restocked: boolean }[];
};

const PAY: Record<PayStatus, [string, "neutral" | "success" | "warning" | "error" | "accent"]> = {
  draft: ["Draft", "warning"], void: ["Voided", "neutral"], unpaid: ["Unpaid", "error"], partly_paid: ["Partly paid", "warning"], paid: ["Paid", "success"],
};
export const PayBadge = ({ status }: { status: PayStatus }) => <Badge tone={PAY[status][1]}>{PAY[status][0]}</Badge>;

/** Same arithmetic as the API (app/pricing.py totals), for a live preview while editing. */
export function previewTotals(
  lines: { kind?: "labour" | "part"; qty: string; unit_price: string }[],
  discount: string,
  includeTax: boolean,
  rate: number,
) {
  const r2 = (n: number) => Math.round(n * 100) / 100;
  const rupees = (n: number) => Math.round(n);
  let labour = 0;
  let parts = 0;
  for (const l of lines) {
    const amt = r2((Number(l.qty) || 0) * (Number(l.unit_price) || 0));
    if (l.kind === "labour") labour = r2(labour + amt);
    else parts = r2(parts + amt);
  }
  const subtotal = r2(labour + parts);
  const disc = Math.min(Number(discount) || 0, subtotal);
  const net = r2(subtotal - disc);
  if (!includeTax) return { labour, parts, subtotal, discount: disc, tax: 0, total: rupees(net) };
  // Tax on the lines before the discount, then round the payable total to whole rupees.
  const total = rupees(net + r2(subtotal * rate / 100));
  return { labour, parts, subtotal, discount: disc, tax: r2(total - net), total };
}
