"use client";

import Image from "next/image";
import { type ReactNode } from "react";
import { phone } from "@/lib/format";

/** Shared pieces of the printed documents (A4, black on white). */
export function PrintBar({ children }: { children?: ReactNode }) {
  return (
    <div className="no-print mb-4 flex flex-wrap items-center gap-3">
      <button onClick={() => window.print()} className="min-h-11 rounded-control bg-accent px-4 font-medium text-accent-ink">Print or save as PDF</button>
      {children}
    </div>
  );
}

export function Letterhead({ branch, title, right }: { branch: { name: string; address: string; phone: string }; title: string; right: ReactNode }) {
  return (
    <header className="mb-4 flex items-start justify-between gap-4 border-b-2 border-ink pb-3">
      <div className="flex items-center gap-3">
        <Image src="/logo.png" alt="" width={56} height={56} />
        <div>
          <p className="text-xl font-bold tracking-tight">{branch.name.toUpperCase()}</p>
          <p className="text-muted">{[branch.address, branch.phone && phone(branch.phone)].filter(Boolean).join(", ")}</p>
        </div>
      </div>
      <div className="text-right">
        <p className="text-lg font-bold">{title}</p>
        {right}
      </div>
    </header>
  );
}

export function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="mb-4 break-inside-avoid-page">
      <p className="mb-1 bg-ink px-2 py-1 font-bold text-accent-ink [print-color-adjust:exact]">{title.toUpperCase()}</p>
      {children}
    </section>
  );
}

export function Grid({ head, rows, right = [] }: { head: string[]; rows: ReactNode[][]; right?: number[] }) {
  return (
    <div className="mb-2 overflow-x-auto print:overflow-visible">
    <table className="w-full border-collapse">
      <thead><tr className="[print-color-adjust:exact]">{head.map((h, i) => <th key={h} className={`border border-rule bg-paper-2 px-2 py-1 ${right.includes(i) ? "text-right" : "text-left"}`}>{h}</th>)}</tr></thead>
      <tbody>
        {rows.length ? rows.map((r, i) => <tr key={i}>{r.map((c, j) => <td key={j} className={`border border-rule px-2 py-1 align-top ${right.includes(j) ? "num text-right" : ""}`}>{c}</td>)}</tr>)
          : <tr><td colSpan={head.length} className="border border-rule px-2 py-1 text-muted">None</td></tr>}
      </tbody>
    </table>
    </div>
  );
}
