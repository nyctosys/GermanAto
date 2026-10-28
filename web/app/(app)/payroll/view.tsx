"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Suspense, useState } from "react";
import { RUN } from "@/components/hr";
import { type PaymentBody, PaymentForm } from "@/components/payments";
import { RequirePermission } from "@/components/shell";
import { Badge, Button, Card, EmptyState, ErrorState, Field, Input, Notice, PageHeader, Select, SkeletonRows } from "@/components/ui";
import { api, useApi } from "@/lib/api";
import { day, money } from "@/lib/format";

type Run = { id: string; number: string; month: string; status: string; people: number; totals: { gross: string; recovery: string; net: string; paid: string } };
type Adv = { employees: { employee: { id: string; number: string; full_name: string; monthly_salary: string }; advanced: string; recovered: string; outstanding: string }[];
  entries: { id: string; number: string; occurred_on: string; amount: string; employee: string; status: string; no_proof_reason: string; proof_url: string | null }[] };

export default function PayrollPage() {
  return (
    <RequirePermission permission="payroll">
      <PageHeader title="Payroll and advances" description="Each month's pay from attendance, and money lent against salary." />
      <Suspense fallback={<Card flush><SkeletonRows /></Card>}>
        <Body />
      </Suspense>
    </RequirePermission>
  );
}

function lastMonth() {
  const d = new Date();
  d.setDate(1);
  d.setMonth(d.getMonth() - 1);
  return d.toLocaleDateString("en-CA").slice(0, 7);
}

function Body() {
  const router = useRouter();
  const runs = useApi<Run[]>("/api/payroll-runs");
  const adv = useApi<Adv>("/api/salary-advances");
  const [month, setMonth] = useState(lastMonth());
  const [error, setError] = useState<string | null>(null);
  const [giving, setGiving] = useState(false);

  async function start() {
    setError(null);
    try { router.push(`/payroll/${(await api<{ id: string }>("/api/payroll-runs", { method: "POST", json: { month } })).id}`); }
    catch (err) { setError((err as Error).message); }
  }
  const owing = adv.data?.employees.filter((e) => Number(e.outstanding) > 0) ?? [];

  return (
    <div className="space-y-4">
      <Card title="Payroll runs" flush>
        <div className="flex flex-wrap items-end gap-3 border-b border-rule p-4 shell:px-5">
          <div className="min-w-48"><Field label="Start a run for"><Input type="month" value={month} max={lastMonth()} onChange={(e) => setMonth(e.target.value)} /></Field></div>
          <Button onClick={start}>Work out the pay</Button>
          {error && <div className="w-full"><Notice>{error}</Notice></div>}
        </div>
        {runs.error ? <ErrorState message={runs.error} onRetry={runs.reload} /> : !runs.data ? <SkeletonRows rows={3} />
          : !runs.data.length ? <EmptyState title="No payroll runs yet">Pick a finished month above. Pay is worked out from attendance and can be adjusted before it is approved.</EmptyState> : (
            <ul>
              {runs.data.map((r) => (
                <li key={r.id}>
                  <Link href={`/payroll/${r.id}`} className="flex min-h-14 flex-wrap items-center justify-between gap-3 border-t border-rule px-4 py-3 pr-10 hover:bg-paper-2 row-link first:border-t-0 shell:px-5 shell:pr-12">
                    <span><span className="block font-medium">{new Date(`${r.month}-01`).toLocaleDateString("en-PK", { month: "long", year: "numeric" })}</span><span className="block text-sm text-muted">{r.number}, {r.people} {r.people === 1 ? "person" : "people"}</span></span>
                    <span className="flex items-center gap-3"><span className="num">{money(r.totals.net)}</span><Badge tone={RUN[r.status][1]}>{RUN[r.status][0]}</Badge></span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
      </Card>

      <Card title="Advances against salary" actions={!giving && <Button variant="secondary" onClick={() => setGiving(true)}>Give an advance</Button>} flush>
        {giving && adv.data && <div className="border-b border-rule p-4 shell:px-5"><AdvanceForm employees={adv.data.employees} onCancel={() => setGiving(false)} onDone={() => { setGiving(false); adv.reload(); }} /></div>}
        {adv.error ? <ErrorState message={adv.error} onRetry={adv.reload} /> : !adv.data ? <SkeletonRows rows={3} /> : (
          <>
            <p className="px-4 py-3 text-sm text-muted shell:px-5">{owing.length ? "Taken back through payroll. No more than a month's pay can be outstanding." : "Nobody owes an advance."}</p>
            {owing.length > 0 && (
              <ul>
                {owing.map((e) => (
                  <li key={e.employee.id} className="flex flex-wrap items-center justify-between gap-3 border-t border-rule px-4 py-3 shell:px-5">
                    <span><span className="font-medium">{e.employee.full_name}</span><span className="block text-sm text-muted">Advanced {money(e.advanced)}, recovered {money(e.recovered)}</span></span>
                    <span className="num">Owes {money(e.outstanding)}</span>
                  </li>
                ))}
              </ul>
            )}
            {adv.data.entries.length > 0 && (
              <>
                <p className="border-t border-rule px-4 py-2 text-sm font-medium text-ink-2 shell:px-5">Recent advances</p>
                <ul>
                  {adv.data.entries.slice(0, 8).map((m) => (
                    <li key={m.id} className="flex flex-wrap items-center justify-between gap-3 border-t border-rule px-4 py-2.5 text-sm shell:px-5">
                      <span className={m.status === "voided" ? "text-muted line-through" : ""}>{m.number}, {m.employee}, {day(m.occurred_on)}</span>
                      <span className="num">{money(m.amount)}</span>
                    </li>
                  ))}
                </ul>
              </>
            )}
          </>
        )}
      </Card>
    </div>
  );
}

function AdvanceForm({ employees, onDone, onCancel }: { employees: Adv["employees"]; onDone: () => void; onCancel: () => void }) {
  const [who, setWho] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const pick = employees.find((e) => e.employee.id === who);
  async function submit(b: PaymentBody) {
    if (!who) { setError("Choose the employee."); return; }
    setBusy(true);
    setError(null);
    try { await api("/api/salary-advances", { method: "POST", json: { ...b, employee_id: who } }); onDone(); }
    catch (err) { setError((err as Error).message); setBusy(false); }
  }
  return (
    <PaymentForm title="Give an advance" hint="Paid out now and taken back from pay. Proof or a reason, like every payment." busy={busy} onSubmit={submit} onCancel={onCancel}
                 note={<>
                   <Field label="To which employee"><Select value={who} onChange={(e) => setWho(e.target.value)}><option value="">Choose an employee</option>{employees.map((e) => <option key={e.employee.id} value={e.employee.id}>{e.employee.full_name}</option>)}</Select></Field>
                   {pick && <p className="text-sm text-muted">Monthly pay {money(pick.employee.monthly_salary)}. Already owes {money(pick.outstanding)}.</p>}
                   <Notice>{error}</Notice>
                 </>} />
  );
}
