"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { RequirePermission } from "@/components/shell";
import { Button, Card, EmptyState, ErrorState, Field, Notice, PageHeader, Select, SkeletonRows } from "@/components/ui";
import { api, useApi } from "@/lib/api";
import { when } from "@/lib/format";

type Entry = {
  id: string; at: string; action: string; entity_type: string; entity_id: string | null;
  changes: Record<string, unknown>; user: string | null; ip: string;
};

const PAGE = 50;
const ACTIONS: Record<string, string> = {
  create: "Created", update: "Changed", delete: "Deleted", login: "Signed in",
  login_failed: "Failed sign-in", switch_branch: "Switched branch",
};
const RECORDS: Record<string, string> = {
  users: "User", user_branches: "User's branch access", roles: "Role", role_permissions: "Role permission",
  branches: "Branch", attachments: "Attachment", customers: "Customer", cars: "Car", car_ownerships: "Car owner",
  labour_codes: "Labour code", items: "Item", item_codes: "Item code", stock_movements: "Stock movement", visits: "Visit",
  inspections: "Inspection", job_cards: "Job card", job_card_lines: "Job card line", quotations: "Quotation",
  quotation_lines: "Quotation line", payments: "Payment", repair_orders: "Repair order", repair_order_lines: "Repair order line",
  repair_order_activity: "Repair order activity", invoices: "Invoice", invoice_lines: "Invoice line",
};
// Any table added later still reads as words, and can wrap on a phone.
const recordName = (t: string) => RECORDS[t] ?? t.replace(/_/g, " ");
const HIDDEN_FIELDS = new Set(["id", "created_at", "updated_at", "version", "created_by", "updated_by"]);

export default function AuditPage() {
  return (
    <RequirePermission permission="audit">
      <PageHeader
        title="Audit log"
        description="Every change and sign-in in this branch, newest first. Entries can't be edited or deleted."
      />
      {/* The filter lives in the URL, which needs a Suspense boundary. */}
      <Suspense fallback={<Card flush><SkeletonRows /></Card>}>
        <Audit />
      </Suspense>
    </RequirePermission>
  );
}

function Audit() {
  const router = useRouter();
  const pathname = usePathname();
  const action = useSearchParams().get("action") ?? "";

  function setAction(value: string) {
    router.replace(value ? `${pathname}?action=${value}` : pathname, { scroll: false });
  }

  return (
    <>
      <div className="mb-4 max-w-xs">
        <Field label="Show">
          <Select value={action} onChange={(e) => setAction(e.target.value)}>
            <option value="">Everything</option>
            {Object.entries(ACTIONS).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
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
  const [busy, setBusy] = useState(false);
  const entries = [...(first.data ?? []), ...older];
  const lastPageSize = older.length ? older.length % PAGE || PAGE : first.data?.length ?? 0;

  async function loadOlder() {
    const params = new URLSearchParams({ limit: String(PAGE), before: entries[entries.length - 1].at, ...(action && { action }) });
    setBusy(true);
    try {
      const page = await api<Entry[]>(`/api/audit?${params}`);
      setOlder((prev) => [...prev, ...page]);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card flush>
      {first.error ? <ErrorState message={first.error} onRetry={first.reload} />
        : !first.data ? <SkeletonRows rows={6} />
        : !entries.length ? (
          <EmptyState title="Nothing recorded yet">Changes and sign-ins appear here the moment they happen.</EmptyState>
        ) : (
          <>
            <table className="table-stack w-full text-left">
              <thead className="border-b border-rule text-sm text-muted">
                <tr>
                  <th className="px-5 py-3 font-medium">When</th>
                  <th className="px-3 py-3 font-medium">Who</th>
                  <th className="px-3 py-3 font-medium">What</th>
                  <th className="px-5 py-3 font-medium">Details</th>
                </tr>
              </thead>
              <tbody>
                {entries.map((e) => (
                  <tr key={e.id} className="border-t border-rule align-top first:border-t-0">
                    <td data-label="When" className="num px-5 py-3 max-sm:px-0 sm:whitespace-nowrap">{when(e.at)}</td>
                    <td data-label="Who" className="px-3 py-3 max-sm:px-0">{e.user ?? "System"}</td>
                    <td data-label="What" className="px-3 py-3 max-sm:px-0">
                      <span className="font-medium">{ACTIONS[e.action] ?? e.action}</span>{" "}
                      <span className="text-muted">{recordName(e.entity_type)}</span>
                    </td>
                    <td className="px-5 py-3 max-sm:px-0"><Changes changes={e.changes} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="flex flex-col gap-3 border-t border-rule p-4 shell:px-5">
              <Notice>{error}</Notice>
              {lastPageSize === PAGE && (
                <div><Button variant="secondary" onClick={loadOlder} disabled={busy}>{busy ? "Loading" : "Show older entries"}</Button></div>
              )}
            </div>
          </>
        )}
    </Card>
  );
}

function Changes({ changes }: { changes: Record<string, unknown> }) {
  const rows = Object.entries(changes).filter(([k]) => !HIDDEN_FIELDS.has(k));
  if (!rows.length) return <span className="text-muted">No field changes</span>;
  return (
    <ul className="space-y-1 text-sm">
      {rows.map(([k, v]) => (
        <li key={k} className="break-words">
          <span className="text-muted">{k.replaceAll("_", " ")}</span>{" "}
          {Array.isArray(v) && v.length === 2 ? (
            <>
              <del className="text-error">{String(v[0] ?? "empty")}</del>
              <span aria-hidden="true" className="px-1 text-muted">→</span>
              <ins className="text-success no-underline">{String(v[1] ?? "empty")}</ins>
            </>
          ) : (
            <span>{String(v ?? "empty")}</span>
          )}
        </li>
      ))}
    </ul>
  );
}
