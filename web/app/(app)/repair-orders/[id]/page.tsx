"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { Suspense, useState, type FormEvent } from "react";
import { type Uploaded, PhotoCapture } from "@/components/capture";
import { CatalogPicker, lineCode, linkButton, type Pick } from "@/components/estimates";
import { RO_STAGES, RoBadge, STAGE, type RoLine, type RoStatus } from "@/components/repairs";
import { Segments } from "@/components/search";
import { RequirePermission } from "@/components/shell";
import { Badge, Button, Card, ErrorState, Field, Input, Notice, Select, SkeletonRows } from "@/components/ui";
import { VehiclePanel } from "@/components/vehicle-panel";
import { api, useApi } from "@/lib/api";
import { money, qty, when } from "@/lib/format";
import { linePrice, lineQty } from "@/lib/schemas";

type Activity = { id: string; kind: string; body: string; from_status: RoStatus | null; to_status: RoStatus | null; line_id: string | null;
  customer_visible: boolean; at: string; by: string | null; photos: { id: string; name: string; url: string }[] };
type RepairOrder = {
  id: string; number: string; status: RoStatus; held_from: RoStatus | null; version: number; created_at: string;
  quotation: { id: string; number: string; revision: number };
  visit: { id: string; number: string; status: string; car_id: string; customer_id: string; buyer_id: string | null; complaint: string;
    odometer_in: number | null; fuel_eighths: number | null; condition_notes: string; items_left: string };
  lines: RoLine[]; activity: Activity[];
};

export default function RepairOrderPage() {
  return (
    <RequirePermission permission="repair-orders">
      <Suspense fallback={<Card flush><SkeletonRows rows={8} /></Card>}>
        <Loader />
      </Suspense>
    </RequirePermission>
  );
}

function Loader() {
  const { id } = useParams<{ id: string }>();
  const ro = useApi<RepairOrder>(`/api/repair-orders/${id}`);
  const techs = useApi<{ id: string; name: string }[]>("/api/technicians");
  const [fresh, setFresh] = useState<RepairOrder | null>(null);
  if (ro.error) return <Card flush><ErrorState message={ro.error} onRetry={ro.reload} /></Card>;
  if (!ro.data) return <Card flush><SkeletonRows rows={8} /></Card>;
  // Every action returns the whole order; showing it directly saves a second request.
  return <View ro={fresh && fresh.version >= ro.data.version ? fresh : ro.data} techs={techs.data ?? []} onChange={setFresh} />;
}

function View({ ro, techs, onChange }: { ro: RepairOrder; techs: { id: string; name: string }[]; onChange: (r: RepairOrder) => void }) {
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const working = ro.visit.status === "open" && ro.status !== "delivered";

  async function call(path: string, method: string, json?: object) {
    setBusy(true);
    setError(null);
    try {
      onChange(await api<RepairOrder>(`/api/repair-orders/${ro.id}${path}`, { method, json }));
      return true;
    } catch (err) {
      setError((err as Error).message);
      return false;
    } finally {
      setBusy(false);
    }
  }

  const pending = ro.lines.filter((l) => l.state === "pending").length;
  return (
    <>
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1>Repair order {ro.number}</h1>
          <p className="text-muted">
            For <Link href={`/visits/${ro.visit.id}`} className="underline">{ro.visit.number}</Link>, from <Link href={`/quotations/${ro.quotation.id}`} className="underline">quotation {ro.quotation.number}</Link>
          </p>
        </div>
        <RoBadge status={ro.status} />
      </div>

      <div className="grid gap-4 shell:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        <div className="space-y-4">
          <StatusCard ro={ro} working={working} busy={busy} onMove={(to, note) => call("/status", "POST", { to, note, version: ro.version })} />
          <Notice>{error}</Notice>

          <Card title="Work and parts" actions={<span className="text-sm text-muted">{pending ? `${pending} to do` : "All lines marked"}</span>} flush>
            <ul>
              {ro.lines.map((l) => <LineRow key={l.id} l={l} techs={techs} working={working} busy={busy} call={call} />)}
            </ul>
            {working && <ExtraWork busy={busy} onAdd={(b) => call("/lines", "POST", b)} />}
          </Card>

          <ActivityCard ro={ro} working={working} onAdd={(b) => call("/activity", "POST", b)} />
        </div>

        <div className="space-y-4">
          <Card title="At check-in">
            <dl className="grid gap-4 sm:grid-cols-2">
              <div><dt className="text-sm text-muted">Odometer</dt><dd className="num">{ro.visit.odometer_in != null ? `${ro.visit.odometer_in.toLocaleString("en-PK")} km` : "Not recorded"}</dd></div>
              <div><dt className="text-sm text-muted">Fuel</dt><dd>{ro.visit.fuel_eighths == null ? "Not recorded" : `${ro.visit.fuel_eighths}/8`}</dd></div>
              {[["Customer's complaint", ro.visit.complaint], ["Existing damage", ro.visit.condition_notes], ["Valuables in the car", ro.visit.items_left]].map(([l, t]) => (
                <div key={l} className="sm:col-span-2"><dt className="text-sm text-muted">{l}</dt><dd className={t ? "whitespace-pre-line" : "text-muted"}>{t || "None"}</dd></div>
              ))}
            </dl>
            <Link href={`/visits/${ro.visit.id}`} className="mt-3 inline-block text-sm underline">Check-in photos and signature</Link>
          </Card>
          <VehiclePanel carId={ro.visit.car_id} ownerId={ro.visit.customer_id} buyerId={ro.visit.buyer_id} />
        </div>
      </div>
    </>
  );
}

function StatusCard({ ro, working, busy, onMove }:
  { ro: RepairOrder; working: boolean; busy: boolean; onMove: (to: RoStatus, note: string) => Promise<boolean> }) {
  const [target, setTarget] = useState<RoStatus | null>(null);
  const [note, setNote] = useState("");
  const current = ro.status === "on_hold" ? ro.held_from! : ro.status;
  const at = RO_STAGES.indexOf(current);
  const next = RO_STAGES[at + 1];
  const needsNote = target === "on_hold" || (target != null && RO_STAGES.indexOf(target) < at);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (target && (await onMove(target, note))) { setTarget(null); setNote(""); }
  }
  return (
    <Card title="Progress">
      <ol className="mb-4 flex flex-wrap gap-1" aria-label="Stages">
        {RO_STAGES.map((s, i) => (
          <li key={s} aria-current={s === current ? "step" : undefined}
              className={`rounded-control px-2.5 py-1 text-sm ${s === current ? "bg-ink text-surface" : i < at ? "bg-paper-3 text-ink-2" : "text-muted"}`}>
            {STAGE[s]}
          </li>
        ))}
      </ol>
      {ro.status === "on_hold" && <div className="mb-4"><Notice tone="warning">On hold. It resumes at {STAGE[ro.held_from!].toLowerCase()}.</Notice></div>}
      {working ? (
        target ? (
          <form onSubmit={submit} className="space-y-4">
            <p>Move to <b className="font-medium">{STAGE[target]}</b></p>
            <Field label={needsNote ? "Why? (required)" : "Note (optional)"}>
              <Input value={note} onChange={(e) => setNote(e.target.value)} required={needsNote} minLength={needsNote ? 3 : undefined} autoFocus maxLength={1000} />
            </Field>
            <div className="flex flex-wrap gap-2">
              <Button type="submit" disabled={busy}>Confirm</Button>
              <Button type="button" variant="secondary" onClick={() => setTarget(null)}>Cancel</Button>
            </div>
          </form>
        ) : (
          <div className="flex flex-wrap items-end gap-2">
            {ro.status === "on_hold"
              ? <Button onClick={() => onMove(ro.held_from!, "")} disabled={busy}>Resume</Button>
              : next && next !== "delivered" && <Button onClick={() => setTarget(next)} disabled={busy}>Move to {STAGE[next].toLowerCase()}</Button>}
            {ro.status !== "on_hold" && <Button variant="secondary" onClick={() => setTarget("on_hold")}>Put on hold</Button>}
            <label className="min-w-40">
              <span className="sr-only">Move to another stage</span>
              <Select value="" onChange={(e) => e.target.value && setTarget(e.target.value as RoStatus)}>
                <option value="">Other stage</option>
                {RO_STAGES.filter((s) => s !== current && s !== "delivered").map((s) => <option key={s} value={s}>{STAGE[s]}</option>)}
              </Select>
            </label>
          </div>
        )
      ) : <p className="text-muted">{ro.status === "delivered" ? "Delivered. This repair order is closed." : "The visit is closed."}</p>}
      {ro.status === "ready" && <p className="mt-3 text-sm text-muted">Next: the invoice and gate pass (being built).</p>}
    </Card>
  );
}

function LineRow({ l, techs, working, busy, call }:
  { l: RoLine; techs: { id: string; name: string }[]; working: boolean; busy: boolean; call: (path: string, method: string, json?: object) => Promise<boolean> }) {
  const [move, setMove] = useState<"issue" | "return" | null>(null);
  const [amount, setAmount] = useState("");
  const url = `/lines/${l.id}`;
  const remaining = Math.max(Number(l.qty) - Number(l.issued_qty), 0);

  return (
    <li className="space-y-3 border-t border-rule px-4 py-3 first:border-t-0 shell:px-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="font-medium">{l.description}</p>
          <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted">
            <span>{l.kind === "labour" ? "Labour" : "Part"}</span><span>{lineCode(l)}</span><span className="num">{qty(l.qty)} x {money(l.unit_price)}</span>
            {!l.in_quote && <Badge tone="warning">Not in the quotation</Badge>}
          </p>
          {l.item && (
            <p className="text-sm text-ink-2">
              Issued {qty(l.issued_qty)} of {qty(l.qty)} {l.item.unit}. {qty(l.item.on_hand)} left in stock.
            </p>
          )}
        </div>
        {working ? (
          <Segments value={l.state} onChange={(s) => call(url, "PATCH", { state: s })}
                    options={[{ value: "pending", label: "To do" }, { value: "done", label: "Done" }, { value: "not_done", label: "Not done" }]} />
        ) : <Badge tone={l.state === "done" ? "success" : "neutral"}>{l.state === "done" ? "Done" : l.state === "not_done" ? "Not done" : "To do"}</Badge>}
      </div>

      {working && (
        <div className="flex flex-wrap items-end gap-2">
          <label className="min-w-48 flex-1">
            <span className="mb-1 block text-sm text-muted">Technician</span>
            <Select value={l.technician_id ?? ""} disabled={busy}
                    onChange={(e) => call(url, "PATCH", e.target.value ? { technician_id: e.target.value } : { clear_technician: true })}>
              <option value="">Not assigned</option>
              {techs.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
            </Select>
          </label>
          {l.item && !move && <Button variant="secondary" onClick={() => { setMove("issue"); setAmount(String(remaining || 1)); }}>Issue from stock</Button>}
          {l.item && !move && Number(l.issued_qty) > 0 && <Button variant="ghost" onClick={() => { setMove("return"); setAmount("1"); }}>Return unused</Button>}
          {!l.in_quote && Number(l.issued_qty) === 0 && <Button variant="ghost" onClick={() => call(url, "DELETE")}>Remove</Button>}
        </div>
      )}
      {!working && l.technician && <p className="text-sm text-muted">By {l.technician}</p>}

      {move && (
        <form className="flex flex-wrap items-end gap-2 rounded-control bg-paper-2 p-3"
              onSubmit={async (e) => { e.preventDefault(); if (lineQty.safeParse(amount).success && (await call(`${url}/${move}`, "POST", { qty: amount }))) setMove(null); }}>
          <Field label={move === "issue" ? "Quantity to issue" : "Quantity to return"} error={amount && !lineQty.safeParse(amount).success ? "More than 0" : undefined}>
            <Input type="number" inputMode="decimal" min="0" step="any" value={amount} onChange={(e) => setAmount(e.target.value)} autoFocus />
          </Field>
          <Button type="submit" disabled={busy}>{move === "issue" ? "Issue" : "Return to stock"}</Button>
          <Button type="button" variant="secondary" onClick={() => setMove(null)}>Cancel</Button>
        </form>
      )}
    </li>
  );
}

function ExtraWork({ busy, onAdd }: { busy: boolean; onAdd: (b: object) => Promise<boolean> }) {
  const [pick, setPick] = useState<Pick | null>(null);
  const [price, setPrice] = useState("");
  const [amount, setAmount] = useState("1");
  const [reason, setReason] = useState("");
  const [tried, setTried] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setTried(true);
    if (!pick || !linePrice.safeParse(price).success || !lineQty.safeParse(amount).success || reason.trim().length < 3) return;
    const ok = await onAdd({ kind: pick.kind, labour_code_id: pick.kind === "labour" ? pick.id : null, item_id: pick.kind === "part" ? pick.id : null,
                             qty: amount, unit_price: price, reason });
    if (ok) { setPick(null); setPrice(""); setAmount("1"); setReason(""); setTried(false); }
  }
  return (
    <div className="border-t border-rule p-4 shell:px-5">
      {!pick ? (
        <>
          <p className="mb-2 text-sm font-medium text-ink-2">Extra work found during the repair</p>
          <CatalogPicker onPick={(p) => { setPick(p); setPrice(p.kind === "part" && Number(p.sale_price) ? String(Number(p.sale_price)) : ""); }} />
        </>
      ) : (
        <form onSubmit={submit} className="grid gap-4 sm:grid-cols-[minmax(0,1fr)_6rem_9rem]">
          <p className="font-medium sm:col-span-3">{pick.name} <span className="text-sm font-normal text-muted">{pick.code}</span></p>
          <Field label="Why is it needed?" error={tried && reason.trim().length < 3 ? "Required" : undefined}>
            <Input value={reason} onChange={(e) => setReason(e.target.value)} maxLength={500} autoFocus />
          </Field>
          <Field label="Qty" error={tried && !lineQty.safeParse(amount).success ? "More than 0" : undefined}>
            <Input type="number" inputMode="decimal" min="0" step="any" value={amount} onChange={(e) => setAmount(e.target.value)} />
          </Field>
          <Field label="Price (Rs)" error={tried && !linePrice.safeParse(price).success ? "Enter the price" : undefined}>
            <Input type="number" inputMode="decimal" min="0" step="any" value={price} onChange={(e) => setPrice(e.target.value)} />
          </Field>
          <p className="text-sm text-muted sm:col-span-3">It is marked “not in the quotation”. Tell the customer before doing it; the activity below records that you did.</p>
          <div className="flex flex-wrap gap-2 sm:col-span-3">
            <Button type="submit" variant="secondary" disabled={busy}>Add to the repair order</Button>
            <Button type="button" variant="ghost" onClick={() => setPick(null)}>Cancel</Button>
          </div>
        </form>
      )}
    </div>
  );
}

const KINDS: Record<string, string> = { note: "Note", finding: "Finding", customer_update: "Customer update" };

function ActivityCard({ ro, working, onAdd }: { ro: RepairOrder; working: boolean; onAdd: (b: object) => Promise<boolean> }) {
  const [kind, setKind] = useState("note");
  const [body, setBody] = useState("");
  const [lineId, setLineId] = useState("");
  const [photos, setPhotos] = useState<Uploaded[]>([]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (body.trim().length < 2) return;
    if (await onAdd({ kind, body, line_id: lineId || null, photo_ids: photos.map((p) => p.id) })) { setBody(""); setPhotos([]); setLineId(""); }
  }
  const lineName = (id: string | null) => ro.lines.find((l) => l.id === id)?.description;
  return (
    <Card title="Activity">
      {working && (
        <form onSubmit={submit} className="mb-5 space-y-3">
          <Segments value={kind} onChange={setKind} options={Object.entries(KINDS).map(([value, label]) => ({ value, label }))} />
          <label className="block">
            <span className="sr-only">{KINDS[kind]}</span>
            <textarea value={body} onChange={(e) => setBody(e.target.value)} rows={2} maxLength={3000}
                      placeholder={kind === "finding" ? "What did you find?" : kind === "customer_update" ? "What the customer should know, e.g. ready by 5pm" : "What happened"}
                      className="w-full rounded-control border border-rule-strong bg-surface px-3 py-2.5 text-base focus-visible:border-accent" />
          </label>
          <div className="grid gap-3 sm:grid-cols-2">
            <label>
              <span className="mb-1 block text-sm text-muted">About a line (optional)</span>
              <Select value={lineId} onChange={(e) => setLineId(e.target.value)}>
                <option value="">The whole job</option>
                {ro.lines.map((l) => <option key={l.id} value={l.id}>{l.description}</option>)}
              </Select>
            </label>
            <PhotoCapture value={photos} onChange={setPhotos} label="Add photos" note={`${ro.number} activity`} />
          </div>
          {kind === "customer_update" && <p className="text-sm text-muted">Customer updates appear on the customer&apos;s copy of the visit record. Everything else stays internal.</p>}
          <Button type="submit" variant="secondary" disabled={body.trim().length < 2}>Add to activity</Button>
        </form>
      )}
      <ol className="space-y-4">
        {ro.activity.map((a) => (
          <li key={a.id} className="border-l-2 border-rule pl-3">
            <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted">
              <span>{when(a.at)}</span>{a.by && <span>{a.by}</span>}
              {a.customer_visible && <Badge tone="accent">Customer can see</Badge>}
            </p>
            <p className="font-medium">
              {a.kind === "status" ? (a.from_status ? `${STAGE[a.from_status]} to ${STAGE[a.to_status!]}` : `Opened: ${STAGE[a.to_status!]}`)
                : a.kind === "parts" ? "Parts" : a.kind === "line" ? "Work list" : KINDS[a.kind]}
              {a.line_id && lineName(a.line_id) && a.kind !== "parts" && a.kind !== "line" ? `, ${lineName(a.line_id)}` : ""}
            </p>
            {a.body && <p className="whitespace-pre-line text-ink-2">{a.body}</p>}
            {a.photos.length > 0 && (
              <ul className="mt-2 flex flex-wrap gap-2">
                {a.photos.map((p) => (
                  <li key={p.id}>
                    <a href={p.url} target="_blank" rel="noreferrer" className="block size-20 overflow-hidden rounded-control border border-rule">
                      {/* eslint-disable-next-line @next/next/no-img-element -- authenticated API files */}
                      <img src={p.url} alt={p.name} className="h-full w-full object-cover" />
                    </a>
                  </li>
                ))}
              </ul>
            )}
          </li>
        ))}
      </ol>
      {!working && <Link href={`/visits/${ro.visit.id}`} className={`${linkButton} mt-4 w-fit`}>Back to the visit</Link>}
    </Card>
  );
}
