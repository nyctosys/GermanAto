"use client";

import { useRef, useState, type FormEvent } from "react";
import { Badge, Button, Field, Input, Notice, Select } from "@/components/ui";
import { api, useApi } from "@/lib/api";
import { phone } from "@/lib/format";
import { useFormErrors } from "@/lib/form";
import { employeeSchema, parseForm } from "@/lib/schemas";

export type Employee = {
  id: string; number: string; full_name: string; title: string; phone: string; cnic: string; user_id: string | null; username: string | null;
  device_pin: string; monthly_salary: string; shift_start: string; shift_end: string; weekly_off: number; joined_on: string; left_on: string | null;
  notes: string; is_active: boolean; version: number;
};

export const WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

export const DAY: Record<string, [string, "neutral" | "success" | "warning" | "error" | "accent"]> = {
  present: ["Present", "success"], late: ["Late", "warning"], incomplete: ["One punch only", "warning"], absent: ["Absent", "error"],
  off: ["Day off", "neutral"], paid_leave: ["Paid leave", "accent"], unpaid_leave: ["Unpaid leave", "neutral"],
};
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
      onSaved(employee
        ? await api<Employee>(`/api/employees/${employee.id}`, { method: "PUT", json: { ...body, is_active: new FormData(form.current!).get("is_active") === "on", version: employee.version } })
        : await api<Employee>("/api/employees", { method: "POST", json: body }));
    } catch (err) {
      setError(applyApi(err));
      setBusy(false);
    }
  }

  return (
    <form ref={form} noValidate onSubmit={submit} className="grid gap-5 sm:grid-cols-2 shell:grid-cols-3" {...live}>
      <Field label="Full name" error={errors.full_name}><Input name="full_name" defaultValue={employee?.full_name} required maxLength={120} autoComplete="off" autoFocus /></Field>
      <Field label="Job title (optional)" error={errors.title}><Input name="title" defaultValue={employee?.title} maxLength={80} placeholder="Technician" /></Field>
      <Field label="Phone (optional)" error={errors.phone}><Input name="phone" defaultValue={employee ? phone(employee.phone) : ""} inputMode="tel" /></Field>
      <Field label="CNIC (optional)" error={errors.cnic} hint="13 digits"><Input name="cnic" defaultValue={employee?.cnic} inputMode="numeric" /></Field>
      <Field label="Monthly salary (Rs)" error={errors.monthly_salary}><Input name="monthly_salary" inputMode="decimal" defaultValue={employee ? String(Number(employee.monthly_salary)) : ""} /></Field>
      <Field label="Number on the attendance device" error={errors.device_pin} hint="Claims punches already received for it."><Input name="device_pin" defaultValue={employee?.device_pin} maxLength={20} inputMode="numeric" /></Field>
      <Field label="Shift starts" error={errors.shift_start}><Input name="shift_start" type="time" defaultValue={hhmm(employee?.shift_start ?? "09:00")} /></Field>
      <Field label="Shift ends" error={errors.shift_end}><Input name="shift_end" type="time" defaultValue={hhmm(employee?.shift_end ?? "18:00")} /></Field>
      <Field label="Weekly day off" error={errors.weekly_off}>
        <Select name="weekly_off" defaultValue={employee?.weekly_off ?? 6}>{WEEKDAYS.map((d, i) => <option key={d} value={i}>{d}</option>)}</Select>
      </Field>
      <Field label="Joined on" error={errors.joined_on}><Input name="joined_on" type="date" defaultValue={employee?.joined_on} /></Field>
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
          <Button type="button" variant="secondary" onClick={onCancel}>Cancel</Button>
        </div>
      </div>
    </form>
  );
}
