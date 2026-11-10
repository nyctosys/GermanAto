"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useState, type ReactNode } from "react";
import { Segments } from "@/components/search";
import { Button, Card, Field, Input } from "@/components/ui";
import { asAmount, downloadReport, reportSheet, type ReportMeta } from "@/lib/report-xlsx";
import { type Sheet } from "@/lib/xlsx";
import { money } from "@/lib/format";
import { useSession } from "@/lib/session";

const iso = (d: Date) => d.toLocaleDateString("en-CA");

export type Range = { from: string; to: string };

/** The period every report is looked at over. It lives in the address, so a report can be shared as a link. */
export function useRange(): [Range, ReactNode] {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const from = params.get("from") ?? "";
  const to = params.get("to") ?? "";
  const now = new Date();
  const monthStart = new Date(now.getFullYear(), now.getMonth(), 1);
  const range: Range = { from: from || iso(monthStart), to: to || iso(now) };

  // Set from and to in one replace — two useQueryParam sets race and the second wins alone.
  const setRange = (nextFrom: string, nextTo: string) => {
    const p = new URLSearchParams(params);
    if (nextFrom) p.set("from", nextFrom); else p.delete("from");
    if (nextTo) p.set("to", nextTo); else p.delete("to");
    const qs = p.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
  };

  const preset = (key: string) => {
    const lastStart = new Date(now.getFullYear(), now.getMonth() - 1, 1), lastEnd = new Date(now.getFullYear(), now.getMonth(), 0);
    const [f, t] = key === "month" ? [monthStart, now] : key === "last" ? [lastStart, lastEnd] : key === "year" ? [new Date(now.getFullYear(), 0, 1), now] : [null, null];
    if (!f || !t) return;
    setRange(iso(f), iso(t));
  };
  const active = range.from === iso(monthStart) && range.to === iso(now) ? "month"
    : range.from === iso(new Date(now.getFullYear(), now.getMonth() - 1, 1)) && range.to === iso(new Date(now.getFullYear(), now.getMonth(), 0)) ? "last"
    : range.from === iso(new Date(now.getFullYear(), 0, 1)) && range.to === iso(now) ? "year" : "custom";

  const control = (
    <Card title="Period">
      <div className="space-y-4">
        <div className="overflow-x-auto">
          <Segments value={active} onChange={preset} options={[{ value: "month", label: "This month" }, { value: "last", label: "Last month" }, { value: "year", label: "This year" }, { value: "custom", label: "Custom" }]} />
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="From"><Input type="date" value={range.from} max={range.to} onChange={(e) => setRange(e.target.value, range.to)} /></Field>
          <Field label="To"><Input type="date" value={range.to} min={range.from} max={iso(now)} onChange={(e) => setRange(range.from, e.target.value)} /></Field>
        </div>
      </div>
    </Card>
  );
  return [range, control];
}

export const rangeQuery = (r: Range) => `date_from=${r.from}&date_to=${r.to}`;

export const periodLabel = (r: Range) => `${r.from} – ${r.to}`;

/** Real .xlsx workbook. Pass sheets for multi-sheet reports, or headers+rows for a single titled sheet.
 *  With `ledgerRange`, the month journal + general ledger + trial balance are put first (accountant form). */
export function ExportButton({
  name, title, period, headers, rows, sheets, amountCols, ledgerRange,
}: {
  name: string;
  title?: string;
  period?: string;
  headers?: string[];
  rows?: (string | number | null | undefined)[][];
  sheets?: Sheet[];
  /** 0-based column indexes to coerce to numbers (default: last column when headers+rows). */
  amountCols?: number[];
  /** When set, fetch the full month ledger and put it before any summary sheets. */
  ledgerRange?: Range;
}) {
  const { branch } = useSession();
  const [busy, setBusy] = useState(false);
  return (
    <Button variant="secondary" disabled={busy} onClick={() => {
      void (async () => {
        setBusy(true);
        try {
          let extra: Sheet[] = sheets ?? [];
          if (!sheets?.length && headers) {
            const cols = amountCols ?? (headers.length ? [headers.length - 1] : []);
            const body = (rows ?? []).map((r) => r.map((c, i) => (cols.includes(i) ? asAmount(c) : c)));
            const meta: ReportMeta = { title: title ?? name, branch: branch.name, period };
            extra = [reportSheet("Report", meta, headers, body)];
          }
          if (ledgerRange) {
            const { downloadFinanceWorkbook } = await import("@/lib/finance-export");
            await downloadFinanceWorkbook(name, branch.name, ledgerRange.from, ledgerRange.to, extra);
          } else {
            downloadReport(name, extra);
          }
        } finally {
          setBusy(false);
        }
      })();
    }}>{busy ? "Preparing" : "Download for Excel"}</Button>
  );
}

/** One number and what it is, optionally a link to the records behind it. */
export function Stat({ label, value, hint, href, tone }: { label: string; value: ReactNode; hint?: ReactNode; href?: string; tone?: "warning" | "error" | "success" }) {
  const body = (
    <>
      <p className="text-sm text-muted">{label}</p>
      <p className={`num mt-1 text-xl ${tone === "error" ? "text-error" : tone === "warning" ? "text-warning" : tone === "success" ? "text-success" : ""}`}>{value}</p>
      {hint && <p className="mt-0.5 text-sm text-muted">{hint}</p>}
    </>
  );
  return href
    ? <Link href={href} className="row-link block rounded-card bg-surface p-4 pr-10 hover:bg-paper-3/40 active:bg-paper-3 shell:p-5 shell:pr-12">{body}</Link>
    : <div className="rounded-card bg-surface p-4 shell:p-5">{body}</div>;
}

/** Peer numbers as one card split by hairlines (not a row of separate tiles). Put Stats inside. */
export function StatGroup({ children }: { children: ReactNode }) {
  return <div className="grid gap-px overflow-hidden rounded-card bg-rule sm:grid-cols-2 shell:grid-cols-4 [&>*]:rounded-none">{children}</div>;
}

/** A line in a statement: a label, an amount, and an optional link to the records behind it. */
export function Line({ label, value, href, strong, indent }: { label: ReactNode; value: string | number; href?: string; strong?: boolean; indent?: boolean }) {
  const amount = <span className="num">{money(value)}</span>;
  return (
    <div className={`flex items-baseline justify-between gap-4 py-1.5 ${strong ? "border-t border-rule pt-2 font-medium" : ""} ${indent ? "pl-4 text-ink-2" : ""}`}>
      <dt>{href ? <Link href={href} className="underline">{label}</Link> : label}</dt>
      <dd>{amount}</dd>
    </div>
  );
}
