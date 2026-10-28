"use client";

import Link from "next/link";
import { Suspense, useState } from "react";
import { RequirePermission } from "@/components/shell";
import { Badge, Button, Card, ErrorState, Notice, PageHeader, SkeletonRows } from "@/components/ui";
import { api, useApi } from "@/lib/api";
import { day } from "@/lib/format";
import { useSession } from "@/lib/session";

type P = { kind: "month" | "year"; period: string; label: string; status: "open" | "closed"; closed_at: string | null; closed_by: string | null; reopen_reason: string };
const PERIOD_PERMISSIONS = ["period-close", "reports-finance"];

export default function PeriodsPage() {
  return (
    <RequirePermission permission={PERIOD_PERMISSIONS}>
      <PageHeader title="Month end" description="Close each finished month once everything is counted and proven. A closed month is locked: nothing can be recorded inside it." />
      <Suspense fallback={<Card flush><SkeletonRows /></Card>}>
        <Body />
      </Suspense>
    </RequirePermission>
  );
}

function Body() {
  const { can } = useSession();
  const list = useApi<{ months: P[]; years: P[] }>("/api/periods");
  const [error, setError] = useState<string | null>(null);

  async function closeYear(y: string) {
    setError(null);
    try { await api(`/api/periods/${y}/close`, { method: "POST", json: {} }); list.reload(); } catch (err) { setError((err as Error).message); }
  }
  if (list.error) return <Card flush><ErrorState message={list.error} onRetry={list.reload} /></Card>;
  if (!list.data) return <Card flush><SkeletonRows rows={6} /></Card>;
  return (
    <div className="space-y-4">
      {error && <Notice>{error}</Notice>}
      <Card title="Months" flush>
        <ul>
          {list.data.months.map((m) => (
            <li key={m.period}>
              <Link href={`/periods/${m.period}`} className="row-link flex min-h-14 flex-wrap items-center justify-between gap-3 border-t border-rule px-4 py-3 pr-10 hover:bg-paper-2 first:border-t-0 shell:px-5 shell:pr-12">
                <span><span className="block font-medium">{m.label}</span>{m.status === "closed" && <span className="block text-sm text-muted">Closed {m.closed_at ? day(m.closed_at) : ""}{m.closed_by ? ` by ${m.closed_by}` : ""}</span>}
                  {m.status === "open" && m.reopen_reason && <span className="block text-sm text-warning">Reopened: {m.reopen_reason}</span>}</span>
                <Badge tone={m.status === "closed" ? "success" : "neutral"}>{m.status === "closed" ? "Closed" : "Open"}</Badge>
              </Link>
            </li>
          ))}
        </ul>
      </Card>
      <Card title="Years" flush>
        <ul>
          {list.data.years.map((y) => (
            <li key={y.period} className="flex flex-wrap items-center justify-between gap-3 border-t border-rule px-4 py-3 first:border-t-0 shell:px-5">
              <span><span className="block font-medium">{y.label}</span>{y.status === "closed" && <span className="block text-sm text-muted">Closed {y.closed_at ? day(y.closed_at) : ""}{y.closed_by ? ` by ${y.closed_by}` : ""}</span>}</span>
              <span className="flex flex-wrap items-center gap-2">
                <Link href={`/print/periods/${y.period}`} target="_blank" className="flex min-h-11 items-center rounded-control border border-rule-strong bg-surface px-4 font-medium hover:bg-paper active:bg-paper-3">Yearly pack</Link>
                {y.status === "open" && can("period-close") && Number(y.period) < new Date().getFullYear() && <Button variant="secondary" onClick={() => closeYear(y.period)}>Close the year</Button>}
                <Badge tone={y.status === "closed" ? "success" : "neutral"}>{y.status === "closed" ? "Closed" : "Open"}</Badge>
              </span>
            </li>
          ))}
        </ul>
        <p className="border-t border-rule px-4 py-3 text-sm text-muted shell:px-5">A year can be closed once it has ended and every month in it with activity is closed.</p>
      </Card>
    </div>
  );
}
