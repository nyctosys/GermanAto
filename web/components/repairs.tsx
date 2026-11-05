"use client";

import { Badge } from "@/components/ui";

export type RoStatus = "received" | "in_repair" | "testing" | "ready" | "delivered" | "on_hold";
export type RoLine = {
  id: string; kind: "labour" | "part"; labour_code_id: string | null; item_id: string | null; qty: string;
  labour_code?: { code: string; name: string };
  item?: { number: string; name: string; unit: string; sale_price: string; on_hand: string; short: string;
    reorder_level?: string; avg_cost?: string; low_stock?: boolean };
  description: string; unit_price: string; amount: string; in_quote: boolean; state: "pending" | "done" | "not_done";
  technician_id: string | null; technician: string | null; issued_qty: string;
  approval?: { method: string; reason: string; proof_url: string | null; proof_urls?: string[] } | null;
};

export const RO_STAGES: RoStatus[] = ["received", "in_repair", "testing", "ready", "delivered"];
export const STAGE: Record<string, string> = {
  received: "Received", in_repair: "In repair", testing: "Testing",
  ready: "Ready", delivered: "Delivered", on_hold: "On hold",
  // Kept for activity history written before stages were simplified.
  diagnosis: "Diagnosis", awaiting_approval: "Awaiting approval",
};

/** Effective work stage (on hold resumes to held_from). */
export function workStage(status: RoStatus, heldFrom: RoStatus | null): RoStatus {
  return status === "on_hold" ? (heldFrom ?? "received") : status;
}

/** What the Work and parts card allows at each stage. */
export function stageActions(stage: RoStatus) {
  return {
    markLabour: stage === "in_repair" || stage === "testing",
    markPart: stage === "in_repair" || stage === "testing",
    issue: stage === "received" || stage === "in_repair" || stage === "testing",
    returnStock: stage === "received" || stage === "in_repair" || stage === "testing",
    assignTech: stage === "received" || stage === "in_repair" || stage === "testing",
    extraWork: stage === "in_repair" || stage === "testing",
    removeExtra: stage === "in_repair" || stage === "testing",
  };
}

export function RoBadge({ status }: { status: RoStatus }) {
  const tone = status === "ready" || status === "delivered" ? "success" : status === "on_hold" ? "warning" : "accent";
  return <Badge tone={tone}>{STAGE[status]}</Badge>;
}
