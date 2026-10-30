"use client";

import { useMemo, useState } from "react";
import { SearchInput } from "@/components/search";
import { Button, EmptyState, PageHeader } from "@/components/ui";
import { CHAPTERS, RULES, WORDS, type Chapter, type Sop } from "@/content/manual";

// Filled pills on a phone, plain underlined links in the desktop sidebar.
const pill = "inline-flex min-h-11 items-center rounded-control bg-paper-3 px-3 hover:bg-silver active:bg-silver shell:rounded-none shell:bg-transparent shell:px-0 shell:underline shell:underline-offset-4";
// A bordered, unshaded box that never splits across two printed pages.
const box = "min-w-0 rounded-card bg-surface p-4 shell:p-5 print:break-inside-avoid print:rounded-none print:border print:border-black/50 print:bg-transparent print:p-3";

// Hard copy: A4, black on white, no menu, each chapter on a fresh page, and no box cut in half.
const PRINT_CSS = `@page { size: A4; margin: 14mm 14mm 16mm; }
@media print {
  html, body { background: #fff !important; color: #000 !important; font-size: 10.5pt; line-height: 1.45; }
  main { max-width: none !important; padding: 0 !important; }
  h1 { font-size: 20pt; } h2 { font-size: 14pt; } h3 { font-size: 11.5pt; }
  a { color: inherit !important; text-decoration: none !important; }
  .manual-chapter { break-before: page; }
  .manual-chapter > h2 { break-after: avoid; }
  .manual-sop h3 { break-after: avoid; }
  .manual-sop li { break-inside: avoid; }
}`;

const matches = (s: Sop, q: string) =>
  [s.title, s.who, ...s.steps, ...(s.right ?? []), ...(s.avoid ?? [])].join(" ").toLowerCase().includes(q);

export default function HelpPage() {
  const [q, setQ] = useState("");
  const query = q.trim().toLowerCase();
  const numbered = useMemo(() => CHAPTERS.map((c, i) => ({ ...c, n: i + 1 })), []);
  const chapters = useMemo(
    () => (query ? numbered.map((c) => ({ ...c, sops: c.sops.filter((s) => matches(s, query) || c.title.toLowerCase().includes(query)) })).filter((c) => c.sops.length) : numbered),
    [query, numbered],
  );

  return (
    <>
      <style>{PRINT_CSS}</style>
      <div className="hidden print:block">
        <h1 className="font-semibold">GermanATO user manual</h1>
        <p className="mt-1">Step-by-step procedures for using the workshop system correctly.</p>
        <p className="mt-1 text-sm">Printed {new Date().toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" })}. The latest version is under Help in the system.</p>
      </div>
      <div className="print:hidden">
        <PageHeader title="Help" description="How to use the system correctly, step by step. Follow these procedures and your records, your cash and your books will agree."
          actions={<Button variant="secondary" onClick={() => window.print()}>Print this manual</Button>} />
      </div>
      <div className="grid gap-6 shell:grid-cols-[15rem_1fr] shell:items-start print:block">
        <nav aria-label="Manual contents" className={`no-print shell:sticky shell:top-4 ${query ? "hidden shell:block" : ""}`}>
          <p className="mb-2 text-sm font-medium text-ink-2">Contents</p>
          <ul className="flex flex-wrap gap-2 shell:flex-col shell:gap-0">
            <li><a href="#rules" className={pill}>The golden rules</a></li>
            <li><a href="#words" className={pill}>What the words mean</a></li>
            {numbered.map((c) => <li key={c.id}><a href={`#${c.id}`} className={pill}>{c.n}. {c.title}</a></li>)}
          </ul>
        </nav>
        <div className="grid min-w-0 gap-6 print:block">
          <div className="no-print max-w-lg"><SearchInput label="Search the manual" placeholder="Search the manual: refund, salary, gate pass ..." value={q} onChange={setQ} /></div>

          {/* Printed contents: a list to find chapters by number, since links do nothing on paper. */}
          <section className="hidden print:mt-5 print:block">
            <h2 className="font-semibold">Contents</h2>
            <ol className="mt-1 list-none">
              <li>The golden rules</li><li>What the words mean</li>
              {numbered.map((c) => <li key={c.id}>{c.n}. {c.title}</li>)}
            </ol>
          </section>

          {!query && (
            <>
              <section id="rules" className="scroll-mt-4 print:mt-5">
                <div className={box}>
                  <h2 className="font-semibold">The golden rules</h2>
                  <ol className="mt-3 grid gap-2 print:mt-2 print:gap-1">{RULES.map((r, i) => <li key={r} className="flex gap-3"><span className="num w-6 shrink-0 text-muted print:text-black">{i + 1}.</span><span>{r}</span></li>)}</ol>
                </div>
              </section>
              <section id="words" className="scroll-mt-4 print:mt-5">
                <div className={box}>
                  <h2 className="font-semibold">What the words mean</h2>
                  <dl className="mt-3 grid gap-2 print:mt-2 print:gap-1">{WORDS.map(([w, d]) => <div key={w}><dt className="inline font-medium">{w}: </dt><dd className="inline">{d}</dd></div>)}</dl>
                </div>
              </section>
            </>
          )}
          {!chapters.length && <EmptyState title="Nothing matches">Try a shorter word, such as “refund” or “stock”.</EmptyState>}
          {chapters.map((c) => <ChapterView key={c.id} c={c} />)}
        </div>
      </div>
    </>
  );
}

function ChapterView({ c }: { c: Chapter & { n: number } }) {
  return (
    <section id={c.id} className="manual-chapter scroll-mt-4">
      <h2 className="text-xl font-semibold">{c.n}. {c.title}</h2>
      <p className="mt-1 text-muted print:text-black">{c.intro}</p>
      <div className="mt-4 grid gap-4 print:block print:space-y-3">{c.sops.map((s, i) => <SopView key={s.id} s={s} no={`${c.n}.${i + 1}`} />)}</div>
    </section>
  );
}

function SopView({ s, no }: { s: Sop; no: string }) {
  return (
    <article className={`manual-sop ${box}`}>
      <h3 className="text-lg font-semibold print:text-base"><span className="num text-muted print:text-black">{no}</span> {s.title}</h3>
      <p className="mt-0.5 text-sm text-muted print:text-black">Who: {s.who}</p>
      <ol className="mt-3 grid gap-2 print:mt-2 print:gap-1">
        {s.steps.map((t, i) => (
          <li key={t} className="flex gap-3">
            {s.checklist
              ? <span aria-hidden="true" className="mt-1 size-4 shrink-0 rounded-sm border border-ink-2 print:border-black" />
              : <span className="num w-6 shrink-0 text-muted print:text-black">{i + 1}.</span>}
            <span className="min-w-0 [overflow-wrap:anywhere]">{t}</span>
          </li>
        ))}
      </ol>
      {s.right && <Callout label="You know it went right when" tone="ok" items={s.right} />}
      {s.avoid && <Callout label="Be careful" tone="warn" items={s.avoid} />}
    </article>
  );
}

function Callout({ label, tone, items }: { label: string; tone: "ok" | "warn"; items: string[] }) {
  return (
    <div className={`mt-3 rounded-control px-3 py-2 print:mt-2 print:rounded-none print:border-l-4 print:bg-transparent print:py-1 ${tone === "ok" ? "bg-success-soft print:border-black/40" : "bg-warning-soft print:border-black"}`}>
      <p className="text-sm font-medium">{label}</p>
      <ul className="mt-1 grid list-disc gap-1 pl-5 text-[0.9375rem] print:gap-0">{items.map((t) => <li key={t} className="[overflow-wrap:anywhere]">{t}</li>)}</ul>
    </div>
  );
}
