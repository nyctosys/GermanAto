"use client";

import { useMemo, useState } from "react";
import { Button, Card, EmptyState, Input, PageHeader } from "@/components/ui";
import { CHAPTERS, RULES, type Chapter, type Sop } from "@/content/manual";

// Filled pills on a phone, plain underlined links in the desktop sidebar.
const pill = "inline-flex min-h-11 items-center rounded-control bg-paper-3 px-3 hover:bg-silver active:bg-silver shell:rounded-none shell:bg-transparent shell:px-0 shell:underline shell:underline-offset-4";

const matches = (s: Sop, q: string) =>
  [s.title, s.who, ...s.steps, ...(s.right ?? []), ...(s.avoid ?? [])].join(" ").toLowerCase().includes(q);

export default function HelpPage() {
  const [q, setQ] = useState("");
  const query = q.trim().toLowerCase();
  const chapters = useMemo<Chapter[]>(
    () => (query ? CHAPTERS.map((c) => ({ ...c, sops: c.sops.filter((s) => matches(s, query) || c.title.toLowerCase().includes(query)) })).filter((c) => c.sops.length) : CHAPTERS),
    [query],
  );

  return (
    <>
      <PageHeader title="Help" description="How to use the system correctly, step by step. Follow these procedures and the records, the cash and the books will agree."
        actions={<Button variant="secondary" onClick={() => window.print()}>Print this manual</Button>} />
      <div className="grid gap-6 shell:grid-cols-[15rem_1fr] shell:items-start">
        <nav aria-label="Manual contents" className={`no-print shell:sticky shell:top-4 ${query ? "hidden shell:block" : ""}`}>
          <p className="mb-2 text-sm font-medium text-ink-2">Contents</p>
          <ul className="flex flex-wrap gap-2 shell:flex-col shell:gap-0">
            <li><a href="#rules" className={pill}>The golden rules</a></li>
            {CHAPTERS.map((c) => <li key={c.id}><a href={`#${c.id}`} className={pill}>{c.title}</a></li>)}
          </ul>
        </nav>
        <div className="grid min-w-0 gap-6">
          <div className="no-print max-w-lg"><Input type="search" aria-label="Search the manual" placeholder="Search the manual: refund, payroll, gate pass ..." value={q} onChange={(e) => setQ(e.target.value)} /></div>
          {!query && (
            <section id="rules" className="scroll-mt-4">
              <Card title="The golden rules">
                <ol className="grid gap-2">{RULES.map((r, i) => <li key={r} className="flex gap-3"><span className="num w-6 shrink-0 text-muted">{i + 1}.</span><span>{r}</span></li>)}</ol>
              </Card>
            </section>
          )}
          {!chapters.length && <EmptyState title="Nothing matches">Try a shorter word, such as “refund” or “stock”.</EmptyState>}
          {chapters.map((c) => (
            <section key={c.id} id={c.id} className="scroll-mt-4">
              <h2 className="text-xl font-semibold">{c.title}</h2>
              <p className="mt-1 text-muted">{c.intro}</p>
              <div className="mt-4 grid gap-4">{c.sops.map((s) => <SopCard key={s.id} s={s} />)}</div>
            </section>
          ))}
        </div>
      </div>
    </>
  );
}

function SopCard({ s }: { s: Sop }) {
  return (
    <Card title={s.title}>
      <p className="text-sm text-muted">Who: {s.who}</p>
      <ol className="mt-3 grid gap-2">
        {s.steps.map((t, i) => <li key={t} className="flex gap-3"><span className="num w-6 shrink-0 text-muted">{i + 1}.</span><span className="min-w-0 [overflow-wrap:anywhere]">{t}</span></li>)}
      </ol>
      {s.right && <Callout label="You know it is right when" tone="ok" items={s.right} />}
      {s.avoid && <Callout label="Avoid" tone="warn" items={s.avoid} />}
    </Card>
  );
}

function Callout({ label, tone, items }: { label: string; tone: "ok" | "warn"; items: string[] }) {
  return (
    <div className={`mt-3 rounded-control px-3 py-2 ${tone === "ok" ? "bg-success-soft" : "bg-warning-soft"}`}>
      <p className="text-sm font-medium">{label}</p>
      <ul className="mt-1 grid list-disc gap-1 pl-5 text-[0.9375rem]">{items.map((t) => <li key={t} className="[overflow-wrap:anywhere]">{t}</li>)}</ul>
    </div>
  );
}
