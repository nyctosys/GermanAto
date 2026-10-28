"use client";

import { useState } from "react";
import { RequirePermission } from "@/components/shell";
import { Button, Card, ErrorBox, Field, PageTitle, Select } from "@/components/ui";
import { api, useApi } from "@/lib/api";

type Entry = {
  id: string; at: string; action: string; entity_type: string; entity_id: string | null;
  changes: Record<string, unknown>; user: string | null; ip: string;
};

const PAGE = 50;

export default function AuditPage() {
  return (
    <RequirePermission permission="audit">
      <Audit />
    </RequirePermission>
  );
}

function Audit() {
  const [action, setAction] = useState("");
  return (
    <>
      <PageTitle title="Audit log" subtitle="Every change and sign-in in this branch, newest first. Entries can't be edited or deleted." />
      <div className="mb-4 max-w-xs">
        <Field label="Action">
          <Select value={action} onChange={(e) => setAction(e.target.value)}>
            <option value="">All</option>
            {["create", "update", "delete", "login", "login_failed", "switch_branch"].map((a) => <option key={a}>{a}</option>)}
          </Select>
        </Field>
      </div>
      {/* key: a new filter starts a fresh list */}
      <AuditList key={action} action={action} />
    </>
  );
}

function AuditList({ action }: { action: string }) {
  const first = useApi<Entry[]>(`/api/audit?${new URLSearchParams({ limit: String(PAGE), ...(action && { action }) })}`);
  const [older, setOlder] = useState<Entry[]>([]);
  const [error, setError] = useState<string | null>(null);
  const entries = [...(first.data ?? []), ...older];
  const lastPageSize = older.length ? older.length % PAGE || PAGE : first.data?.length ?? 0;

  async function loadOlder() {
    const params = new URLSearchParams({ limit: String(PAGE), before: entries[entries.length - 1].at, ...(action && { action }) });
    try {
      const page = await api<Entry[]>(`/api/audit?${params}`);
      setOlder((prev) => [...prev, ...page]);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <>
      <ErrorBox message={first.error ?? error} />
      <Card>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-left text-neutral-500">
              <tr><th className="py-2">When</th><th>Who</th><th>Action</th><th>Record</th><th>Details</th></tr>
            </thead>
            <tbody>
              {entries.map((e) => (
                <tr key={e.id} className="border-t border-neutral-100 align-top">
                  <td className="whitespace-nowrap py-2 pr-3">{new Date(e.at).toLocaleString()}</td>
                  <td className="pr-3">{e.user ?? "system"}</td>
                  <td className="pr-3 font-medium">{e.action}</td>
                  <td className="pr-3">{e.entity_type}</td>
                  <td><Changes changes={e.changes} /></td>
                </tr>
              ))}
            </tbody>
          </table>
          {first.loading && <p className="py-4 text-neutral-500">Loading…</p>}
          {first.data && !entries.length && <p className="py-4 text-neutral-500">Nothing logged yet.</p>}
        </div>
        {lastPageSize === PAGE && <Button variant="secondary" className="mt-4" onClick={loadOlder}>Load older</Button>}
      </Card>
    </>
  );
}

function Changes({ changes }: { changes: Record<string, unknown> }) {
  const rows = Object.entries(changes).filter(([k]) => !["id", "created_at", "updated_at", "version", "created_by", "updated_by"].includes(k));
  if (!rows.length) return <span className="text-neutral-400">—</span>;
  return (
    <ul className="space-y-0.5 text-xs">
      {rows.map(([k, v]) => (
        <li key={k}>
          <span className="text-neutral-500">{k}:</span>{" "}
          {Array.isArray(v) && v.length === 2
            ? <><s className="text-red-700">{String(v[0] ?? "∅")}</s> → <span className="text-green-700">{String(v[1] ?? "∅")}</span></>
            : String(v ?? "∅")}
        </li>
      ))}
    </ul>
  );
}
