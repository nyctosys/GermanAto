"use client";

import Link from "next/link";
import { NextStep } from "@/components/next-step";
import { useParams, useRouter } from "next/navigation";
import { Suspense, useState } from "react";
import { linkButton } from "@/components/estimates";
import { RUN } from "@/components/hr";
import { type PaymentBody, PaymentForm } from "@/components/payments";
import { Segments } from "@/components/search";
import { RequirePermission } from "@/components/shell";
import { Badge, Button, Card, ErrorState, Field, Input, Notice, SkeletonRows } from "@/components/ui";
import { api, useApi } from "@/lib/api";
import { money } from "@/lib/format";
import { type FieldErrors, payrollLineSchema } from "@/lib/schemas";

type Line = {
  id: string; employee: { id: string; full_name: string; title: string }; monthly_salary: string; working_days: number; month_working_days: number; absent_days: number;
  unpaid_leave_days: number; late_days: number; base_pay: string; deduction: string; adjustment: string; adjustment_reason: string; advance_recovery: string;
  net_pay: string; gross_pay: string; outstanding_advance: string; paid: { number: string; account: string } | null;
};
type Run = { id: string; number: string; month: string; status: string; approved_by: string | null; lines: Line[]; totals: { gross: string; recovery: string; net: string; paid: string } };

export default function PayrollRunPage() {
  return (
    <RequirePermission permission="payroll">
      <Suspense fallback={<Card flush><SkeletonRows rows={6} /></Card>}>
        <Loader />
      </Suspense>
    </RequirePermission>
  );
}

function Loader() {
  const { id } = useParams<{ id: string }>();
  const run = useApi<Run>(`/api/payroll-runs/${id}`);
  const [fresh, setFresh] = useState<Run | null>(null);
  if (run.error) return <Card flush><ErrorState message={run.error} onRetry={run.reload} /></Card>;
  if (!run.data) return <Card flush><SkeletonRows rows={6} /></Card>;
  return <View run={fresh && fresh.id === run.data.id ? fresh : run.data} onChange={setFresh} />;
}

function View({ run, onChange }: { run: Run; onChange: (r: Run) => void }) {
  const router = useRouter();
  const [editing, setEditing] = useState<string | null>(null);
  const [paying, setPaying] = useState<Line | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const draft = run.status === "draft";
  const title = new Date(`${run.month}-01`).toLocaleDateString("en-PK", { month: "long", year: "numeric" });

  async function call(path: string, method = "POST", json?: object) {
    setBusy(true);
    setError(null);
    try { const r = await api<Run>(`/api/payroll-runs/${run.id}${path}`, { method, json }); onChange(r); return true; }
    catch (err) { setError((err as Error).message); return false; }
    finally { setBusy(false); }
  }

  return (
    <>
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div><h1>Payroll for {title}</h1><p className="text-muted">{run.number}{run.approved_by ? `, approved by ${run.approved_by}` : ""}</p></div>
        <Badge tone={RUN[run.status][1]}>{RUN[run.status][0]}</Badge>
      </div>
      {draft
        ? <NextStep who="Accountant" target="act-approve-run" open={false} label="Review and approve">Check each person&apos;s days and any bonus or penalty (press Adjust on a line). When everything is right, approve the run.</NextStep>
        : run.status === "approved" && run.lines.some((l) => !l.paid && Number(l.net_pay) > 0)
          ? <NextStep who="Accountant">The run is approved. Press Pay next to each person to pay their salary.</NextStep>
          : null}
      <div className="mb-4 grid gap-4 sm:grid-cols-3">
        <Card title="Pay for the month"><p className="num text-xl">{money(run.totals.gross)}</p></Card>
        <Card title="Advances taken back"><p className="num text-xl">{money(run.totals.recovery)}</p></Card>
        <Card title="To pay out"><p className="num text-xl">{money(run.totals.net)}</p><p className="num text-sm text-muted">{money(run.totals.paid)} paid so far</p></Card>
      </div>

      {paying && (
        <div className="mb-4">
          <PaymentForm out title={`Pay ${paying.employee.full_name}`} hint={`Net pay ${money(paying.net_pay)} for ${title}.`} suggested={String(Number(paying.net_pay))} busy={busy}
                       onCancel={() => setPaying(null)} onSubmit={async (b: PaymentBody) => { if (await call(`/lines/${paying.id}/pay`, "POST", { account: b.account, reference: b.reference, note: b.note, proof_id: b.proof_id, no_proof_reason: b.no_proof_reason })) setPaying(null); }} />
        </div>
      )}
      <Card flush>
        <ul>
          {run.lines.map((l) => (
            <li key={l.id} className="space-y-3 border-t border-rule px-4 py-4 first:border-t-0 shell:px-5">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="font-medium">{l.employee.full_name} <span className="font-normal text-muted">{l.employee.title}</span></p>
                  <p className="text-sm text-muted">{l.working_days} of {l.month_working_days} working days. {l.absent_days} absent, {l.unpaid_leave_days} unpaid leave, {l.late_days} late.</p>
                </div>
                <div className="text-right">
                  <p className="num font-medium">{money(l.net_pay)}</p>
                  {l.paid ? <Badge tone="success">Paid, {l.paid.number}</Badge> : null}
                </div>
              </div>
              <dl className="grid grid-cols-2 gap-x-6 gap-y-1 text-sm sm:grid-cols-4">
                <div><dt className="text-muted">Base pay</dt><dd className="num">{money(l.base_pay)}</dd></div>
                <div><dt className="text-muted">Absence deduction</dt><dd className="num">{Number(l.deduction) ? `-${money(l.deduction)}` : "None"}</dd></div>
                <div><dt className="text-muted">{Number(l.adjustment) < 0 ? "Other deduction" : "Bonus"}</dt><dd className="num">{Number(l.adjustment) ? `${money(l.adjustment)}${l.adjustment_reason ? `, ${l.adjustment_reason}` : ""}` : "None"}</dd></div>
                <div><dt className="text-muted">Advance taken back</dt><dd className="num">{Number(l.advance_recovery) ? `-${money(l.advance_recovery)}` : "None"}</dd></div>
              </dl>
              {editing === l.id ? (
                <LineForm line={l} busy={busy} onCancel={() => setEditing(null)} onSubmit={async (b) => { if (await call(`/lines/${l.id}`, "PUT", b)) setEditing(null); }} />
              ) : (
                <div className="flex flex-wrap gap-2">
                  {draft && <Button variant="secondary" onClick={() => setEditing(l.id)}>Adjust</Button>}
                  {!draft && !l.paid && Number(l.net_pay) > 0 && <Button onClick={() => setPaying(l)}>Pay</Button>}
                  <Link href={`/print/payroll/${run.id}/${l.id}`} target="_blank" className={linkButton}>Payslip</Link>
                </div>
              )}
            </li>
          ))}
        </ul>
      </Card>
      <div className="mt-4 space-y-3">
        <Notice>{error}</Notice>
        {draft && (
          <>
            <div className="flex flex-wrap gap-2">
              <Button id="act-approve-run" disabled={busy} onClick={() => call("/approve")}>Approve the run</Button>
              <Button variant="secondary" disabled={busy} onClick={() => call("/refresh")}>Refresh from attendance</Button>
              <Button variant="ghost" disabled={busy} onClick={async () => { if (await call("/void")) router.push("/payroll"); }}>Throw this draft away</Button>
            </div>
            <p className="text-sm text-muted">Approving fixes the figures and books the salary expense. Check attendance first: after approving, nothing here can change.</p>
          </>
        )}
      </div>
    </>
  );
}

const round2 = (n: number) => String(Math.round(n * 100) / 100);

/** Adjust one person's pay: a bonus or a penalty, and how much advance to take back. Each can be rupees or a percentage. */
function LineForm({ line, busy, onSubmit, onCancel }: { line: Line; busy: boolean; onSubmit: (b: object) => void; onCancel: () => void }) {
  const adjNow = Number(line.adjustment);
  const [kind, setKind] = useState<"bonus" | "penalty">(adjNow < 0 ? "penalty" : "bonus");
  const [adjUnit, setAdjUnit] = useState<"rs" | "pct">("rs");
  const [adj, setAdj] = useState(adjNow ? String(Math.abs(adjNow)) : "");
  const [why, setWhy] = useState(line.adjustment_reason);
  const [recUnit, setRecUnit] = useState<"rs" | "pct">("rs");
  const [rec, setRec] = useState(String(Number(line.advance_recovery)));
  const [errors, setErrors] = useState<FieldErrors>({});
  const base = Number(line.base_pay), owed = Number(line.outstanding_advance);
  const adjRs = adjUnit === "pct" ? round2((base * Number(adj || 0)) / 100) : adj;
  const recRs = recUnit === "pct" ? round2((owed * Number(rec || 0)) / 100) : rec;
  const signed = kind === "penalty" && Number(adjRs) ? `-${adjRs}` : adjRs;
  const unitToggle = (u: "rs" | "pct", set: (u: "rs" | "pct") => void) => (
    <Segments value={u} onChange={(v) => set(v as "rs" | "pct")} options={[{ value: "rs", label: "Rs" }, { value: "pct", label: "%" }]} />
  );
  return (
    <form noValidate className="grid gap-4 rounded-control bg-paper-2 p-4 sm:grid-cols-3" onSubmit={(e) => {
      e.preventDefault();
      const r = payrollLineSchema.safeParse({ adjustment: signed, adjustment_reason: why, advance_recovery: recRs });
      const found: FieldErrors = {};
      if (!r.success) for (const i of r.error.issues) found[String(i.path[0])] ??= i.message;
      if (r.success && Number(r.data.advance_recovery) > owed) found.advance_recovery = `They only owe ${money(owed)}`;
      setErrors(found);
      if (r.success && !Object.keys(found).length) onSubmit(r.data);
    }}>
      <div className="space-y-2">
        <Segments value={kind} onChange={(v) => setKind(v as typeof kind)} options={[{ value: "bonus", label: "Bonus" }, { value: "penalty", label: "Penalty" }]} />
        {unitToggle(adjUnit, setAdjUnit)}
        <Field label={kind === "bonus" ? "Bonus" : "Penalty"} error={errors.adjustment} hint={adjUnit === "pct" ? `${adj || 0}% of base pay ${money(base)} = ${money(adjRs || 0)}` : undefined}>
          <Input inputMode="decimal" value={adj} onChange={(e) => setAdj(e.target.value.replace(/^-/, ""))} placeholder="0" />
        </Field>
      </div>
      <Field label="What it is for" error={errors.adjustment_reason}><Input value={why} onChange={(e) => setWhy(e.target.value)} maxLength={200} /></Field>
      <div className="space-y-2">
        {unitToggle(recUnit, setRecUnit)}
        <Field label="Advance to take back" error={errors.advance_recovery} hint={`Owes ${money(owed)}${recUnit === "pct" ? `. ${rec || 0}% = ${money(recRs || 0)}` : ""}`}><Input inputMode="decimal" value={rec} onChange={(e) => setRec(e.target.value)} /></Field>
      </div>
      <div className="flex flex-wrap gap-2 sm:col-span-3"><Button type="submit" variant="success" disabled={busy}>Save</Button><Button type="button" variant="danger" onClick={onCancel}>Cancel</Button></div>
    </form>
  );
}
