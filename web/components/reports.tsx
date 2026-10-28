"use client";

import Link from "next/link";
import { type ReactNode } from "react";
import { Segments, useQueryParam } from "@/components/search";
import { Button, Card, Field, Input } from "@/components/ui";
import { downloadCsv } from "@/lib/csv";
import { money } from "@/lib/format";

const iso = (d: Date) => d.toLocaleDateString("en-CA");

export type Range = { from: string; to: string };

/** The period every report is looked at over. It lives in the address, so a report can be shared as a link. */
export function useRange(): [Range, ReactNode] {
  const [from, setFrom] = useQueryParam("from");
  const [to, setTo] = useQueryParam("to");
  const now = new Date();
  const monthStart = new Date(now.getFullYear(), now.getMonth(), 1);
  const range: Range = { from: from || iso(monthStart), to: to || iso(now) };

  const preset = (key: string) => {
    const lastStart = new Date(now.getFullYear(), now.getMonth() - 1, 1), lastEnd = new Date(now.getFullYear(), now.getMonth(), 0);
    const [f, t] = key === "month" ? [monthStart, now] : key === "last" ? [lastStart, lastEnd] : key === "year" ? [new Date(now.getFullYear(), 0, 1), now] : [null, null];
    if (!f || !t) return;
    setFrom(iso(f));
    setTo(iso(t));
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
          <Field label="From"><Input type="date" value={range.from} max={range.to} onChange={(e) => setFrom(e.target.value)} /></Field>
          <Field label="To"><Input type="date" value={range.to} min={range.from} max={iso(now)} onChange={(e) => setTo(e.target.value)} /></Field>
        </div>
      </div>
    </Card>
  );
  return [range, control];
}

export const rangeQuery = (r: Range) => `date_from=${r.from}&date_to=${r.to}`;

export function ExportButton({ name, headers, rows }: { name: string; headers: string[]; rows: (string | number | null | undefined)[][] }) {
  return <Button variant="secondary" onClick={() => downloadCsv(`${name}.csv`, headers, rows)}>Download for Excel</Button>;
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
