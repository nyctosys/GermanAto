"use client";

import Link from "next/link";
import { Suspense, useState, type FormEvent } from "react";
import { MarkForm, PunchForm } from "@/components/hr";
import { useQueryParam } from "@/components/search";
import { RequirePermission } from "@/components/shell";
import { Badge, Button, Card, EmptyState, ErrorState, Field, Input, Notice, PageHeader, Select, SkeletonRows } from "@/components/ui";
import { api, useApi } from "@/lib/api";
import { when } from "@/lib/format";
import { useLiveErrors } from "@/lib/form";
import { deviceSchema, issuesToFieldErrors } from "@/lib/schemas";

type Row = { employee: { id: string; number: string; full_name: string; title: string }; present: number; late: number; absent: number; paid_leave: number; unpaid_leave: number; working_days: number; hours: string };
type Device = { id: string; serial: string; name: string; is_active: boolean; has_secret: boolean; last_seen_at: string | null; version: number; secret?: string };

export default function AttendancePage() {
  return (
    <RequirePermission permission="hr">
      <PageHeader title="Attendance" description="Who came in, who was late and who was away, worked out from the attendance device." />
      <Suspense fallback={<Card flush><SkeletonRows /></Card>}>
        <Body />
      </Suspense>
    </RequirePermission>
  );
}

function Body() {
  const [monthParam, setMonth] = useQueryParam("month");
  const now = new Date().toLocaleDateString("en-CA").slice(0, 7);
  const month = monthParam || now;
  const list = useApi<{ month: string; employees: Row[] }>(`/api/attendance?month=${month}`);
  return (
    <div className="space-y-4">
      <Card title="This month" actions={<Input type="month" aria-label="Month" value={month} max={now} onChange={(e) => setMonth(e.target.value)} className="min-h-11 rounded-control border border-rule-strong bg-surface px-3" />} flush>
        {list.error ? <ErrorState message={list.error} onRetry={list.reload} /> : !list.data ? <SkeletonRows />
          : !list.data.employees.length ? <EmptyState title="Nobody was employed this month">Add people under Employees.</EmptyState> : (
            <table className="table-stack w-full">
              <thead><tr className="text-left text-sm text-muted">
                <th className="px-4 py-2 font-normal shell:px-5">Employee</th><th className="px-4 py-2 text-right font-normal">Present</th><th className="px-4 py-2 text-right font-normal">Late</th>
                <th className="px-4 py-2 text-right font-normal">Absent</th><th className="px-4 py-2 text-right font-normal">Leave</th><th className="px-4 py-2 text-right font-normal shell:pr-5">Hours</th>
              </tr></thead>
              <tbody>
                {list.data.employees.map((r) => (
                  <tr key={r.employee.id} className="border-t border-rule">
                    <td className="px-4 py-3 shell:px-5 max-sm:px-0"><Link href={`/employees/${r.employee.id}?month=${month}`} className="font-medium underline">{r.employee.full_name}</Link><span className="block text-sm text-muted">{r.working_days} working days</span></td>
                    <td data-label="Present" className="num px-4 py-3 text-right max-sm:px-0">{r.present}</td>
                    <td data-label="Late" className="num px-4 py-3 text-right max-sm:px-0">{r.late}</td>
                    <td data-label="Absent" className={`num px-4 py-3 text-right max-sm:px-0 ${r.absent ? "text-error" : ""}`}>{r.absent}</td>
                    <td data-label="Leave" className="num px-4 py-3 text-right max-sm:px-0">{r.paid_leave + r.unpaid_leave}</td>
                    <td data-label="Hours" className="num px-4 py-3 text-right shell:pr-5 max-sm:px-0">{Number(r.hours).toFixed(1)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
      </Card>
      {list.data && list.data.employees.length > 0 && <ByHand people={list.data.employees.map((r) => r.employee)} onDone={list.reload} />}
      <div className="grid gap-4 shell:grid-cols-2">
        <Devices />
        <Unmatched />
      </div>
    </div>
  );
}

/** Fix a day when the device got it wrong: a missed punch, a leave day, or a day marked present (8 hours). */
function ByHand({ people, onDone }: { people: Row["employee"][]; onDone: () => void }) {
  const [who, setWho] = useState("");
  const [mode, setMode] = useState<"punch" | "mark" | null>(null);
  const done = () => { setMode(null); onDone(); };
  return (
    <Card title="Add or fix a day by hand">
      <div className="space-y-4">
        <Field label="Employee"><Select value={who} onChange={(e) => { setWho(e.target.value); setMode(null); }}><option value="">Choose an employee</option>{people.map((p) => <option key={p.id} value={p.id}>{p.full_name}</option>)}</Select></Field>
        {who && !mode && (
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" onClick={() => setMode("punch")}>Add a missed punch</Button>
            <Button variant="secondary" onClick={() => setMode("mark")}>Mark present or leave</Button>
          </div>
        )}
        {who && mode === "punch" && <PunchForm id={who} onDone={done} onCancel={() => setMode(null)} />}
        {who && mode === "mark" && <MarkForm id={who} onDone={done} onCancel={() => setMode(null)} />}
      </div>
    </Card>
  );
}

function Unmatched() {
  const list = useApi<{ device_pin: string; punches: number; last: string }[]>("/api/attendance/unmatched");
  return (
    <Card title="Unmatched device numbers" flush>
      {list.error ? <ErrorState message={list.error} onRetry={list.reload} /> : !list.data ? <SkeletonRows rows={2} />
        : !list.data.length ? <p className="px-4 py-4 text-muted shell:px-5">Every punch belongs to an employee.</p> : (
          <ul>
            {list.data.map((u) => (
              <li key={u.device_pin} className="flex flex-wrap items-center justify-between gap-3 border-t border-rule px-4 py-3 first:border-t-0 shell:px-5">
                <span><span className="font-medium">Number {u.device_pin}</span><span className="block text-sm text-muted">{u.punches} punches, last {when(u.last)}</span></span>
                <Link href="/employees" className="text-sm underline">Give it to an employee</Link>
              </li>
            ))}
          </ul>
        )}
      <p className="border-t border-rule px-4 py-3 text-sm text-muted shell:px-5">Put the number in the employee&apos;s &ldquo;Number on the attendance device&rdquo; and these punches are claimed automatically.</p>
    </Card>
  );
}

function Devices() {
  const list = useApi<Device[]>("/api/attendance-devices");
  const [adding, setAdding] = useState(false);
  const [secret, setSecret] = useState<{ name: string; value: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [logOf, setLogOf] = useState<string | null>(null);

  async function toggle(d: Device) {
    setError(null);
    try { await api(`/api/attendance-devices/${d.id}`, { method: "PUT", json: { name: d.name, is_active: !d.is_active, version: d.version } }); list.reload(); }
    catch (err) { setError((err as Error).message); }
  }
  async function rotate(d: Device) {
    setError(null);
    try { const r = await api<Device>(`/api/attendance-devices/${d.id}/secret`, { method: "POST" }); setSecret({ name: d.name, value: r.secret! }); list.reload(); }
    catch (err) { setError((err as Error).message); }
  }
  return (
    <Card title="Attendance devices" actions={!adding && <Button variant="secondary" onClick={() => setAdding(true)}>Register a device</Button>} flush>
      {adding && <div className="border-b border-rule p-4 shell:px-5"><DeviceForm onCancel={() => setAdding(false)} onDone={(d) => { setAdding(false); if (d.secret) setSecret({ name: d.name, value: d.secret }); list.reload(); }} /></div>}
      {secret && (
        <div className="space-y-2 border-b border-rule p-4 shell:px-5">
          <Notice tone="warning">{`Secret for ${secret.name}. It is shown only now. Copy it into the device's server address as ?token=…`}</Notice>
          <code className="block break-all rounded-control bg-paper-3 px-3 py-2 text-sm">{secret.value}</code>
          <Button variant="secondary" onClick={() => setSecret(null)}>I have copied it</Button>
        </div>
      )}
      {error && <div className="p-4"><Notice>{error}</Notice></div>}
      {list.error ? <ErrorState message={list.error} onRetry={list.reload} /> : !list.data ? <SkeletonRows rows={2} />
        : !list.data.length ? <p className="px-4 py-4 text-muted shell:px-5">No devices registered. A terminal that isn&apos;t registered is refused.</p> : (
          <ul>
            {list.data.map((d) => (
              <li key={d.id} className="space-y-2 border-t border-rule px-4 py-3 first:border-t-0 shell:px-5">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <span className="min-w-0"><span className="block font-medium">{d.name} {!d.is_active && <Badge>Switched off</Badge>}</span>
                    <span className="block text-sm text-muted">Serial {d.serial}. {d.last_seen_at ? `Last heard ${when(d.last_seen_at)}` : "Never heard from"}. {d.has_secret ? "Needs a secret." : "No secret."}</span></span>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button variant="ghost" onClick={() => toggle(d)}>{d.is_active ? "Switch off" : "Switch on"}</Button>
                  <Button variant="ghost" onClick={() => rotate(d)}>{d.has_secret ? "New secret" : "Add a secret"}</Button>
                  <Button variant="ghost" onClick={() => setLogOf(logOf === d.id ? null : d.id)}>{logOf === d.id ? "Hide log" : "Activity log"}</Button>
                </div>
                {logOf === d.id && <DeviceLog id={d.id} />}
              </li>
            ))}
          </ul>
        )}
    </Card>
  );
}

/** The last things a terminal did, for working out why it does not seem to work. */
function DeviceLog({ id }: { id: string }) {
  const log = useApi<{ id: string; at: string; event: string; detail: string }[]>(`/api/attendance-devices/${id}/log`);
  if (log.error) return <Notice>{log.error}</Notice>;
  if (!log.data) return <SkeletonRows rows={2} />;
  if (!log.data.length) return <p className="text-sm text-muted">Nothing yet. Punches received and refused calls show here.</p>;
  return (
    <ul className="space-y-1 rounded-control bg-paper-2 p-3 text-sm">
      {log.data.map((r) => (
        <li key={r.id} className="flex flex-wrap gap-x-3"><span className="num text-muted">{when(r.at)}</span><Badge tone={r.event === "refused" ? "error" : "success"}>{r.event === "refused" ? "Refused" : "Punches"}</Badge><span>{r.detail}</span></li>
      ))}
    </ul>
  );
}

function DeviceForm({ onDone, onCancel }: { onDone: (d: Device) => void; onCancel: () => void }) {
  const [serial, setSerial] = useState("");
  const [name, setName] = useState("");
  const [useSecret, setUseSecret] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { errors, activate, live } = useLiveErrors({ serial, name }, (v) => {
    const r = deviceSchema.safeParse(v);
    return r.success ? {} : issuesToFieldErrors(r.error.issues);
  });
  async function submit(e: FormEvent) {
    e.preventDefault();
    activate();
    const r = deviceSchema.safeParse({ serial, name });
    if (!r.success) return;
    try { onDone(await api<Device>("/api/attendance-devices", { method: "POST", json: { ...r.data, use_secret: useSecret } })); }
    catch (err) { setError((err as Error).message); }
  }
  return (
    <form noValidate onSubmit={submit} className="space-y-4" {...live}>
      <Field label="Serial number" error={errors.serial} hint="Printed on the device, or in its menu under System information."><Input value={serial} onChange={(e) => setSerial(e.target.value)} autoFocus maxLength={40} /></Field>
      <Field label="Name" error={errors.name}><Input value={name} onChange={(e) => setName(e.target.value)} maxLength={80} placeholder="Front door" /></Field>
      <label className="flex min-h-11 cursor-pointer items-center gap-3"><input type="checkbox" checked={useSecret} onChange={(e) => setUseSecret(e.target.checked)} className="size-5 accent-accent" /><span>Require a secret (recommended)</span></label>
      <Notice>{error}</Notice>
      <div className="flex flex-wrap gap-2"><Button type="submit">Register</Button><Button type="button" variant="danger" onClick={onCancel}>Cancel</Button></div>
    </form>
  );
}
