"use client";

import { useState, type FormEvent } from "react";
import { RequirePermission } from "@/components/shell";
import { Badge, Button, Card, EmptyState, ErrorState, Field, Input, Notice, PageHeader, SkeletonRows } from "@/components/ui";
import { api, useApi } from "@/lib/api";
import { day, money } from "@/lib/format";
import { useLiveErrors } from "@/lib/form";
import { closeSchema, issuesToFieldErrors } from "@/lib/schemas";
import { useSession } from "@/lib/session";

type Status = { account: string; name: string; expected: string; last_close: { close_date: string; counted: string; difference: string } | null; closed_today: boolean };
type Close = { id: string; account: string; close_date: string; expected: string; counted: string; difference: string; reason: string; closed_by: string | null };
const KIND: Record<string, string> = { cash: "Cash", bank: "Bank", wallet: "Mobile wallet" };

export default function CashClosePage() {
  return (
    <RequirePermission permission={["cash-close", "reports-finance"]}>
      <PageHeader title="Cash close" description="At the end of the day, count what is really in each account and sign it off against what the books say." />
      <Body />
    </RequirePermission>
  );
}

function Body() {
  const status = useApi<Status[]>("/api/cash-closes/status");
  const history = useApi<Close[]>("/api/cash-closes");
  const reload = () => { status.reload(); history.reload(); };
  return (
    <div className="space-y-4">
      {status.error ? <Card flush><ErrorState message={status.error} onRetry={status.reload} /></Card> : !status.data ? <Card flush><SkeletonRows rows={3} /></Card> : (
        <div className="grid gap-4 shell:grid-cols-3">{status.data.map((s) => <AccountCard key={s.account} s={s} onDone={reload} />)}</div>
      )}
      <Card title="Past closes" flush>
        {history.error ? <ErrorState message={history.error} onRetry={history.reload} /> : !history.data ? <SkeletonRows rows={4} />
          : !history.data.length ? <EmptyState title="No closes yet">Each signed count appears here and cannot be changed.</EmptyState> : (
            <table className="table-stack w-full">
              <thead><tr className="text-left text-sm text-muted">
                <th className="px-4 py-2 font-normal shell:px-5">Day</th><th className="px-4 py-2 font-normal">Account</th>
                <th className="px-4 py-2 text-right font-normal">Books said</th><th className="px-4 py-2 text-right font-normal">Counted</th>
                <th className="px-4 py-2 text-right font-normal shell:pr-5">Difference</th>
              </tr></thead>
              <tbody>
                {history.data.map((c) => (
                  <tr key={c.id} className="border-t border-rule">
                    <td className="px-4 py-3 shell:px-5 max-sm:px-0"><span className="font-medium">{day(c.close_date)}</span>{c.closed_by && <span className="block text-sm text-muted">Signed by {c.closed_by}</span>}</td>
                    <td data-label="Account" className="px-4 py-3 max-sm:px-0">{KIND[c.account]}</td>
                    <td data-label="Books said" className="num px-4 py-3 text-right max-sm:px-0">{money(c.expected)}</td>
                    <td data-label="Counted" className="num px-4 py-3 text-right max-sm:px-0">{money(c.counted)}</td>
                    <td data-label="Difference" className="px-4 py-3 text-right shell:pr-5 max-sm:px-0">
                      {Number(c.difference) === 0 ? <Badge tone="success">Matched</Badge> : <><span className="num block text-warning">{Number(c.difference) > 0 ? "+" : "-"}{money(Math.abs(Number(c.difference)))}</span><span className="block text-sm text-muted">{c.reason}</span></>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
      </Card>
    </div>
  );
}

function AccountCard({ s, onDone }: { s: Status; onDone: () => void }) {
  const { can } = useSession();
  const [counting, setCounting] = useState(false);
  const [counted, setCounted] = useState("");
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const expected = Number(s.expected);
  const diff = /^\d/.test(counted) ? Math.round((Number(counted) - expected) * 100) / 100 : null;
  const { errors, activate, live } = useLiveErrors({ counted, reason, note: "" }, (v) => {
    const r = closeSchema(expected).safeParse(v);
    return r.success ? {} : issuesToFieldErrors(r.error.issues);
  });

  async function submit(e: FormEvent) {
    e.preventDefault();
    activate();
    const r = closeSchema(expected).safeParse({ counted, reason, note: "" });
    if (!r.success) return;
    setBusy(true);
    setError(null);
    try {
      await api("/api/cash-closes", { method: "POST", json: { account: s.account, counted, reason: diff ? reason : "" } });
      setCounting(false);
      onDone();
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  return (
    <Card title={`${s.name}`}>
      <p className="text-sm text-muted">The books say there should be</p>
      <p className="num text-xl">{money(s.expected)}</p>
      {Number(s.expected) < 0 && <p className="mt-1 text-sm text-error">Less than nothing? The opening balance may be missing. The owner can set it under Money settings.</p>}
      <p className="mt-2 text-sm text-muted">
        {s.last_close ? `Last counted ${day(s.last_close.close_date)}: ${money(s.last_close.counted)}` : "Never counted"}
      </p>
      {s.closed_today ? <div className="mt-3"><Badge tone="success">Closed for today</Badge></div> : can("cash-close") && !counting && (
        <div className="mt-4"><Button onClick={() => setCounting(true)}>Count and close</Button></div>
      )}
      {counting && (
        <form noValidate onSubmit={submit} className="mt-4 space-y-4" {...live}>
          <Field label="What is really in it (Rs)" error={errors.counted}><Input inputMode="decimal" value={counted} onChange={(e) => setCounted(e.target.value)} autoFocus /></Field>
          {diff !== null && diff !== 0 && (
            <>
              <Notice tone="warning">{`${money(Math.abs(diff))} ${diff > 0 ? "over" : "short"} compared with the books.`}</Notice>
              <Field label="Why does it differ?" error={errors.reason}><Input value={reason} onChange={(e) => setReason(e.target.value)} maxLength={500} /></Field>
            </>
          )}
          {diff === 0 && <p className="text-sm text-success">Matches the books.</p>}
          <Notice>{error}</Notice>
          <p className="text-sm text-muted">Signing is final. A difference is recorded in the books so tomorrow starts from what you counted.</p>
          <div className="flex flex-wrap gap-2"><Button type="submit" disabled={busy}>{busy ? "Signing" : "Sign the count"}</Button><Button type="button" variant="secondary" onClick={() => setCounting(false)}>Cancel</Button></div>
        </form>
      )}
    </Card>
  );
}
