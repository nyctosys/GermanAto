"use client";

import { useParams } from "next/navigation";
import { Suspense, useState, type FormEvent } from "react";
import { DayBadge, DAY, EmployeeForm, type Employee, WEEKDAYS } from "@/components/hr";
import { ReasonForm } from "@/components/purchasing";
import { Segments, useQueryParam } from "@/components/search";
import { RequirePermission } from "@/components/shell";
import { Badge, Button, Card, ErrorState, Field, Input, Notice, SkeletonRows } from "@/components/ui";
import { api, useApi } from "@/lib/api";
import { day, money, phone } from "@/lib/format";
import { useLiveErrors } from "@/lib/form";
import { issuesToFieldErrors, markSchema, punchSchema } from "@/lib/schemas";

type Month = {
  month: string; employee: Employee; present: number; late: number; absent: number; paid_leave: number; unpaid_leave: number; off: number;
  incomplete: number; working_days: number; hours: string;
  days: { day: string; status: string; first: string | null; last: string | null; hours: string; punches: number; note: string }[];
  punches: { id: string; at: string; source: string; reason: string; voided: boolean }[];
};
const time = (iso: string | null) => (iso ? new Date(iso).toLocaleTimeString("en-PK", { hour: "numeric", minute: "2-digit" }) : "");

export default function EmployeePage() {
  return (
    <RequirePermission permission="hr">
      <Suspense fallback={<Card flush><SkeletonRows rows={6} /></Card>}>
        <View />
      </Suspense>
    </RequirePermission>
  );
}

function View() {
  const { id } = useParams<{ id: string }>();
  const [monthParam, setMonth] = useQueryParam("month");
  const month = monthParam || new Date().toLocaleDateString("en-CA").slice(0, 7);
  const data = useApi<Month>(`/api/attendance/${id}?month=${month}`);
  const [editing, setEditing] = useState(false);
  const [panel, setPanel] = useState<"punch" | "mark" | null>(null);
  const [voiding, setVoiding] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (data.error) return <Card flush><ErrorState message={data.error} onRetry={data.reload} /></Card>;
  if (!data.data) return <Card flush><SkeletonRows rows={6} /></Card>;
  const d = data.data, e = d.employee;

  async function voidPunch(reason: string) {
    try { await api(`/api/attendance/punches/${voiding}/void`, { method: "POST", json: { reason } }); setVoiding(null); data.reload(); }
    catch (err) { setError((err as Error).message); }
  }

  return (
    <>
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1>{e.full_name}</h1>
          <p className="text-muted">{e.number}{e.title ? `, ${e.title}` : ""}{e.is_active ? "" : ", no longer working here"}</p>
        </div>
        {!editing && <Button variant="secondary" onClick={() => setEditing(true)}>Edit</Button>}
      </div>
      {editing && <div className="mb-4"><Card title="Edit employee"><EmployeeForm employee={e} onCancel={() => setEditing(false)} onSaved={() => { setEditing(false); data.reload(); }} /></Card></div>}

      <div className="grid gap-4 shell:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        <div className="space-y-4">
          <Card title="Attendance" actions={<Input type="month" aria-label="Month" value={month} max={new Date().toLocaleDateString("en-CA").slice(0, 7)} onChange={(ev) => setMonth(ev.target.value)} className="min-h-11 rounded-control border border-rule-strong bg-surface px-3" />}>
            <dl className="mb-4 grid grid-cols-2 gap-4 sm:grid-cols-4">
              {[["Present", d.present], ["Late", d.late], ["Absent", d.absent], ["Leave", d.paid_leave + d.unpaid_leave]].map(([l, v]) => (
                <div key={l}><dt className="text-sm text-muted">{l}</dt><dd className="num text-lg">{v}</dd></div>
              ))}
            </dl>
            <p className="text-sm text-muted">{d.working_days} working days, {Number(d.hours).toFixed(1)} hours recorded.</p>
          </Card>
          <Card title="Day by day" flush>
            <ul>
              {[...d.days].reverse().map((x) => (
                <li key={x.day} className="flex flex-wrap items-center justify-between gap-3 border-t border-rule px-4 py-2.5 first:border-t-0 shell:px-5">
                  <span><span className="font-medium">{day(x.day)}</span>{x.note && <span className="block text-sm text-muted">{x.note}</span>}</span>
                  <span className="flex flex-wrap items-center gap-3">
                    {x.first && <span className="num text-sm text-muted">{time(x.first)}{x.punches > 1 ? ` to ${time(x.last)}` : ""}</span>}
                    <DayBadge status={x.status} />
                  </span>
                </li>
              ))}
            </ul>
          </Card>
        </div>

        <div className="space-y-4">
          <Card title="Details">
            <dl className="space-y-3">
              {[["Salary", money(e.monthly_salary)], ["Phone", e.phone ? phone(e.phone) : ""], ["CNIC", e.cnic], ["Device number", e.device_pin],
                ["Shift", `${e.shift_start.slice(0, 5)} to ${e.shift_end.slice(0, 5)}, off on ${WEEKDAYS[e.weekly_off]}`], ["Joined", day(e.joined_on)], ["Login", e.username ?? ""], ["Notes", e.notes]].map(([l, t]) => (
                <div key={l}><dt className="text-sm text-muted">{l}</dt><dd className={t ? "" : "text-muted"}>{t || "None"}</dd></div>
              ))}
            </dl>
          </Card>
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" onClick={() => setPanel("punch")}>Add a missed punch</Button>
            <Button variant="secondary" onClick={() => setPanel("mark")}>Mark a leave day</Button>
          </div>
          {panel === "punch" && <PunchForm id={e.id} onDone={() => { setPanel(null); data.reload(); }} onCancel={() => setPanel(null)} />}
          {panel === "mark" && <MarkForm id={e.id} onDone={() => { setPanel(null); data.reload(); }} onCancel={() => setPanel(null)} />}
          {voiding && <ReasonForm title="Void this punch" hint="It stays on record, struck through, and no longer counts." confirm="Void it" busy={false} onCancel={() => setVoiding(null)} onSubmit={voidPunch} />}
          {error && <Notice>{error}</Notice>}
          <Card title="Punches this month" flush>
            {!d.punches.length ? <p className="px-4 py-4 text-muted shell:px-5">None.</p> : (
              <ul>
                {d.punches.map((p) => (
                  <li key={p.id} className="flex flex-wrap items-center justify-between gap-3 border-t border-rule px-4 py-2.5 first:border-t-0 shell:px-5">
                    <span className={p.voided ? "text-muted line-through" : ""}>
                      <span className="num">{new Date(p.at).toLocaleString("en-PK", { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" })}</span>
                      <span className="block text-sm text-muted">{p.source === "device" ? "From the device" : `Entered by hand: ${p.reason}`}</span>
                    </span>
                    {p.source === "manual" && !p.voided ? <Button variant="danger" onClick={() => setVoiding(p.id)}>Void</Button> : p.voided ? <Badge>Voided</Badge> : null}
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      </div>
    </>
  );
}

function PunchForm({ id, onDone, onCancel }: { id: string; onDone: () => void; onCancel: () => void }) {
  const [at, setAt] = useState("");
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const { errors, activate, live } = useLiveErrors({ punched_at: at, reason }, (v) => {
    const r = punchSchema.safeParse(v);
    return r.success ? {} : issuesToFieldErrors(r.error.issues);
  });
  async function submit(e: FormEvent) {
    e.preventDefault();
    activate();
    const r = punchSchema.safeParse({ punched_at: at, reason });
    if (!r.success) return;
    try { await api("/api/attendance/punches", { method: "POST", json: { employee_id: id, punched_at: at, reason: r.data.reason } }); onDone(); }
    catch (err) { setError((err as Error).message); }
  }
  return (
    <Card title="Add a missed punch">
      <form noValidate onSubmit={submit} className="space-y-4" {...live}>
        <Field label="Date and time" error={errors.punched_at}><Input type="datetime-local" value={at} onChange={(e) => setAt(e.target.value)} /></Field>
        <Field label="Why" error={errors.reason} hint="For example: the finger scan failed at the door."><Input value={reason} onChange={(e) => setReason(e.target.value)} maxLength={500} /></Field>
        <Notice>{error}</Notice>
        <div className="flex flex-wrap gap-2"><Button type="submit">Add it</Button><Button type="button" variant="danger" onClick={onCancel}>Cancel</Button></div>
      </form>
    </Card>
  );
}

function MarkForm({ id, onDone, onCancel }: { id: string; onDone: () => void; onCancel: () => void }) {
  const [dayV, setDayV] = useState("");
  const [kind, setKind] = useState("paid_leave");
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const { errors, activate, live } = useLiveErrors({ day: dayV, kind, reason }, (v) => {
    const r = markSchema.safeParse(v);
    return r.success ? {} : issuesToFieldErrors(r.error.issues);
  });
  async function submit(e: FormEvent) {
    e.preventDefault();
    activate();
    const r = markSchema.safeParse({ day: dayV, kind, reason });
    if (!r.success) return;
    try { await api("/api/attendance/marks", { method: "POST", json: { employee_id: id, ...r.data } }); onDone(); }
    catch (err) { setError((err as Error).message); }
  }
  return (
    <Card title="Mark a leave day">
      <form noValidate onSubmit={submit} className="space-y-4" {...live}>
        <Field label="Day" error={errors.day}><Input type="date" value={dayV} onChange={(e) => setDayV(e.target.value)} /></Field>
        <Segments value={kind} onChange={setKind} options={[{ value: "paid_leave", label: DAY.paid_leave[0] }, { value: "unpaid_leave", label: DAY.unpaid_leave[0] }]} />
        <Field label="Why" error={errors.reason}><Input value={reason} onChange={(e) => setReason(e.target.value)} maxLength={500} /></Field>
        <p className="text-sm text-muted">Unpaid leave costs a day&apos;s pay in payroll; paid leave does not.</p>
        <Notice>{error}</Notice>
        <div className="flex flex-wrap gap-2"><Button type="submit">Mark it</Button><Button type="button" variant="danger" onClick={onCancel}>Cancel</Button></div>
      </form>
    </Card>
  );
}
