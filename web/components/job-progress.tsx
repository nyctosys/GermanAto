import type { ReactNode } from "react";
import { useApi } from "@/lib/api";

/** One stroke icon per step of a job. Drawn here so the bar needs no icon library. */
const ICONS: Record<string, ReactNode> = {
  checkin: <path d="M5 16v-4l2-5h10l2 5v4M5 16h14M7 16v2.5M17 16v2.5M7.5 12h9" />,
  jobcard: <path d="M9 4h6v3H9zM7 6H5v14h14V6h-2M9 12h6M9 16h4" />,
  quotation: <path d="M6 3h9l3 3v15H6zM9 11h6M9 15h6" />,
  approved: <path d="M4 12.5l5 5L20 6.5" />,
  repair: <path d="M14.5 5.5a4 4 0 0 0 4.7 5.2L10 20l-3-3 9.2-9.2A4 4 0 0 0 14.5 5.5z" />,
  ready: <path d="M6 21V4M6 5h11l-2 4 2 4H6" />,
  invoice: <path d="M7 3h10v18l-2.5-2-2.5 2-2.5-2L7 21zM10 8h4M10 12h4" />,
  paid: <><path d="M3 7h18v10H3z" /><circle cx="12" cy="12" r="2.5" /></>,
  left: <path d="M4 12h12M12 7l5 5-5 5M20 4v16" />,
  inspect: <><circle cx="11" cy="11" r="6" /><path d="M16 16l4.5 4.5M8.5 11l2 2 3.5-4" /></>,
  report: <path d="M6 3h9l3 3v15H6zM9 9h6M9 13h6M9 17h3" />,
};

export type Step = { key: keyof typeof ICONS; label: string; done: boolean };

/**
 * Where a job has got to: a row of round icons joined by a line. Finished steps are filled,
 * the step being worked on now has a ring, and later steps are grey.
 */
export function JobProgress({ steps, flat = false }: { steps: Step[]; flat?: boolean }) {
  const done = steps.filter((s) => s.done).length;
  const current = steps.findIndex((s) => !s.done);
  return (
    <div className={flat ? "pt-1" : "mb-4 rounded-card bg-surface px-3 py-4 shell:px-5"} role="group" aria-label={`Progress: ${done} of ${steps.length} steps done`}>
      <ol className="flex">
        {steps.map((s, i) => {
          const state = s.done ? "done" : i === current ? "now" : "later";
          return (
            <li key={s.key} className="relative flex min-w-0 flex-1 flex-col items-center gap-1.5" aria-current={state === "now" ? "step" : undefined}>
              {i > 0 && <span aria-hidden="true" className={`absolute right-1/2 top-4 h-0.5 w-full -translate-y-1/2 ${steps[i - 1].done && s.done ? "bg-primary" : steps[i - 1].done ? "bg-primary/40" : "bg-rule-strong"}`} />}
              <span className={`relative z-10 flex size-8 items-center justify-center rounded-full border-2 ${
                state === "done" ? "border-primary bg-primary text-primary-ink" : state === "now" ? "border-primary bg-surface text-primary ring-4 ring-primary/20" : "border-rule-strong bg-paper-3 text-muted"}`}>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{ICONS[s.key]}</svg>
              </span>
              <span className={`hidden text-center text-xs leading-tight sm:block ${state === "later" ? "text-muted" : "font-medium text-ink"}`}>{s.label}</span>
              <span className="sr-only">{state === "done" ? "Done" : state === "now" ? "Now" : "Not yet"}</span>
            </li>
          );
        })}
      </ol>
      {current >= 0 && <p className="mt-3 text-center text-sm sm:hidden"><span className="text-muted">Waiting for:</span> <span className="font-medium">{steps[current].label}</span> <span className="text-muted">(step {current + 1} of {steps.length})</span></p>}
    </div>
  );
}


export type Progress = {
  kind?: string;
  inspections?: { status: string; supersedes_id?: string | null }[];
  status: string;
  job_card: unknown | null;
  quotations: { status: string }[];
  repair_order: { status: string } | null;
  invoice: { status: string; paid?: boolean } | null;
};

/** The steps of a visit, worked out from what exists so far. */
export function stepsOf(v: Progress): Step[] {
  if (v.kind === "pre_purchase") {
    const ins = v.inspections ?? [];
    return [
      { key: "checkin", label: "Checked in", done: true },
      { key: "inspect", label: "Inspecting the car", done: ins.length > 0 },
      { key: "report", label: "Report signed", done: ins.some((i) => i.status === "signed") },
      { key: "invoice", label: "Invoiced", done: !!v.invoice && v.invoice.status !== "draft" },
      { key: "paid", label: "Paid", done: !!v.invoice?.paid || v.status === "closed" },
      { key: "left", label: "Report handed over", done: v.status === "closed" },
    ];
  }
  const q = v.quotations.find((x) => x.status !== "revised");
  return [
    { key: "checkin", label: "Checked in", done: true },
    { key: "jobcard", label: "Job card", done: !!v.job_card },
    { key: "quotation", label: "Quotation sent", done: !!q && q.status !== "draft" },
    { key: "approved", label: "Approved", done: q?.status === "approved" || q?.status === "converted" || !!v.repair_order },
    { key: "repair", label: "Repair", done: !!v.repair_order && v.repair_order.status !== "received" },
    { key: "ready", label: "Ready", done: ["ready", "delivered"].includes(v.repair_order?.status ?? "") },
    { key: "invoice", label: "Invoiced", done: !!v.invoice && v.invoice.status !== "draft" },
    { key: "paid", label: "Paid", done: !!v.invoice?.paid || v.status === "closed" },
    { key: "left", label: "Left", done: v.status === "closed" },
  ];
}

/** The same progress bar as on the visit, for the job card, quotation, repair order, inspection and invoice of that visit.
 *  Quietly shows nothing if the person cannot open visits. */
export function VisitProgress({ visitId }: { visitId: string }) {
  const { data } = useApi<Progress>(`/api/visits/${visitId}`);
  if (!data || data.status === "cancelled") return null;
  return <JobProgress steps={stepsOf(data)} />;
}
