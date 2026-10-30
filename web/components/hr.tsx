"use client";

import { useRef, useState, type FormEvent } from "react";
import { Segments } from "@/components/search";
import { Badge, Button, Card, Field, Input, Notice, Select } from "@/components/ui";
import { api, useApi } from "@/lib/api";
import { phone } from "@/lib/format";
import { useFormErrors } from "@/lib/form";
import { useLiveErrors } from "@/lib/form";
import { employeeSchema, issuesToFieldErrors, markSchema, parseForm, punchSchema } from "@/lib/schemas";

export type Employee = {
  id: string; number: string; full_name: string; title: string; phone: string; cnic: string; user_id: string | null; username: string | null;
  device_pin: string; monthly_salary: string; shift_start: string; shift_end: string; days_off: number[]; joined_on: string; left_on: string | null;
  notes: string; is_active: boolean; version: number;
};

export const WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

export const DAY: Record<string, [string, "neutral" | "success" | "warning" | "error" | "accent"]> = {
  present: ["Present", "success"], late: ["Late", "warning"], incomplete: ["One punch only", "warning"], absent: ["Absent", "error"],
  off: ["Day off", "neutral"], paid_leave: ["Paid leave", "accent"], unpaid_leave: ["Unpaid leave", "neutral"],
};

/** Pick any number of weekly days off. Posts them as one comma list under `name`. */
export function DaysOff({ name, defaultValue }: { name: string; defaultValue: number[] }) {
  const [days, setDays] = useState(defaultValue);
  return (
    <fieldset className="flex flex-wrap gap-2">
      <legend className="sr-only">Weekly days off</legend>
      {WEEKDAYS.map((d, i) => (
        <label key={d} className={`flex min-h-11 cursor-pointer items-center gap-2 rounded-control border px-3 ${days.includes(i) ? "border-primary bg-paper-3 font-medium" : "border-rule-strong bg-surface"}`}>
          <input type="checkbox" className="size-4 accent-primary" checked={days.includes(i)} onChange={(e) => setDays(e.target.checked ? [...days, i].sort() : days.filter((x) => x !== i))} />
          {d.slice(0, 3)}
        </label>
      ))}
      <input type="hidden" name={name} value={days.join(",")} />
    </fieldset>
  );
}
export const DayBadge = ({ status }: { status: string }) => <Badge tone={DAY[status][1]}>{DAY[status][0]}</Badge>;

export const RUN: Record<string, [string, "neutral" | "success" | "warning" | "accent"]> = { draft: ["Draft", "warning"], approved: ["Approved, to be paid", "accent"], paid: ["Paid", "success"] };

const hhmm = (t: string) => t.slice(0, 5);

/** Add or edit an employee. A device number claims the punches already received for it. */
export function EmployeeForm({ employee, onSaved, onCancel }: { employee?: Employee; onSaved: (e: Employee) => void; onCancel: () => void }) {
  const logins = useApi<{ id: string; username: string; full_name: string }[]>("/api/employee-logins");
  const { errors, setErrors, live, applyApi } = useFormErrors(employeeSchema);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const form = useRef<HTMLFormElement>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    const { data, errors } = parseForm(employeeSchema, form.current!);
    setErrors(errors ?? {});
    if (!data) return;
    setBusy(true);
    setError(null);
    try {
      const body = { ...data, notes: data.notes };
      const saved = employee
        ? await api<Employee>(`/api/employees/${employee.id}`, { method: "PUT", json: { ...body, is_active: new FormData(form.current!).get("is_active") === "on", version: employee.version } })
        : await api<Employee>("/api/employees", { method: "POST", json: body });
      setBusy(false);
      onSaved(saved);
    } catch (err) {
      setError(applyApi(err));
      setBusy(false);
    }
  }

  return (
    <form ref={form} noValidate onSubmit={submit} className="grid gap-5 sm:grid-cols-2 shell:grid-cols-3" {...live}>
      <Field required label="Full name" error={errors.full_name}><Input name="full_name" defaultValue={employee?.full_name} required maxLength={120} autoComplete="off" autoFocus /></Field>
      <Field label="Job title (optional)" error={errors.title}><Input name="title" defaultValue={employee?.title} maxLength={80} placeholder="Technician" /></Field>
      <Field label="Phone (optional)" error={errors.phone}><Input name="phone" defaultValue={employee ? phone(employee.phone) : ""} inputMode="tel" placeholder="+92 300 1234567" /></Field>
      <Field required label="CNIC" error={errors.cnic} hint="13 digits"><Input name="cnic" defaultValue={employee?.cnic} inputMode="numeric" /></Field>
      <Field required label="Monthly salary (Rs)" error={errors.monthly_salary}><Input name="monthly_salary" inputMode="decimal" defaultValue={employee ? String(Number(employee.monthly_salary)) : ""} /></Field>
      <Field label="Number on the attendance device" error={errors.device_pin} hint="Claims punches already received for it."><Input name="device_pin" defaultValue={employee?.device_pin} maxLength={20} inputMode="numeric" /></Field>
      <Field required label="Shift starts" error={errors.shift_start}><Input name="shift_start" type="time" defaultValue={hhmm(employee?.shift_start ?? "09:00")} /></Field>
      <Field required label="Shift ends" error={errors.shift_end}><Input name="shift_end" type="time" defaultValue={hhmm(employee?.shift_end ?? "18:00")} /></Field>
      <Field label="Weekly days off" error={errors.days_off} hint="Tick every day this person does not work."><DaysOff name="days_off" defaultValue={employee?.days_off ?? [6]} /></Field>
      <Field required label="Joined on" error={errors.joined_on}><Input name="joined_on" type="date" defaultValue={employee?.joined_on} /></Field>
      {employee && <Field label="Left on (if they left)" error={errors.left_on}><Input name="left_on" type="date" defaultValue={employee.left_on ?? ""} /></Field>}
      <Field label="Linked login (optional)" error={errors.user_id}>
        <Select name="user_id" defaultValue={employee?.user_id ?? ""}>
          <option value="">No login</option>
          {employee?.user_id && <option value={employee.user_id}>{employee.username}</option>}
          {logins.data?.map((u) => <option key={u.id} value={u.id}>{u.full_name} ({u.username})</option>)}
        </Select>
      </Field>
      <div className="sm:col-span-2 shell:col-span-3"><Field label="Notes (optional)" error={errors.notes}><Input name="notes" defaultValue={employee?.notes} /></Field></div>
      {employee && (
        <label className="flex min-h-11 cursor-pointer items-center gap-3 sm:col-span-2 shell:col-span-3">
          <input type="checkbox" name="is_active" defaultChecked={employee.is_active} className="size-5 accent-accent" />
          <span>Active <span className="text-sm text-muted">(an employee who left is marked inactive; their history stays)</span></span>
        </label>
      )}
      <div className="flex flex-col gap-3 sm:col-span-2 shell:col-span-3">
        <Notice>{error}</Notice>
        <div className="flex flex-wrap gap-2">
          <Button type="submit" variant={employee ? "success" : "primary"} disabled={busy}>{busy ? "Saving" : employee ? "Save changes" : "Add employee"}</Button>
          <Button type="button" variant="danger" onClick={onCancel}>Cancel</Button>
        </div>
      </div>
    </form>
  );
}

export function PunchForm({ id, onDone, onCancel }: { id: string; onDone: () => void; onCancel: () => void }) {
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

export function MarkForm({ id, onDone, onCancel }: { id: string; onDone: () => void; onCancel: () => void }) {
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
    <Card title="Mark a day">
      <form noValidate onSubmit={submit} className="space-y-4" {...live}>
        <Field label="Day" error={errors.day}><Input type="date" value={dayV} onChange={(e) => setDayV(e.target.value)} /></Field>
        <Segments value={kind} onChange={setKind} options={[{ value: "present", label: "Present (8 hours)" }, { value: "paid_leave", label: DAY.paid_leave[0] }, { value: "unpaid_leave", label: DAY.unpaid_leave[0] }]} />
        <Field label="Why" error={errors.reason}><Input value={reason} onChange={(e) => setReason(e.target.value)} maxLength={500} /></Field>
        <p className="text-sm text-muted">Present counts as a full 8-hour day (use it when the device missed the person). Unpaid leave costs a day&apos;s pay in payroll; paid leave does not.</p>
        <Notice>{error}</Notice>
        <div className="flex flex-wrap gap-2"><Button type="submit">Mark it</Button><Button type="button" variant="danger" onClick={onCancel}>Cancel</Button></div>
      </form>
    </Card>
  );
}
