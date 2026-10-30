"use client";

import { VisitProgress } from "@/components/job-progress";
import Link from "next/link";
import { NextStep } from "@/components/next-step";
import { useParams, useRouter } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { CatalogPicker, type JobLine, lineCode, lineName, linkButton, type Pick, QuoteBadge, type QuoteStatus } from "@/components/estimates";
import { RequirePermission } from "@/components/shell";
import { Button, Card, EmptyState, ErrorState, Input, Notice, SkeletonRows } from "@/components/ui";
import { VehiclePanel } from "@/components/vehicle-panel";
import { api, ApiError, useApi } from "@/lib/api";
import { money, qty, when, qtyStep } from "@/lib/format";
import { lineQty } from "@/lib/schemas";
import { useSession } from "@/lib/session";

type JobCard = {
  id: string; number: string; notes: string; version: number; updated_at: string; lines: JobLine[];
  visit: { id: string; number: string; status: string; car_id: string; customer_id: string; buyer_id: string | null; complaint: string };
  quotation: { id: string; number: string; revision: number; status: QuoteStatus } | null;
};

export default function JobCardPage() {
  return (
    <RequirePermission permission="job-cards">
      <Suspense fallback={<Card flush><SkeletonRows rows={6} /></Card>}>
        <Loader />
      </Suspense>
    </RequirePermission>
  );
}

function Loader() {
  const { id } = useParams<{ id: string }>();
  const jc = useApi<JobCard>(`/api/job-cards/${id}`);
  if (jc.error) return <Card flush><ErrorState message={jc.error} onRetry={jc.reload} /></Card>;
  if (!jc.data) return <Card flush><SkeletonRows rows={6} /></Card>;
  return <Editor key={jc.data.version} initial={jc.data} />;
}

/** A picked line before it is saved looks like a saved one, so the list renders both the same way. */
function fromPick(p: Pick): JobLine {
  return p.kind === "labour"
    ? { id: crypto.randomUUID(), kind: "labour", labour_code_id: p.id, item_id: null, qty: "1", note: "", labour_code: { code: p.code, name: p.name } }
    : { id: crypto.randomUUID(), kind: "part", labour_code_id: null, item_id: p.id, qty: "1", note: "",
        item: { number: p.code, name: p.name, unit: p.unit!, sale_price: p.sale_price!, on_hand: p.on_hand!, short: "0" } };
}

function Editor({ initial }: { initial: JobCard }) {
  const router = useRouter();
  const { can } = useSession();
  const [lines, setLines] = useState(initial.lines.map((l) => ({ ...l, qty: String(Number(l.qty)) })));
  const [notes, setNotes] = useState(initial.notes);
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [card, setCard] = useState(initial);
  const locked = initial.visit.status !== "open";

  // Leaving with unsaved lines asks first.
  useEffect(() => {
    if (!dirty) return;
    const block = (e: BeforeUnloadEvent) => e.preventDefault();
    window.addEventListener("beforeunload", block);
    return () => window.removeEventListener("beforeunload", block);
  }, [dirty]);

  const change = (fn: (ls: JobLine[]) => JobLine[]) => { setLines(fn); setDirty(true); };
  const bad = lines.filter((l) => !lineQty.safeParse(l.qty).success).map((l) => l.id);

  async function save(): Promise<JobCard | null> {
    if (bad.length) { setError("Fix the quantities marked in red."); return null; }
    setBusy(true);
    setError(null);
    try {
      const saved = await api<JobCard>(`/api/job-cards/${card.id}`, { method: "PUT", json: {
        notes, version: card.version,
        lines: lines.map(({ kind, labour_code_id, item_id, qty, note, proposed_price }) => ({ kind, labour_code_id, item_id, qty, note, proposed_price: proposed_price ?? null })),
      } });
      setCard(saved);
      setLines(saved.lines);
      setDirty(false);
      return saved;
    } catch (err) {
      setError((err as Error).message);
      return null;
    } finally {
      setBusy(false);
    }
  }

  async function quote() {
    const saved = dirty ? await save() : card;
    if (!saved) return;
    setBusy(true);
    try {
      const q = await api<{ id: string }>(`/api/job-cards/${saved.id}/quotation`, { method: "POST" });
      router.push(`/quotations/${q.id}`);
    } catch (err) {
      const d = err instanceof ApiError ? (err.detail as { quotation_id?: string }) : undefined;
      if (d?.quotation_id) { router.push(`/quotations/${d.quotation_id}`); return; }
      setError((err as Error).message);
      setBusy(false);
    }
  }

  const shortages = lines.filter((l) => l.item && Number(l.qty) > Number(l.item.on_hand));
  return (
    <>
      {initial.visit && <VisitProgress visitId={initial.visit.id} />}
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1>Job card</h1>
          <p className="text-muted">{card.number} for <Link href={`/visits/${card.visit.id}`} className="underline">{card.visit.number}</Link></p>
        </div>
        <p className="text-sm text-muted">{dirty ? "Unsaved changes" : `Saved ${when(card.updated_at)}`}</p>
      </div>

      {!locked && (lines.length === 0
        ? <NextStep who="Front desk" target="act-add-work" open={false} label="Add work">Add the work to be done: search for a labour code or a part.</NextStep>
        : <NextStep who="Front desk" target="act-quote" open={false} label="Make the quotation">The list is ready? Make the quotation to price it for the customer.</NextStep>)}

      <div className="grid gap-4 shell:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)]">
        <div className="space-y-4">
          <Card title="Work to do" flush>
            {!locked && <div className="border-b border-rule p-4 shell:px-5"><CatalogPicker onPick={(p) => change((ls) => [...ls, fromPick(p)])} /></div>}
            {!lines.length ? (
              <EmptyState title="Nothing on the job card yet">
                Search for a labour code or a part above, or scan a part&apos;s barcode. Only codes and stock items can be added, so every job is priced and costed the same way.
              </EmptyState>
            ) : (
              <ul>
                {lines.map((l) => (
                  <li key={l.id} className="grid gap-3 border-t border-rule px-4 py-3 first:border-t-0 sm:grid-cols-[minmax(0,1fr)_7rem] shell:px-5">
                    <div className="min-w-0">
                      <p className="font-medium">{lineName(l)}</p>
                      <p className="flex flex-wrap gap-3 text-sm text-muted">
                        <span>{l.kind === "labour" ? "Labour" : "Part"}</span><span>{lineCode(l)}</span>
                        {l.proposed_price != null && <span className="num">Inspector&apos;s estimate {money(l.proposed_price)}</span>}
                        {l.item && (Number(l.qty) > Number(l.item.on_hand)
                          ? <span className="text-error">{Number(l.item.on_hand) > 0 ? `Only ${qty(l.item.on_hand)} in stock` : "Out of stock"}</span>
                          : <span>{qty(l.item.on_hand)} {l.item.unit} in stock</span>)}
                      </p>
                      <Input aria-label={`Note for ${lineName(l)}`} placeholder="Note (optional)" value={l.note} disabled={locked} maxLength={300}
                             onChange={(e) => change((ls) => ls.map((x) => (x.id === l.id ? { ...x, note: e.target.value } : x)))} />
                    </div>
                    <div className="flex items-end gap-2 sm:flex-col sm:items-stretch">
                      <label className="flex-1">
                        <span className="mb-1 block text-sm text-muted">Quantity</span>
                        <Input type="number" inputMode="decimal" min="0" step={qtyStep(l.item?.unit)} value={l.qty} disabled={locked}
                               aria-invalid={bad.includes(l.id)} className={`min-h-11 w-full rounded-control border bg-surface px-3 text-base ${bad.includes(l.id) ? "border-error" : "border-rule-strong"}`}
                               onChange={(e) => change((ls) => ls.map((x) => (x.id === l.id ? { ...x, qty: e.target.value } : x)))} />
                      </label>
                      {!locked && <Button variant="danger" onClick={() => change((ls) => ls.filter((x) => x.id !== l.id))}>Remove</Button>}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </Card>

          <Card title="Notes for the estimate">
            <textarea value={notes} disabled={locked} rows={3} maxLength={3000} aria-label="Notes"
                      onChange={(e) => { setNotes(e.target.value); setDirty(true); }}
                      className="w-full rounded-control border border-rule-strong bg-surface px-3 py-2.5 text-base focus-visible:border-ink" />
          </Card>

          {shortages.length > 0 && <Notice tone="warning">{shortages.length === 1 ? "One part is" : `${shortages.length} parts are`} short in stock. The quotation can still go out; order them before the repair starts.</Notice>}
          <Notice>{error}</Notice>
          {!locked && (
            <div className="flex flex-wrap gap-2">
              {card.quotation
                ? <Link href={`/quotations/${card.quotation.id}`} className={linkButton}>Open quotation {card.quotation.number}</Link>
                : can("quotations") && <Button id="act-quote" onClick={quote} disabled={busy || !lines.length}>Make the quotation</Button>}
              <Button variant="success" onClick={save} disabled={busy || !dirty}>{busy ? "Saving" : "Save job card"}</Button>
            </div>
          )}
          {card.quotation && <p className="flex flex-wrap items-center gap-2 text-sm text-muted">Quotation {card.quotation.number}, revision {card.quotation.revision}: <QuoteBadge status={card.quotation.status} /> Changes here don&apos;t change a quotation already made; revise the quotation instead.</p>}
        </div>

        <div className="space-y-4">
          <Card title="What the customer said">
            <p className={card.visit.complaint ? "whitespace-pre-line" : "text-muted"}>{card.visit.complaint || "Nothing recorded at check-in."}</p>
          </Card>
          <VehiclePanel carId={card.visit.car_id} ownerId={card.visit.customer_id} buyerId={card.visit.buyer_id} />
        </div>
      </div>
    </>
  );
}
