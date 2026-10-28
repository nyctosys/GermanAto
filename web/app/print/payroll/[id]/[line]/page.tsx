"use client";

import { useParams } from "next/navigation";
import { Suspense } from "react";
import { Grid, Letterhead, PrintBar } from "@/components/print";
import { useApi } from "@/lib/api";
import { day, money } from "@/lib/format";

type Any = Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any -- mirrors the API's JSON

export default function PrintPayslip() {
  return <Suspense fallback={<p className="p-8">Loading</p>}><Slip /></Suspense>;
}

function Slip() {
  const { id, line } = useParams<{ id: string; line: string }>();
  const d = useApi<Any>(`/api/payroll-runs/${id}/lines/${line}`);
  const branch = useApi<{ name: string; address: string; phone: string }>("/api/branch");
  if (d.error) return <p className="p-8 text-error">{d.error}</p>;
  if (!d.data || !branch.data) return <p className="p-8">Loading</p>;
  const { run, line: l } = d.data;
  const title = new Date(`${run.month}-01`).toLocaleDateString("en-PK", { month: "long", year: "numeric" });
  return (
    <div className="mx-auto max-w-[148mm] px-4 py-4 text-[12px] leading-snug sm:px-[10mm] sm:py-[8mm] print:p-0">
      <PrintBar>{run.status === "draft" && <p className="text-error">Draft: not approved yet.</p>}</PrintBar>
      <Letterhead branch={branch.data} title="PAYSLIP" right={<><p>{title}</p><p>{run.number}</p></>} />
      <section className="mb-4 grid grid-cols-2 gap-4">
        <div><p className="font-bold">Employee</p><p>{l.employee.full_name}</p><p className="text-muted">{l.employee.number}{l.employee.title ? `, ${l.employee.title}` : ""}</p></div>
        <div><p className="font-bold">Attendance</p><p>{l.working_days} of {l.month_working_days} working days</p><p className="text-muted">{l.absent_days} absent, {l.unpaid_leave_days} unpaid leave, {l.late_days} late</p></div>
      </section>
      <Grid head={["", "Amount"]} right={[1]} rows={[
        ["Monthly salary", money(l.monthly_salary)],
        ...(l.working_days !== l.month_working_days ? [[`Pay for ${l.working_days} of ${l.month_working_days} days`, money(l.base_pay)]] : []),
        ...(Number(l.deduction) ? [[`Absence and unpaid leave (${l.absent_days + l.unpaid_leave_days} day${l.absent_days + l.unpaid_leave_days === 1 ? "" : "s"})`, `-${money(l.deduction)}`]] : []),
        ...(Number(l.adjustment) ? [[`${Number(l.adjustment) > 0 ? "Bonus" : "Deduction"}: ${l.adjustment_reason}`, money(l.adjustment)]] : []),
        ["Gross pay", money(l.gross_pay)],
        ...(Number(l.advance_recovery) ? [["Advance taken back", `-${money(l.advance_recovery)}`]] : []),
        [<b key="n">Net pay</b>, <b key="m">{money(l.net_pay)}</b>],
      ]} />
      {l.paid && <p className="mb-6">Paid on {day(l.paid.occurred_on)} ({l.paid.number}).</p>}
      <div className="mt-12 grid grid-cols-2 gap-10">
        <div><div className="h-10 border-b border-ink" /><p>Employee signature</p></div>
        <div><div className="h-10 border-b border-ink" /><p>For {branch.data.name}</p></div>
      </div>
    </div>
  );
}
