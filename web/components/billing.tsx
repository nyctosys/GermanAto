"use client";

import { type Payment } from "@/components/payments";
import { Badge } from "@/components/ui";

export type InvoiceLine = {
  id: string; kind: "labour" | "part"; labour_code_id: string | null; item_id: string | null; qty: string;
  labour_code?: { code: string; name: string }; item?: { number: string; name: string; unit: string; sale_price: string; on_hand: string; short: string };
  description: string; unit_price: string; amount: string; in_quote: boolean; repair_order_line_id: string | null;
};
export type PayStatus = "draft" | "void" | "unpaid" | "partly_paid" | "paid";
export type Invoice = {
  id: string; number: string; kind: "workshop" | "counter_sale"; status: "draft" | "issued" | "void"; pay_status: PayStatus;
  version: number; include_tax: boolean; tax_rate: string; discount: string; notes: string; created_at: string;
  issued_at: string | null; issued_by: string | null; repair_order_id: string | null;
  visit: { id: string; number: string; status: string; car_id: string; customer_id: string; buyer_id: string | null; odometer_in: number | null } | null;
  customer: { id: string; name: string; phone: string; number: string } | null; walk_in_name: string; walk_in_phone: string;
  car: { id: string; plate: string; make: string; model: string; year: number | null; vin: string } | null;
  lines: InvoiceLine[];
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

/** Same arithmetic as the API (app/routers/estimates.py totals), for a live preview while editing. */
export function previewTotals(lines: { qty: string; unit_price: string }[], discount: string, includeTax: boolean, rate: number) {
  const r2 = (n: number) => Math.round(n * 100) / 100;
  const subtotal = lines.reduce((s, l) => s + r2((Number(l.qty) || 0) * (Number(l.unit_price) || 0)), 0);
  const disc = Math.min(Number(discount) || 0, subtotal);
  const tax = includeTax ? r2((subtotal - disc) * rate / 100) : 0;
  return { subtotal, discount: disc, tax, total: r2(subtotal - disc + tax) };
}
