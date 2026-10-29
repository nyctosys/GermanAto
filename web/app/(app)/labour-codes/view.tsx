"use client";

import { useState, type FormEvent } from "react";
import { RequirePermission } from "@/components/shell";
import { Badge, Button, Card, Checkbox, EmptyState, ErrorState, Field, Input, Notice, PageHeader, SkeletonRows } from "@/components/ui";
import { api, useApi } from "@/lib/api";
import { useSession } from "@/lib/session";

type Code = { id: string; code: string; name: string; category: string; description: string; is_active: boolean; version: number };

// Suggestions only: any category can be typed.
const CATEGORIES = ["Mechanical", "Electrical", "Denting", "Painting", "AC", "Diagnostics", "Detailing", "Inspection", "Tyres"];

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
            <CodeForm key={editing === "new" ? "new" : editing.id} code={editing === "new" ? null : editing}
                      categories={[...new Set([...CATEGORIES, ...groups.map(([c]) => c)])]}
                      onDone={() => { setEditing(null); list.reload(); }} />
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

function CodeForm({ code, categories, onDone }: { code: Code | null; categories: string[]; onDone: () => void }) {
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const body = { code: code?.code ?? f.get("code"), name: f.get("name"), category: f.get("category"),
                   description: f.get("description"), is_active: code ? f.get("is_active") === "on" : true };
    setBusy(true);
    setError(null);
    try {
      await api(code ? `/api/labour-codes/${code.id}` : "/api/labour-codes", { method: code ? "PUT" : "POST", json: body });
      onDone();
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="grid gap-5 sm:grid-cols-2">
      <Field label="Code" hint={code ? "Codes can't be changed once created." : "2 to 24 letters, digits or dashes, e.g. PNT-DOOR"}>
        <Input name="code" defaultValue={code?.code} disabled={!!code} required pattern="[A-Za-z0-9][A-Za-z0-9\-]{1,23}" autoCapitalize="characters" spellCheck={false} />
      </Field>
      <Field label="Category">
        <Input name="category" defaultValue={code?.category} required list="labour-categories" />
        <datalist id="labour-categories">{categories.map((c) => <option key={c} value={c} />)}</datalist>
      </Field>
      <div className="sm:col-span-2"><Field label="Name"><Input name="name" defaultValue={code?.name} required placeholder="Paint one door" /></Field></div>
      <div className="sm:col-span-2"><Field label="Description (optional)"><Input name="description" defaultValue={code?.description} /></Field></div>
      {code && <div className="sm:col-span-2"><Checkbox name="is_active" defaultChecked={code.is_active} label="In use" hint="Retired codes stay on old documents but can't be picked." /></div>}
      <div className="flex flex-col gap-3 sm:col-span-2">
        <Notice>{error}</Notice>
        <div className="flex flex-wrap gap-2">
          <Button type="submit" variant={code ? "success" : "primary"} disabled={busy}>{busy ? "Saving" : code ? "Save changes" : "Add labour code"}</Button>
          <Button type="button" variant="secondary" onClick={onDone}>Cancel</Button>
        </div>
      </div>
    </form>
  );
}
