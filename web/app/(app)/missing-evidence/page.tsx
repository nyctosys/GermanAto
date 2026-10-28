"use client";

import Link from "next/link";
import { Suspense, useState } from "react";
import { ACCOUNT } from "@/components/payments";
import { ReasonForm } from "@/components/purchasing";
import { Segments, useQueryParam } from "@/components/search";
import { MONEY, RequirePermission } from "@/components/shell";
import { SOURCE } from "@/components/moneybook";
import { Badge, Button, Card, EmptyState, ErrorState, Notice, PageHeader, SkeletonRows } from "@/components/ui";
import { api, useApi } from "@/lib/api";
import { day, money, when } from "@/lib/format";
import { useSession } from "@/lib/session";

type Row = { id: string; number: string; date: string; source: string; source_type: string; party: string; detail: string; account: string;
  amount: string; no_proof_reason: string; link: string | null; by: string | null; signoff: { reason: string; by: string | null; at: string } | null };
type Page = { rows: Row[]; open: number; signed_off: number; open_total: string };

export default function MissingEvidencePage() {
  return (
    <RequirePermission permission={MONEY}>
      <PageHeader title="Missing proof" description="Every payment recorded with a written reason instead of a photo or document. An admin can accept each one, with a reason, so month-end isn't blocked." />
      <Suspense fallback={<Card flush><SkeletonRows /></Card>}>
        <List />
      </Suspense>
    </RequirePermission>
  );
}

function List() {
  const { can } = useSession();
  const [view, setView] = useQueryParam("show");
  const list = useApi<Page>(`/api/missing-evidence?include_signed=${view === "all"}`);
  const [signing, setSigning] = useState<Row | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function sign(reason: string) {
    try {
      await api("/api/missing-evidence/sign", { method: "POST", json: { source_type: signing!.source_type, source_id: signing!.id, reason } });
      setSigning(null);
      list.reload();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <>
      {list.data && (
        <div className="mb-4 grid gap-4 sm:grid-cols-3">
          <Card title="Waiting for an admin"><p className="num text-xl">{list.data.open}</p><p className="num text-sm text-muted">{money(list.data.open_total)} in total</p></Card>
          <Card title="Accepted"><p className="num text-xl">{list.data.signed_off}</p><p className="text-sm text-muted">signed off with a reason</p></Card>
        </div>
      )}
      <div className="mb-4"><Segments value={view || "open"} onChange={(v) => setView(v === "open" ? "" : v)} options={[{ value: "open", label: "Waiting" }, { value: "all", label: "Waiting and accepted" }]} /></div>
      {signing && <div className="mb-4"><ReasonForm title={`Accept ${signing.number} without proof`} hint="Your name and this reason are kept with the record. It will still show as having no proof." confirm="Accept it" busy={false} onCancel={() => setSigning(null)} onSubmit={sign} /></div>}
      {error && <div className="mb-4"><Notice>{error}</Notice></div>}
      <Card flush>
        {list.error ? <ErrorState message={list.error} onRetry={list.reload} /> : !list.data ? <SkeletonRows />
          : !list.data.rows.length ? <EmptyState title="Nothing is missing proof">Every payment has a photo or document, or has been accepted by an admin.</EmptyState>
          : (
            <ul>
              {list.data.rows.map((r) => (
                <li key={`${r.source_type}-${r.id}`} className="flex flex-wrap items-start justify-between gap-3 border-t border-rule px-4 py-4 first:border-t-0 shell:px-5">
                  <div className="min-w-0">
                    <p className="font-medium">
                      {r.link ? <Link href={r.link} className="underline">{r.number}</Link> : r.number}{" "}
                      <span className="font-normal text-muted">{SOURCE[r.source]}, {day(r.date)}{r.party ? `, ${r.party}` : ""}, {ACCOUNT[r.account]}</span>
                    </p>
                    <p className="text-sm text-warning">Reason given: {r.no_proof_reason}</p>
                    {r.signoff && <p className="text-sm text-success">Accepted by {r.signoff.by} on {when(r.signoff.at)}: {r.signoff.reason}</p>}
                  </div>
                  <div className="flex flex-col items-end gap-1">
                    <span className="num">{money(r.amount)}</span>
                    {r.signoff ? <Badge tone="success">Accepted</Badge> : can("evidence-signoff") && <Button variant="secondary" onClick={() => setSigning(r)}>Accept</Button>}
                  </div>
                </li>
              ))}
            </ul>
          )}
      </Card>
    </>
  );
}
