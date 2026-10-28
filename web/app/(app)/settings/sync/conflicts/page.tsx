"use client";

import { useState } from "react";
import Link from "next/link";
import { RequirePermission } from "@/components/shell";
import { Badge, Button, Card, EmptyState, ErrorState, Notice, PageHeader, Select, SkeletonRows } from "@/components/ui";
import { api, useApi } from "@/lib/api";
import { when } from "@/lib/format";

type Conflict = { id: string; table: string; status: "open" | "resolved"; resolution: string | null; note: string; created_at: string; resolved_at: string | null; local: Record<string, unknown>; remote: Record<string, unknown>; differs: string[] };

const show = (v: unknown) => (v === null || v === undefined || v === "" ? "empty" : typeof v === "object" ? JSON.stringify(v) : String(v));
const label = (k: string) => k.replaceAll("_", " ");

export default function ConflictsPage() {
  const [status, setStatus] = useState("open");
  const list = useApi<Conflict[]>(`/api/sync/conflicts?status=${status}`);
  const [error, setError] = useState<string | null>(null);

  async function resolve(c: Conflict, resolution: "keep_local" | "keep_remote") {
    setError(null);
    try { await api(`/api/sync/conflicts/${c.id}/resolve`, { method: "POST", json: { resolution } }); list.reload(); }
    catch (e) { setError((e as Error).message); }
  }

  return (
    <RequirePermission permission="sync">
      <PageHeader title="Sync conflicts" description="A record was changed here and somewhere else in different ways. Choose which version to keep."
        actions={<Link href="/settings/sync" className="inline-flex min-h-11 items-center font-medium underline underline-offset-4">Back to cloud sync</Link>} />
      {error && <div className="mb-4"><Notice>{error}</Notice></div>}
      <Card title="Conflicts" flush actions={<Select aria-label="Show" value={status} onChange={(e) => setStatus(e.target.value)} className="w-auto"><option value="open">To review</option><option value="resolved">Settled</option></Select>}>
        {list.error ? <ErrorState message={list.error} onRetry={list.reload} /> : !list.data ? <SkeletonRows rows={3} /> : !list.data.length ? (
          <EmptyState title={status === "open" ? "Nothing to review" : "Nothing settled yet"}>{status === "open" ? "No record has been changed in two places." : "Settled conflicts appear here."}</EmptyState>
        ) : (
          <ul>
            {list.data.map((c) => (
              <li key={c.id} className="border-t border-rule px-4 py-4 first:border-t-0 shell:px-5">
                <p className="flex flex-wrap items-center gap-2 font-medium">{label(c.table)} <span className="font-normal text-muted">{when(c.created_at)}</span>
                  {c.status === "resolved" && <Badge tone="success">{c.resolution === "keep_local" ? "Kept this server's" : "Took the other server's"}</Badge>}</p>
                <ul className="mt-3">
                  {c.differs.map((k) => (
                    <li key={k} className="border-t border-rule py-2">
                      <p className="text-sm capitalize text-muted">{label(k)}</p>
                      <p className="grid grid-cols-[6.5rem_1fr] gap-x-3 break-words text-[0.9375rem]"><span className="text-muted">This server</span><span>{show(c.local[k])}</span></p>
                      <p className="grid grid-cols-[6.5rem_1fr] gap-x-3 break-words text-[0.9375rem]"><span className="text-muted">Other server</span><span>{show(c.remote[k])}</span></p>
                    </li>
                  ))}
                </ul>
                {c.status === "open" && (
                  <div className="mt-3 flex flex-wrap gap-2">
                    <Button variant="secondary" onClick={() => resolve(c, "keep_local")}>Keep this server&apos;s</Button>
                    <Button variant="secondary" onClick={() => resolve(c, "keep_remote")}>Take the other server&apos;s</Button>
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </Card>
    </RequirePermission>
  );
}
