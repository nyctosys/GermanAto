"use client";

import { useState } from "react";
import { type LabourCode as Code, LabourCodeForm } from "@/components/labour-code-form";
import { RequirePermission } from "@/components/shell";
import { Badge, Button, Card, EmptyState, ErrorState, PageHeader, SkeletonRows } from "@/components/ui";
import { useApi } from "@/lib/api";
import { useSession } from "@/lib/session";


export default function LabourCodesPage() {
  return (
    <RequirePermission permission="dashboard">
      <LabourCodes />
    </RequirePermission>
  );
}

function LabourCodes() {
  const { can } = useSession();
  const editable = can("labour-codes");
  const list = useApi<Code[]>("/api/labour-codes?include_inactive=true", { swr: true });
  const [editing, setEditing] = useState<Code | "new" | null>(null);
  const groups = Object.entries(
    (list.data ?? []).reduce<Record<string, Code[]>>((acc, c) => ((acc[c.category] ??= []).push(c), acc), {}),
  ).sort(([a], [b]) => a.localeCompare(b));

  return (
    <>
      <PageHeader
        title="Labour codes"
        description="The work the workshop does. Job cards and quotations pick from this list; the price is set on each quotation."
        actions={editable && <Button onClick={() => setEditing("new")}>Add labour code</Button>}
      />
      {editing && (
        <div className="mb-6">
          <Card title={editing === "new" ? "New labour code" : `Edit ${editing.code}`}>
            <LabourCodeForm key={editing === "new" ? "new" : editing.id} code={editing === "new" ? null : editing}
                      onSaved={() => { setEditing(null); list.reload(); }} onCancel={() => { setEditing(null); list.reload(); }} />
          </Card>
        </div>
      )}
      {list.error ? <Card flush><ErrorState message={list.error} onRetry={list.reload} /></Card>
        : !list.data ? <Card flush><SkeletonRows /></Card>
        : !list.data.length ? (
          <Card flush>
            <EmptyState title="No labour codes yet" action={editable && <Button onClick={() => setEditing("new")}>Add labour code</Button>}>
              Add the jobs you do, for example PNT-DOOR for painting one door or OIL-SVC for an oil service.
            </EmptyState>
          </Card>
        ) : (
          <div className="space-y-4">
            {groups.map(([category, codes]) => (
              <Card key={category} title={category} flush>
                <ul>
                  {codes.map((c) => (
                    <li key={c.id} className="flex min-h-14 flex-wrap items-center justify-between gap-x-4 gap-y-1 border-t border-rule px-4 py-2.5 first:border-t-0 shell:px-5">
                      <span className="min-w-0">
                        <span className="num mr-3 font-semibold">{c.code}</span>
                        <span className={c.is_active ? "" : "text-muted"}>{c.name}</span>
                        {!c.is_active && <span className="ml-2"><Badge>Retired</Badge></span>}
                        {c.description && <span className="block text-sm text-muted">{c.description}</span>}
                      </span>
                      {editable && <Button variant="ghost" onClick={() => setEditing(c)}>Edit</Button>}
                    </li>
                  ))}
                </ul>
              </Card>
            ))}
          </div>
        )}
    </>
  );
}
