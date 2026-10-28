"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { Suspense, useEffect, useRef, useState, type ReactNode } from "react";
import { type Uploaded, PhotoCapture, SignaturePad, upload } from "@/components/capture";
import { carTitle, Plate } from "@/components/cars";
import { CatalogPicker, type Pick } from "@/components/estimates";
import { Segments } from "@/components/search";
import { RequirePermission } from "@/components/shell";
import { type Snapshot, VehiclePanel } from "@/components/vehicle-panel";
import { Badge, Button, Card, Checkbox, ErrorState, Field, Input, Notice, Select, SkeletonRows } from "@/components/ui";
import { api, ApiError, useApi } from "@/lib/api";
import { money } from "@/lib/format";
import { useSession } from "@/lib/session";
import { when } from "@/lib/format";

// --- types mirroring app/routers/workshop.py ---------------------------------------------------
type Rating = "good" | "average" | "attention" | "not_checked";
type ItemAnswer = { rating: Rating; note: string; photo_ids: string[] };
type Data = {
  items: Record<string, ItemAnswer>;
  bulk_marked: string[];
  paint: { findings: Record<string, string>; notes: string; accident: "none" | "repair_signs" | null; structural_notes: string };
  tyres: Record<"fl" | "fr" | "rl" | "rr", { mm: string | null; pct: number | null }> & { spare: string; wheel_damage: boolean | null };
  scan: { tool: string; scanned_on: string | null; battery_rest_v: string | null; battery_running_v: string | null; warning_lights: string[];
          other_light: string; dtcs_stored: boolean | null; modules_not_communicating: string;
          dtcs: { module: string; code: string; description: string; priority: string }[] };
  ev: Record<"soc_pct" | "soh_pct" | "capacity_kwh" | "pack_voltage" | "cell_imbalance_mv" | "isolation_mohm", string | null> &
      { charging_ac: string | null; charging_dc: string | null; cooling: string | null; notes: string };
  repairs: { priority: string; repair: string; remarks: string; estimated_cost: string | null; sent_to_job_card: boolean }[];
  assessment: { overall: string | null; recommendation: string | null; budget: string | null; summary: string; odometer_km: number | null };
  customer_ack_name: string;
};
type Template = {
  version: number; ratings: Record<Rating, string>; overall: Record<string, string>; recommendation: Record<string, string>;
  disclaimer: string; sections: { key: string; title: string; items: { key: string; label: string }[] }[];
};
type Inspection = {
  id: string; number: string; kind: string; status: "draft" | "signed"; data: Data; version: number; signed_at: string | null;
  supersedes_id: string | null; inspector: string | null; customer_signature_url: string | null; inspector_signature_url: string | null;
  visit: { id: string; number: string; car_id: string; customer_id: string; buyer_id: string | null };
  car: { plate: string; make: string; model: string; year: number | null; fuel: string };
  snapshot: Snapshot;
  repairs_sent: Record<string, string>;
};

const RATING_STYLE: Record<Rating, string> = {
  good: "border-success bg-success text-accent-ink",
  average: "border-warning bg-warning text-accent-ink",
  attention: "border-error bg-error text-accent-ink",
  not_checked: "border-ink bg-ink text-surface",
};
const PANELS = ["Front bumper", "Bonnet", "Roof", "Boot", "Left front fender", "Right front fender", "Left front door",
  "Right front door", "Left rear door", "Right rear door", "Left quarter", "Right quarter", "Rear bumper"];
const KIND = { workshop: "Workshop inspection", delivery: "Delivery inspection", pre_purchase: "Pre-purchase inspection" } as Record<string, string>;

export default function InspectionPage() {
  return (
    <RequirePermission permission="visits">
      <Suspense fallback={<Card flush><SkeletonRows rows={8} /></Card>}>
        <InspectionLoader />
      </Suspense>
    </RequirePermission>
  );
}

function InspectionLoader() {
  const { id } = useParams<{ id: string }>();
  const ins = useApi<Inspection>(`/api/inspections/${id}`);
  const tpl = useApi<Template>("/api/inspection-template");
  if (ins.error || tpl.error) return <Card flush><ErrorState message={(ins.error ?? tpl.error)!} onRetry={() => { ins.reload(); tpl.reload(); }} /></Card>;
  if (!ins.data || !tpl.data) return <Card flush><SkeletonRows rows={8} /></Card>;
  return <InspectionForm key={`${ins.data.id}-${ins.data.status}`} initial={ins.data} tpl={tpl.data} reload={ins.reload} />;
}

function InspectionForm({ initial, tpl, reload }: { initial: Inspection; tpl: Template; reload: () => void }) {
  const router = useRouter();
  const [data, setData] = useState<Data>(initial.data);
  const [save, setSave] = useState<{ state: "saved" | "saving" | "dirty" | "error" | "conflict"; at?: string; message?: string }>({ state: "saved" });
  const version = useRef(initial.version);
  const readOnly = initial.status === "signed";
  const fuel = (readOnly ? initial.snapshot.car : initial.car).fuel;
  const showEv = fuel === "hybrid" || fuel === "ev";

  // Autosave: 1.2s after the last change; one request at a time.
  useEffect(() => {
    if (readOnly || save.state !== "dirty") return;
    const t = setTimeout(async () => {
      setSave({ state: "saving" });
      try {
        const r = await api<{ version: number; saved_at: string }>(`/api/inspections/${initial.id}`, { method: "PUT", json: { data, version: version.current } });
        version.current = r.version;
        setSave((s) => (s.state === "saving" ? { state: "saved", at: r.saved_at } : s));
      } catch (err) {
        setSave({ state: err instanceof ApiError && err.status === 409 ? "conflict" : "error", message: (err as Error).message });
      }
    }, 1200);
    return () => clearTimeout(t);
  }, [data, save.state, readOnly, initial.id]);

  // Warn before leaving with unsaved answers.
  useEffect(() => {
    const block = (e: BeforeUnloadEvent) => { if (save.state === "dirty" || save.state === "saving") e.preventDefault(); };
    window.addEventListener("beforeunload", block);
    return () => window.removeEventListener("beforeunload", block);
  }, [save.state]);

  function update(fn: (d: Data) => void) {
    if (readOnly) return;
    setData((d) => { const next = structuredClone(d); fn(next); return next; });
    setSave((s) => (s.state === "conflict" ? s : { state: "dirty" }));
  }

  const sections = [
    { id: "details", title: "Vehicle" },
    ...tpl.sections.slice(0, 1).map((s) => ({ id: s.key, title: "Body" })),
    { id: "paint", title: "Paint and tyres" },
    ...tpl.sections.slice(1).map((s) => ({ id: s.key, title: s.title.split(",")[0] })),
    { id: "scan", title: "Diagnostics" },
    ...(showEv ? [{ id: "ev", title: "Hybrid / EV" }] : []),
    { id: "repairs", title: "Repairs" },
    { id: "assessment", title: "Assessment" },
  ];

  return (
    <>
      <div className="mb-4 flex flex-wrap items-start justify-between gap-4">
        <div className="flex flex-wrap items-center gap-4">
          <Plate plate={initial.car.plate} />
          <div>
            <h1>{KIND[initial.kind]}</h1>
            <p className="text-muted">{initial.number} for {carTitle(initial.car)}, <Link href={`/visits/${initial.visit.id}`} className="underline">{initial.visit.number}</Link></p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {readOnly ? (
            <>
              <Badge tone="success">Signed {when(initial.signed_at!)}</Badge>
              <Link href={`/print/inspections/${initial.id}`} target="_blank" className="flex min-h-11 items-center rounded-control border border-rule-strong bg-surface px-4 font-medium hover:bg-paper-2">Print report</Link>
              <Button variant="secondary" onClick={async () => {
                try { router.push(`/inspections/${(await api<{ id: string }>(`/api/inspections/${initial.id}/revise`, { method: "POST" })).id}`); }
                catch (err) { alert((err as Error).message); }
              }}>Revise</Button>
            </>
          ) : <SaveStatus save={save} onReload={reload} />}
        </div>
      </div>
      {readOnly && <div className="mb-4"><Notice tone="success">This report is signed and can&apos;t be changed. A correction creates a new version that keeps this one.</Notice></div>}

      <nav aria-label="Sections" className="no-print sticky top-[57px] z-20 -mx-4 mb-4 overflow-x-auto bg-paper/85 px-4 py-2 backdrop-blur shell:top-0 sm:-mx-6 sm:px-6 shell:-mx-10 shell:px-10">
        <ul className="flex gap-1">
          {sections.map((s) => (
            <li key={s.id}><a href={`#${s.id}`} className="flex min-h-11 items-center whitespace-nowrap rounded-control px-3 text-sm text-ink-2 hover:bg-paper-3">{s.title}</a></li>
          ))}
        </ul>
      </nav>

      <div id="details" className="mb-4 scroll-mt-32">
        <VehiclePanel carId={initial.visit.car_id} ownerId={initial.visit.customer_id} buyerId={initial.visit.buyer_id}
                      frozen={readOnly ? initial.snapshot : null} onChange={reload} />
      </div>

      <fieldset disabled={readOnly} className="space-y-4">
        <RatedSection section={tpl.sections[0]} tpl={tpl} data={data} update={update} readOnly={readOnly} />

        <Section id="paint" title="Paint, accident check and tyres">
          <div className="space-y-5">
            <div className="grid gap-x-4 gap-y-3 sm:grid-cols-2 shell:grid-cols-3">
              {PANELS.map((p) => (
                <Field key={p} label={p}>
                  <Select value={data.paint.findings[p] ?? ""} onChange={(e) => update((d) => { if (e.target.value) d.paint.findings[p] = e.target.value; else delete d.paint.findings[p]; })}>
                    <option value="">Not measured</option>
                    {["original", "repaint", "filler", "replaced"].map((o) => <option key={o} value={o}>{o[0].toUpperCase() + o.slice(1)}</option>)}
                  </Select>
                </Field>
              ))}
            </div>
            <Field label="Paint-meter notes"><Input value={data.paint.notes} onChange={(e) => update((d) => { d.paint.notes = e.target.value; })} /></Field>
            <div>
              <p className="mb-1.5 text-sm font-medium text-ink-2">Accident and structure</p>
              <Segments value={data.paint.accident ?? ""} onChange={(v) => update((d) => { d.paint.accident = (v || null) as Data["paint"]["accident"]; })}
                        options={[{ value: "none", label: "No obvious structural repair" }, { value: "repair_signs", label: "Repair signs found" }]} />
            </div>
            <Field label="Chassis, apron, pillars and floor"><Input value={data.paint.structural_notes} onChange={(e) => update((d) => { d.paint.structural_notes = e.target.value; })} /></Field>
            <div className="grid gap-4 sm:grid-cols-2 shell:grid-cols-4">
              {(["fl", "fr", "rl", "rr"] as const).map((t) => (
                <div key={t} className="rounded-control border border-rule p-3">
                  <p className="mb-2 font-medium">{{ fl: "Front left", fr: "Front right", rl: "Rear left", rr: "Rear right" }[t]}</p>
                  <div className="grid grid-cols-2 gap-2">
                    <Field label="Tread mm"><Input type="number" inputMode="decimal" step="0.1" min={0} max={20} value={data.tyres[t].mm ?? ""} onChange={(e) => update((d) => { d.tyres[t].mm = e.target.value || null; })} /></Field>
                    <Field label="Life %"><Input type="number" inputMode="numeric" min={0} max={100} value={data.tyres[t].pct ?? ""} onChange={(e) => update((d) => { d.tyres[t].pct = e.target.value ? Number(e.target.value) : null; })} /></Field>
                  </div>
                </div>
              ))}
            </div>
            <div className="grid gap-5 sm:grid-cols-2">
              <Field label="Spare wheel"><Input value={data.tyres.spare} onChange={(e) => update((d) => { d.tyres.spare = e.target.value; })} /></Field>
              <div>
                <p className="mb-1.5 text-sm font-medium text-ink-2">Wheel damage</p>
                <Segments value={data.tyres.wheel_damage == null ? "" : data.tyres.wheel_damage ? "yes" : "no"}
                          onChange={(v) => update((d) => { d.tyres.wheel_damage = v === "yes"; })}
                          options={[{ value: "no", label: "No" }, { value: "yes", label: "Yes" }]} />
              </div>
            </div>
          </div>
        </Section>

        {tpl.sections.slice(1).map((s) => <RatedSection key={s.key} section={s} tpl={tpl} data={data} update={update} readOnly={readOnly} />)}

        <Section id="scan" title="Diagnostic scan">
          <div className="space-y-5">
            <div className="grid gap-5 sm:grid-cols-2 shell:grid-cols-4">
              <Field label="Diagnostic tool"><Input value={data.scan.tool} onChange={(e) => update((d) => { d.scan.tool = e.target.value; })} /></Field>
              <Field label="Scan date"><Input type="date" value={data.scan.scanned_on ?? ""} onChange={(e) => update((d) => { d.scan.scanned_on = e.target.value || null; })} /></Field>
              <Field label="12V battery at rest (V)"><Input type="number" inputMode="decimal" step="0.01" value={data.scan.battery_rest_v ?? ""} onChange={(e) => update((d) => { d.scan.battery_rest_v = e.target.value || null; })} /></Field>
              <Field label="12V battery running (V)"><Input type="number" inputMode="decimal" step="0.01" value={data.scan.battery_running_v ?? ""} onChange={(e) => update((d) => { d.scan.battery_running_v = e.target.value || null; })} /></Field>
            </div>
            <fieldset>
              <legend className="mb-1 text-sm font-medium text-ink-2">Warning lights on</legend>
              <div className="grid gap-x-4 sm:grid-cols-3 shell:grid-cols-5">
                {[["check_engine", "Check engine"], ["abs", "ABS"], ["airbag", "Airbag"], ["chassis", "Chassis"], ["other", "Other"]].map(([k, l]) => (
                  <Checkbox key={k} label={l} checked={data.scan.warning_lights.includes(k)}
                            onChange={(e) => update((d) => { d.scan.warning_lights = e.target.checked ? [...d.scan.warning_lights, k] : d.scan.warning_lights.filter((x) => x !== k); })} />
                ))}
              </div>
            </fieldset>
            <div className="grid gap-5 sm:grid-cols-2">
              <Field label="Other warning light"><Input value={data.scan.other_light} onChange={(e) => update((d) => { d.scan.other_light = e.target.value; })} /></Field>
              <Field label="Modules not communicating"><Input value={data.scan.modules_not_communicating} onChange={(e) => update((d) => { d.scan.modules_not_communicating = e.target.value; })} /></Field>
            </div>
            <div>
              <p className="mb-2 text-sm font-medium text-ink-2">Fault codes</p>
              <Rows
                rows={data.scan.dtcs} readOnly={readOnly}
                onAdd={() => update((d) => { d.scan.dtcs.push({ module: "", code: "", description: "", priority: "medium" }); d.scan.dtcs_stored = true; })}
                onRemove={(i) => update((d) => { d.scan.dtcs.splice(i, 1); })}
                render={(row, i) => (
                  <div className="grid flex-1 gap-2 sm:grid-cols-[8rem_8rem_minmax(0,1fr)_9rem]">
                    <Input aria-label="Module" placeholder="Module" value={row.module} onChange={(e) => update((d) => { d.scan.dtcs[i].module = e.target.value; })} />
                    <Input aria-label="Code" placeholder="P0300" value={row.code} className="num" onChange={(e) => update((d) => { d.scan.dtcs[i].code = e.target.value.toUpperCase(); })} />
                    <Input aria-label="Description" placeholder="Description / status" value={row.description} onChange={(e) => update((d) => { d.scan.dtcs[i].description = e.target.value; })} />
                    <Select aria-label="Priority" value={row.priority} onChange={(e) => update((d) => { d.scan.dtcs[i].priority = e.target.value; })}>
                      <option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option>
                    </Select>
                  </div>
                )}
                addLabel="Add fault code" empty="No fault codes recorded."
              />
            </div>
          </div>
        </Section>

        {showEv && (
          <Section id="ev" title="Hybrid / EV checks">
            <div className="grid gap-5 sm:grid-cols-3">
              {([["soc_pct", "Battery charge (SOC %)"], ["soh_pct", "Battery health (SOH %)"], ["capacity_kwh", "Capacity (kWh)"],
                 ["pack_voltage", "Pack voltage (V)"], ["cell_imbalance_mv", "Cell imbalance (mV)"], ["isolation_mohm", "Isolation (MΩ)"]] as const).map(([k, l]) => (
                <Field key={k} label={l}><Input type="number" inputMode="decimal" step="0.01" min={0} value={data.ev[k] ?? ""} onChange={(e) => update((d) => { d.ev[k] = e.target.value || null; })} /></Field>
              ))}
              {(["charging_ac", "charging_dc", "cooling"] as const).map((k) => (
                <div key={k}>
                  <p className="mb-1.5 text-sm font-medium text-ink-2">{{ charging_ac: "AC charging", charging_dc: "DC charging", cooling: "Battery cooling" }[k]}</p>
                  <Segments value={data.ev[k] ?? ""} onChange={(v) => update((d) => { d.ev[k] = v; })} options={[{ value: "ok", label: "OK" }, { value: "issue", label: "Issue" }]} />
                </div>
              ))}
              <div className="sm:col-span-3"><Field label="Hybrid / EV notes"><Input value={data.ev.notes} onChange={(e) => update((d) => { d.ev.notes = e.target.value; })} /></Field></div>
            </div>
          </Section>
        )}

        <Section id="repairs" title="Repairs and estimated work">
          <Rows
            rows={data.repairs} readOnly={readOnly}
            onAdd={() => update((d) => { d.repairs.push({ priority: "medium", repair: "", remarks: "", estimated_cost: null, sent_to_job_card: false }); })}
            onRemove={(i) => update((d) => { d.repairs.splice(i, 1); })}
            render={(row, i) => (
              <div className="grid flex-1 gap-2 sm:grid-cols-[9rem_minmax(0,1.4fr)_minmax(0,1fr)_9rem]">
                <Select aria-label="Priority" value={row.priority} onChange={(e) => update((d) => { d.repairs[i].priority = e.target.value; })}>
                  <option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option>
                </Select>
                <Input aria-label="Repair or part" placeholder="Repair or part needed" value={row.repair} onChange={(e) => update((d) => { d.repairs[i].repair = e.target.value; })} />
                <Input aria-label="Remarks" placeholder="Remarks" value={row.remarks} onChange={(e) => update((d) => { d.repairs[i].remarks = e.target.value; })} />
                <Input aria-label="Estimated cost" placeholder="PKR" type="number" inputMode="decimal" min={0} value={row.estimated_cost ?? ""} onChange={(e) => update((d) => { d.repairs[i].estimated_cost = e.target.value || null; })} />
              </div>
            )}
            addLabel="Add repair" empty="No repairs recommended."
          />
          <p className="mt-3 text-sm text-muted">After the report is signed, each repair can be sent to the job card from the panel below.</p>
        </Section>

        <Section id="assessment" title="Overall assessment">
          <div className="space-y-5">
            <div>
              <p className="mb-1.5 text-sm font-medium text-ink-2">Overall condition</p>
              <Segments value={data.assessment.overall ?? ""} onChange={(v) => update((d) => { d.assessment.overall = v; })}
                        options={Object.entries(tpl.overall).map(([value, label]) => ({ value, label }))} />
            </div>
            <div>
              <p className="mb-1.5 text-sm font-medium text-ink-2">Recommendation</p>
              <Segments value={data.assessment.recommendation ?? ""} onChange={(v) => update((d) => { d.assessment.recommendation = v; })}
                        options={Object.entries(tpl.recommendation).map(([value, label]) => ({ value, label }))} />
            </div>
            <div className="grid gap-5 sm:grid-cols-3">
              <Field label="Immediate repair budget (PKR)"><Input type="number" inputMode="decimal" min={0} value={data.assessment.budget ?? ""} onChange={(e) => update((d) => { d.assessment.budget = e.target.value || null; })} /></Field>
              <Field label="Odometer (km)"><Input type="number" inputMode="numeric" min={0} value={data.assessment.odometer_km ?? ""} onChange={(e) => update((d) => { d.assessment.odometer_km = e.target.value ? Number(e.target.value) : null; })} /></Field>
              <Field label={initial.kind === "pre_purchase" ? "Buyer's name (acknowledgement)" : "Customer's name (acknowledgement)"}>
                <Input value={data.customer_ack_name} onChange={(e) => update((d) => { d.customer_ack_name = e.target.value; })} />
              </Field>
            </div>
            <Field label="Inspector summary">
              <textarea rows={4} value={data.assessment.summary} maxLength={3000} onChange={(e) => update((d) => { d.assessment.summary = e.target.value; })}
                        className="w-full rounded-control border border-rule-strong bg-surface px-3 py-2.5 text-base focus-visible:border-accent disabled:opacity-80" />
            </Field>
            <p className="text-sm text-muted">{tpl.disclaimer}</p>
          </div>
        </Section>
      </fieldset>

      {readOnly && initial.data.repairs.length > 0 && <RepairHandoff inspection={initial} reload={reload} />}

      {!readOnly && <SignOff inspection={initial} data={data} saveState={save.state} version={version} onSigned={reload} />}
      {readOnly && (
        <Card title="Signatures">
          <div className="flex flex-wrap gap-8">
            {[["Inspector", initial.inspector_signature_url, initial.inspector], ["Customer", initial.customer_signature_url, data.customer_ack_name]].map(([l, url, name]) => (
              <figure key={l}>
                {/* eslint-disable-next-line @next/next/no-img-element -- authenticated API files */}
                {url ? <img src={url} alt={`${l} signature`} className="h-20 rounded-control border border-rule bg-surface" /> : <p className="text-muted">Not signed</p>}
                <figcaption className="mt-1 text-sm text-muted">{l}{name ? `: ${name}` : ""}</figcaption>
              </figure>
            ))}
          </div>
        </Card>
      )}
    </>
  );
}

function SaveStatus({ save, onReload }: { save: { state: string; at?: string; message?: string }; onReload: () => void }) {
  if (save.state === "conflict") return <span className="flex items-center gap-2"><Badge tone="error">Changed on another device</Badge><Button variant="secondary" onClick={onReload}>Reload</Button></span>;
  if (save.state === "error") return <Badge tone="error">Not saved: {save.message}</Badge>;
  return <span role="status" className="text-sm text-muted">{{ dirty: "Unsaved changes", saving: "Saving", saved: save.at ? `Saved ${new Date(save.at).toLocaleTimeString()}` : "All changes saved" }[save.state]}</span>;
}

function Section({ id, title, actions, children }: { id: string; title: string; actions?: ReactNode; children: ReactNode }) {
  return (
    <section id={id} className="scroll-mt-32 rounded-card bg-surface">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-rule px-4 py-3 shell:px-5">
        <h2>{title}</h2>{actions}
      </header>
      <div className="p-4 shell:p-5">{children}</div>
    </section>
  );
}

function RatedSection({ section, tpl, data, update, readOnly }:
  { section: Template["sections"][number]; tpl: Template; data: Data; update: (fn: (d: Data) => void) => void; readOnly: boolean }) {
  const unrated = section.items.filter((i) => !data.items[i.key] || data.items[i.key].rating === "not_checked").length;
  return (
    <Section id={section.key} title={section.title} actions={!readOnly && unrated > 0 && (
      <Button type="button" variant="secondary" onClick={() => update((d) => {
        for (const it of section.items) if (!d.items[it.key] || d.items[it.key].rating === "not_checked") d.items[it.key] = { rating: "good", note: d.items[it.key]?.note ?? "", photo_ids: d.items[it.key]?.photo_ids ?? [] };
        if (!d.bulk_marked.includes(section.key)) d.bulk_marked.push(section.key);
      })}>Mark the rest Good ({unrated})</Button>
    )}>
      <ul className="divide-y divide-rule">
        {section.items.map((item) => <ItemRow key={item.key} item={item} tpl={tpl} answer={data.items[item.key]} update={update} readOnly={readOnly} />)}
      </ul>
    </Section>
  );
}

function ItemRow({ item, tpl, answer, update, readOnly }:
  { item: { key: string; label: string }; tpl: Template; answer?: ItemAnswer; update: (fn: (d: Data) => void) => void; readOnly: boolean }) {
  const [open, setOpen] = useState(!!(answer?.note || answer?.photo_ids.length));
  const [photos, setPhotos] = useState<Uploaded[]>((answer?.photo_ids ?? []).map((id) => ({ id, url: `/api/attachments/${id}/file`, name: "Photo" })));
  const rating = answer?.rating ?? "not_checked";
  const set = (patch: Partial<ItemAnswer>) => update((d) => { d.items[item.key] = { ...(d.items[item.key] ?? { rating, note: "", photo_ids: [] }), ...patch }; });

  return (
    <li className="py-3 first:pt-0 last:pb-0">
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
        <span className="min-w-40 flex-1 font-medium">{item.label}</span>
        <div role="radiogroup" aria-label={item.label} className="grid min-w-0 flex-[2_1_17rem] grid-cols-4 gap-1">
          {(Object.keys(tpl.ratings) as Rating[]).map((r) => (
            <button key={r} type="button" role="radio" aria-checked={rating === r} onClick={() => set({ rating: r })}
                    className={`min-h-11 rounded-control border px-0.5 text-[0.8125rem] leading-tight font-medium transition-colors sm:px-1 sm:text-sm duration-(--dur-micro) active:duration-0 ${
                      rating === r ? RATING_STYLE[r] : "border-rule-strong bg-surface text-ink-2 hover:bg-paper active:bg-paper-3"}`}>
              {tpl.ratings[r]}
            </button>
          ))}
        </div>
        {!readOnly && <Button type="button" variant="ghost" aria-expanded={open} onClick={() => setOpen(!open)}>{open ? "Hide note" : "Note or photo"}</Button>}
      </div>
      {open && (
        <div className="mt-3 space-y-3">
          <Input aria-label={`${item.label} note`} placeholder="What you found" value={answer?.note ?? ""} onChange={(e) => set({ note: e.target.value })} />
          {!readOnly && <PhotoCapture value={photos} onChange={(p) => { setPhotos(p); set({ photo_ids: p.map((x) => x.id) }); }} note={`Inspection: ${item.label}`} label="Add photo" />}
        </div>
      )}
    </li>
  );
}

function Rows<T>({ rows, render, onAdd, onRemove, addLabel, empty, readOnly }:
  { rows: T[]; render: (row: T, i: number) => ReactNode; onAdd: () => void; onRemove: (i: number) => void; addLabel: string; empty: string; readOnly: boolean }) {
  return (
    <div className="space-y-2">
      {!rows.length && <p className="text-muted">{empty}</p>}
      {rows.map((row, i) => (
        <div key={i} className="flex flex-wrap items-start gap-2 rounded-control border border-rule p-2 sm:flex-nowrap sm:border-0 sm:p-0">
          {render(row, i)}
          {!readOnly && <Button type="button" variant="ghost" onClick={() => onRemove(i)}>Remove</Button>}
        </div>
      ))}
      {!readOnly && <Button type="button" variant="secondary" onClick={onAdd}>{addLabel}</Button>}
    </div>
  );
}

function SignOff({ inspection, data, saveState, version, onSigned }:
  { inspection: Inspection; data: Data; saveState: string; version: React.RefObject<number>; onSigned: () => void }) {
  const [inspectorSig, setInspectorSig] = useState<Blob | null>(null);
  const [customerSig, setCustomerSig] = useState<Blob | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const missing = [!data.assessment.overall && "the overall condition", !data.assessment.recommendation && "the recommendation", !inspectorSig && "the inspector's signature"].filter(Boolean);

  async function sign() {
    setBusy(true);
    setError(null);
    try {
      const ins = await upload(inspectorSig!, "inspector-signature.png", `Inspector signature ${inspection.number}`);
      const cust = customerSig ? await upload(customerSig, "customer-signature.png", `Customer signature ${inspection.number}`) : null;
      await api(`/api/inspections/${inspection.id}/sign`, { method: "POST", json: { inspector_signature_id: ins.id, customer_signature_id: cust?.id ?? null, version: version.current } });
      onSigned();
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  return (
    <div className="mt-4">
      <Card title="Sign the report">
        <div className="grid gap-6 sm:grid-cols-2">
          <SignaturePad label="Inspector" onChange={setInspectorSig} />
          <SignaturePad label={inspection.kind === "pre_purchase" ? "Buyer (optional)" : "Customer (optional)"} onChange={setCustomerSig} />
        </div>
        <div className="mt-5 space-y-3">
          {missing.length > 0 && <p className="text-sm text-muted">Still needed: {missing.join(", ")}.</p>}
          <p className="text-sm text-muted">Items left unrated are recorded as Not checked. Once signed, the report is locked.</p>
          <Notice>{error}</Notice>
          <Button onClick={sign} disabled={busy || missing.length > 0 || saveState !== "saved"}>
            {busy ? "Signing" : saveState !== "saved" ? "Saving first" : "Sign and lock the report"}
          </Button>
        </div>
      </Card>
    </div>
  );
}


/** Send a signed report's recommended repairs to the visit's job card, one at a time, as a labour code or a part. */
function RepairHandoff({ inspection, reload }: { inspection: Inspection; reload: () => void }) {
  const { can } = useSession();
  const [picking, setPicking] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  if (!can("job-cards")) return null;

  async function send(index: number, p: Pick) {
    setError(null);
    try {
      await api(`/api/inspections/${inspection.id}/repairs/${index}/send`, { method: "POST", json: {
        kind: p.kind, labour_code_id: p.kind === "labour" ? p.id : null, item_id: p.kind === "part" ? p.id : null, qty: "1" } });
      setPicking(null);
      reload();
    } catch (err) {
      setError((err as Error).message);
    }
  }
  return (
    <div className="mt-4">
      <Card title="Send repairs to the job card">
        <p className="mb-4 text-sm text-muted">Each repair becomes a labour code or a part on the visit&apos;s job card. The estimate here becomes the proposed price on the quotation.</p>
        <ul className="space-y-4">
          {inspection.data.repairs.map((r, i) => {
            const jobCard = inspection.repairs_sent[String(i)];
            return (
              <li key={i} className="space-y-2">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="font-medium">{r.repair || "Unnamed repair"} <Badge tone={r.priority === "high" ? "error" : r.priority === "medium" ? "warning" : "neutral"}>{r.priority}</Badge></p>
                    <p className="text-sm text-muted">{r.estimated_cost ? `Estimate ${money(r.estimated_cost)}` : "No estimate"}{r.remarks ? `. ${r.remarks}` : ""}</p>
                  </div>
                  {jobCard ? <Link href={`/job-cards/${jobCard}`} className="text-sm underline">On the job card</Link>
                    : picking === i ? <Button variant="secondary" onClick={() => setPicking(null)}>Cancel</Button>
                    : <Button variant="secondary" onClick={() => setPicking(i)}>Send to job card</Button>}
                </div>
                {picking === i && <div><CatalogPicker onPick={(p) => send(i, p)} /></div>}
              </li>
            );
          })}
        </ul>
        {error && <div className="mt-4"><Notice>{error}</Notice></div>}
      </Card>
    </div>
  );
}
