"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { Suspense, useState } from "react";
import { DayBadge, EmployeeForm, type Employee, WEEKDAYS } from "@/components/hr";
import { ReasonForm } from "@/components/purchasing";
import { useQueryParam } from "@/components/search";
import { RequirePermission } from "@/components/shell";
import { Badge, Button, Card, ErrorState, Input, Notice, SkeletonRows } from "@/components/ui";
import { api, useApi } from "@/lib/api";
import { day, money, phone } from "@/lib/format";

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
                ["Shift", `${e.shift_start.slice(0, 5)} to ${e.shift_end.slice(0, 5)}, off on ${e.days_off.map((d) => WEEKDAYS[d]).join(" and ") || "no fixed day"}`], ["Joined", day(e.joined_on)], ["Login", e.username ?? ""], ["Notes", e.notes]].map(([l, t]) => (
                <div key={l}><dt className="text-sm text-muted">{l}</dt><dd className={t ? "" : "text-muted"}>{t || "None"}</dd></div>
              ))}
            </dl>
          </Card>
          <Link href="/attendance" className="inline-flex min-h-11 items-center rounded-control border border-rule-strong bg-surface px-4 font-medium hover:bg-paper">Add a missed punch, leave or present day in Attendance</Link>
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
