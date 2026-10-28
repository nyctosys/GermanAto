"use client";

import { useState } from "react";
import Link from "next/link";
import { RequirePermission } from "@/components/shell";
import { Badge, Button, Card, ErrorState, Notice, PageHeader, SkeletonRows } from "@/components/ui";
import { api, useApi } from "@/lib/api";
import { when } from "@/lib/format";

type Status = { configured: boolean; branch_id: string; pending: number; oldest_pending_at: string | null; last_push_at: string | null; last_pull_at: string | null; last_error: string; last_error_at: string | null; open_conflicts: number };

export default function SyncPage() {
  const s = useApi<Status>("/api/sync/status");
  const [note, setNote] = useState<{ tone: "success" | "error"; text: string } | null>(null);
  const [busy, setBusy] = useState(false);

  async function run() {
    setBusy(true);
    setNote(null);
    try {
      const r = await api<{ pushed: number; pulled: number; error: string }>("/api/sync/run", { method: "POST" });
      setNote(r.error ? { tone: "error", text: r.error } : { tone: "success", text: `Sent ${r.pushed} changes, received ${r.pulled}.` });
      s.reload();
    } catch (e) {
      setNote({ tone: "error", text: (e as Error).message });
    } finally {
      setBusy(false);
    }
  }

  const d = s.data;
  return (
    <RequirePermission permission="sync">
      <PageHeader title="Cloud sync" description="The workshop works without internet. When it is back, changes are sent to the cloud and other branches' changes are brought in."
        actions={<Button disabled={busy || !d?.configured} onClick={run}>{busy ? "Syncing" : "Sync now"}</Button>} />
      {note && <div className="mb-4"><Notice tone={note.tone}>{note.text}</Notice></div>}
      {s.error ? <ErrorState message={s.error} onRetry={s.reload} /> : !d ? <SkeletonRows rows={4} /> : (
        <div className="grid gap-4">
          {!d.configured && <Notice tone="warning">Sync is not set up. This workshop runs on its own. To connect it to the cloud, add the cloud address and the sync token to the server settings (see the runbook).</Notice>}
          {d.last_error && <Notice>Last attempt failed{d.last_error_at ? ` (${when(d.last_error_at)})` : ""}: {d.last_error}. Nothing is lost; it tries again by itself.</Notice>}
          <Card title="Status">
            <dl className="grid gap-4 sm:grid-cols-2 shell:grid-cols-4">
              <Stat label="Waiting to be sent" value={String(d.pending)} hint={d.oldest_pending_at ? `oldest from ${when(d.oldest_pending_at)}` : "everything is sent"} />
              <Stat label="Last sent" value={d.last_push_at ? when(d.last_push_at) : "Never"} />
              <Stat label="Last received" value={d.last_pull_at ? when(d.last_pull_at) : "Never"} />
              <Stat label="Needs a decision" value={String(d.open_conflicts)} hint={d.open_conflicts ? "changed in two places" : "no conflicts"} />
            </dl>
          </Card>
          <Card title="Conflicts" actions={<Link href="/settings/sync/conflicts" className="inline-flex min-h-11 items-center font-medium underline underline-offset-4">Review conflicts</Link>}>
            <p className="text-sm text-muted">When the same record was changed in two places in different ways, both versions are kept for a person to choose between.
              {d.open_conflicts > 0 && <> <Badge tone="warning">{d.open_conflicts} to review</Badge></>}</p>
          </Card>
          <Card title="This branch">
            <p className="text-sm text-muted">The cloud needs this branch&apos;s id to create its sync token:</p>
            <p className="num mt-1 break-all font-mono text-sm">{d.branch_id}</p>
          </Card>
        </div>
      )}
    </RequirePermission>
  );
}

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div>
      <dt className="text-sm text-muted">{label}</dt>
      <dd className="mt-0.5 text-lg font-medium">{value}</dd>
      {hint && <dd className="text-sm text-muted">{hint}</dd>}
    </div>
  );
}
