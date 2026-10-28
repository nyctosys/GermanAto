"use client";

import { Badge } from "@/components/ui";

export type RoStatus = "received" | "diagnosis" | "awaiting_approval" | "in_repair" | "testing" | "ready" | "delivered" | "on_hold";
export type RoLine = {
  id: string; kind: "labour" | "part"; labour_code_id: string | null; item_id: string | null; qty: string;
  labour_code?: { code: string; name: string };
  item?: { number: string; name: string; unit: string; sale_price: string; on_hand: string; short: string };
  description: string; unit_price: string; amount: string; in_quote: boolean; state: "pending" | "done" | "not_done";
  technician_id: string | null; technician: string | null; issued_qty: string;
};

export const RO_STAGES: RoStatus[] = ["received", "diagnosis", "awaiting_approval", "in_repair", "testing", "ready", "delivered"];
export const STAGE: Record<RoStatus, string> = {
  received: "Received", diagnosis: "Diagnosis", awaiting_approval: "Awaiting approval", in_repair: "In repair",
  testing: "Testing", ready: "Ready", delivered: "Delivered", on_hold: "On hold",
};

export function RoBadge({ status }: { status: RoStatus }) {
  const tone = status === "ready" || status === "delivered" ? "success" : status === "on_hold" ? "warning" : "accent";
  return <Badge tone={tone}>{STAGE[status]}</Badge>;
}
