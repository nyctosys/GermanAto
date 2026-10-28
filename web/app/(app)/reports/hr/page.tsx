"use client";

import Link from "next/link";
import { Suspense } from "react";
import { ExportButton } from "@/components/reports";
import { useQueryParam } from "@/components/search";
import { RequirePermission } from "@/components/shell";
import { Card, EmptyState, ErrorState, Field, Input, PageHeader, SkeletonRows } from "@/components/ui";
import { useApi } from "@/lib/api";
import { money } from "@/lib/format";

type Hr = {
  month: string; attendance: { employee_id: string; full_name: string; present: number; late: number; absent: number; leave: number; working_days: number; hours: string }[];
  payroll_cost: { month: string; status: string; gross: string; net: string }[]; advances_outstanding: { employee_id: string; full_name: string; outstanding: string }[]; advances_total: string;
  technicians: { name: string; jobs: number; labour_billed: string }[];
};

export default function HrReport() {
  return (
    <RequirePermission permission="hr">
      <PageHeader title="People report" description="Attendance, what payroll costs, advances owed, and what each technician billed." />
      <Suspense fallback={<Card flush><SkeletonRows /></Card>}>
        <Body />
      </Suspense>
    </RequirePermission>
  );
}

function Body() {
  const [m, setM] = useQueryParam("month");
  const now = new Date().toLocaleDateString("en-CA").slice(0, 7);
  const month = m || now;
  const r = useApi<Hr>(`/api/reports/hr?month=${month}`);
  return (
    <div className="space-y-4">
      <Card title="Month"><div className="max-w-60"><Field label="Month"><Input type="month" value={month} max={now} onChange={(e) => setM(e.target.value)} /></Field></div></Card>
      {r.error ? <Card flush><ErrorState message={r.error} onRetry={r.reload} /></Card> : !r.data ? <Card flush><SkeletonRows rows={5} /></Card> : (
        <>
          <Card title="Attendance" actions={<ExportButton name={`attendance-${month}`} headers={["Employee", "Present", "Late", "Absent", "Leave", "Working days", "Hours"]} rows={r.data.attendance.map((a) => [a.full_name, a.present, a.late, a.absent, a.leave, a.working_days, a.hours])} />} flush>
            {!r.data.attendance.length ? <EmptyState title="Nobody was employed this month" /> : (
              <table className="table-stack w-full">
                <thead><tr className="text-left text-sm text-muted"><th className="px-4 py-2 font-normal shell:px-5">Employee</th><th className="px-4 py-2 text-right font-normal">Present</th><th className="px-4 py-2 text-right font-normal">Late</th><th className="px-4 py-2 text-right font-normal">Absent</th><th className="px-4 py-2 text-right font-normal">Leave</th><th className="px-4 py-2 text-right font-normal shell:pr-5">Hours</th></tr></thead>
                <tbody>
                  {r.data.attendance.map((a) => (
                    <tr key={a.employee_id} className="border-t border-rule">
                      <td className="px-4 py-3 shell:px-5 max-sm:px-0"><Link href={`/employees/${a.employee_id}?month=${month}`} className="font-medium underline">{a.full_name}</Link><span className="block text-sm text-muted">{a.working_days} working days</span></td>
                      <td data-label="Present" className="num px-4 py-3 text-right max-sm:px-0">{a.present}</td><td data-label="Late" className="num px-4 py-3 text-right max-sm:px-0">{a.late}</td>
                      <td data-label="Absent" className={`num px-4 py-3 text-right max-sm:px-0 ${a.absent ? "text-error" : ""}`}>{a.absent}</td><td data-label="Leave" className="num px-4 py-3 text-right max-sm:px-0">{a.leave}</td>
                      <td data-label="Hours" className="num px-4 py-3 text-right shell:pr-5 max-sm:px-0">{Number(a.hours).toFixed(1)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Card>
          <div className="grid gap-4 shell:grid-cols-2">
            <Card title="Payroll cost by month" flush>
              {!r.data.payroll_cost.length ? <p className="px-4 py-4 text-muted shell:px-5">No payroll runs yet.</p> : (
                <ul>{r.data.payroll_cost.map((p) => <li key={p.month} className="flex justify-between gap-3 border-t border-rule px-4 py-2.5 first:border-t-0 shell:px-5"><span>{new Date(`${p.month}-01`).toLocaleDateString("en-PK", { month: "long", year: "numeric" })}<span className="block text-sm text-muted">{p.status}</span></span><span className="text-right"><span className="num block">{money(p.gross)}</span><span className="num block text-sm text-muted">{money(p.net)} paid out</span></span></li>)}</ul>
              )}
            </Card>
            <div className="space-y-4">
              <Card title="Advances owed" actions={<span className="num font-medium">{money(r.data.advances_total)}</span>} flush>
                {!r.data.advances_outstanding.length ? <p className="px-4 py-4 text-muted shell:px-5">Nobody owes an advance.</p> : (
                  <ul>{r.data.advances_outstanding.map((a) => <li key={a.employee_id} className="flex justify-between gap-3 border-t border-rule px-4 py-2.5 first:border-t-0 shell:px-5"><span>{a.full_name}</span><span className="num">{money(a.outstanding)}</span></li>)}</ul>
                )}
              </Card>
              <Card title="What each technician billed" flush>
                {!r.data.technicians.length ? <p className="px-4 py-4 text-muted shell:px-5">No finished labour assigned to a technician this month.</p> : (
                  <ul>{r.data.technicians.map((t) => <li key={t.name} className="flex justify-between gap-3 border-t border-rule px-4 py-2.5 first:border-t-0 shell:px-5"><span>{t.name}<span className="block text-sm text-muted">{t.jobs} {t.jobs === 1 ? "job" : "jobs"}</span></span><span className="num">{money(t.labour_billed)}</span></li>)}</ul>
                )}
              </Card>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
