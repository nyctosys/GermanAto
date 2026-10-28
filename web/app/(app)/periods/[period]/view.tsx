"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { Suspense, useState } from "react";
import { linkButton } from "@/components/estimates";
import { ReasonForm } from "@/components/purchasing";
import { RequirePermission } from "@/components/shell";
import { Badge, Button, Card, ErrorState, Field, Input, Notice, SkeletonRows } from "@/components/ui";
import { api, useApi } from "@/lib/api";
import { day } from "@/lib/format";
import { useSession } from "@/lib/session";

type Item = { key: string; label: string; ok: boolean; detail: string; blocking: boolean; link: string | null };
type Check = { period: string; label: string; items: Item[]; can_close: boolean; blockers: number; warnings: number; status: "open" | "closed"; closed_at: string | null; closed_by: string | null; reopen_reason: string; reopened_by: string | null };

export default function PeriodPage() {
  return (
    <RequirePermission permission={["period-close", "reports-finance"]}>
      <Suspense fallback={<Card flush><SkeletonRows rows={6} /></Card>}>
        <Wizard />
      </Suspense>
    </RequirePermission>
  );
}

function Wizard() {
  const { period } = useParams<{ period: string }>();
  const { can } = useSession();
  const c = useApi<Check>(`/api/periods/${period}/checklist`);
  const [notes, setNotes] = useState("");
  const [reopening, setReopening] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function act(path: string, json: object) {
    setBusy(true);
    setError(null);
    try { await api(`/api/periods/${period}/${path}`, { method: "POST", json }); setReopening(false); c.reload(); return true; }
    catch (err) { setError((err as Error).message); return false; }
    finally { setBusy(false); }
  }
  if (c.error) return <Card flush><ErrorState message={c.error} onRetry={c.reload} /></Card>;
  if (!c.data) return <Card flush><SkeletonRows rows={6} /></Card>;
  const d = c.data, closed = d.status === "closed";

  return (
    <>
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1>{d.label}</h1>
          <p className="text-muted">{closed ? `Closed ${d.closed_at ? day(d.closed_at) : ""}${d.closed_by ? ` by ${d.closed_by}` : ""}. Nothing can be recorded inside this month.` : "Check everything below, then close the month."}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone={closed ? "success" : "neutral"}>{closed ? "Closed" : "Open"}</Badge>
          <Link href={`/print/periods/${d.period}`} target="_blank" className={linkButton}>Closing pack</Link>
        </div>
      </div>
      {d.reopen_reason && !closed && <div className="mb-4"><Notice tone="warning">Reopened by {d.reopened_by}: {d.reopen_reason}</Notice></div>}

      <Card title="Checklist" flush>
        <ul>
          {d.items.map((i) => (
            <li key={i.key} className="flex flex-wrap items-start justify-between gap-3 border-t border-rule px-4 py-3 first:border-t-0 shell:px-5">
              <div className="flex min-w-0 gap-3">
                <span aria-hidden="true" className={`mt-1 flex size-5 shrink-0 items-center justify-center rounded-full text-xs ${i.ok ? "bg-success text-accent-ink" : i.blocking ? "bg-error text-accent-ink" : "bg-warning text-accent-ink"}`}>{i.ok ? "✓" : "!"}</span>
                <div className="min-w-0">
                  <p className="font-medium">{i.label}{!i.blocking && !i.ok && <span className="ml-2 text-sm font-normal text-muted">Not required</span>}</p>
                  <p className="sr-only">{i.ok ? "Done" : i.blocking ? "Not done, stops the close" : "Not done"}</p>
                  {i.detail && <p className="text-sm text-muted">{i.detail}</p>}
                </div>
              </div>
              {!i.ok && i.link && <Link href={i.link} className="flex min-h-11 items-center text-sm underline">Fix it</Link>}
            </li>
          ))}
        </ul>
      </Card>

      <div className="mt-4 space-y-4">
        <Notice>{error}</Notice>
        {reopening && <ReasonForm title={`Reopen ${d.label}`} hint="Only an admin can. The reason is kept. Later months must be reopened first." confirm="Reopen" busy={busy} onCancel={() => setReopening(false)} onSubmit={(reason) => act("reopen", { reason })} />}
        {!closed && can("period-close") && (
          <Card title="Close the month">
            <div className="space-y-4">
              <Field label="Note (optional)"><Input value={notes} onChange={(e) => setNotes(e.target.value)} maxLength={1000} /></Field>
              <Button disabled={busy || !d.can_close} onClick={() => act("close", { notes })}>{d.can_close ? "Close this month" : `${d.blockers} thing${d.blockers === 1 ? "" : "s"} to fix first`}</Button>
              <p className="text-sm text-muted">Closing locks the month. Print the closing pack first if you want a copy of the figures as they stand.</p>
            </div>
          </Card>
        )}
        {closed && can("period-approve") && !reopening && <Button variant="secondary" onClick={() => setReopening(true)}>Reopen this month</Button>}
      </div>
    </>
  );
}
