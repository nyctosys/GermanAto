"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { RequirePermission } from "@/components/shell";
import {
  Badge, Button, Card, Checkbox, EmptyState, ErrorState, Field, Input, Notice, PageHeader, SkeletonRows,
} from "@/components/ui";
import { api, useApi } from "@/lib/api";

type Role = { id: string; name: string; description: string; is_admin: boolean; permissions: string[] };
type Permission = { key: string; label: string };

export default function RolesPage() {
  return (
    <RequirePermission permission="users">
      <Roles />
    </RequirePermission>
  );
}

function Roles() {
  const roles = useApi<Role[]>("/api/roles");
  const perms = useApi<Permission[]>("/api/permissions");
  const [editing, setEditing] = useState<Role | "new" | null>(null);
  const label = (key: string) => perms.data?.find((p) => p.key === key)?.label ?? key;
  const error = roles.error ?? perms.error;

  return (
    <>
      <PageHeader
        title="Roles and permissions"
        description="A role is a set of permissions. Each user has one role, and the server checks it on every request."
        actions={<Button onClick={() => setEditing("new")} disabled={!perms.data}>Add role</Button>}
      />
      {editing && perms.data && (
        <RoleForm
          key={editing === "new" ? "new" : editing.id}
          role={editing === "new" ? null : editing}
          permissions={perms.data}
          onCancel={() => setEditing(null)}
          onSaved={() => { setEditing(null); roles.reload(); }}
        />
      )}
      {error ? <Card flush><ErrorState message={error} onRetry={() => { roles.reload(); perms.reload(); }} /></Card>
        : !roles.data ? <Card flush><SkeletonRows /></Card>
        : !roles.data.length ? (
          <Card flush><EmptyState title="No roles yet" action={<Button onClick={() => setEditing("new")}>Add role</Button>} /></Card>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2">
            {roles.data.map((r) => (
              <Card key={r.id} title={r.name} actions={<Button variant="secondary" onClick={() => setEditing(r)}>Edit</Button>}>
                {r.description && <p className="mb-3 text-muted">{r.description}</p>}
                {r.is_admin ? (
                  <Badge tone="accent">Every permission</Badge>
                ) : r.permissions.length ? (
                  <ul className="space-y-1.5">
                    {r.permissions.map((p) => <li key={p} className="text-ink-2">{label(p)}</li>)}
                  </ul>
                ) : (
                  <p className="text-muted">No permissions yet. People with this role can only sign in.</p>
                )}
              </Card>
            ))}
          </div>
        )}
    </>
  );
}

function RoleForm({ role, permissions, onCancel, onSaved }:
  { role: Role | null; permissions: Permission[]; onCancel: () => void; onSaved: () => void }) {
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [isAdmin, setIsAdmin] = useState(role?.is_admin ?? false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => { ref.current?.scrollIntoView({ block: "start", behavior: "smooth" }); }, []);

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const body = { name: f.get("name"), description: f.get("description"), is_admin: isAdmin,
                   permissions: isAdmin ? [] : f.getAll("permissions") };
    setError(null);
    setBusy(true);
    try {
      await api(role ? `/api/roles/${role.id}` : "/api/roles", { method: role ? "PUT" : "POST", json: body });
      onSaved();
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  return (
    <div ref={ref} className="mb-6 scroll-mt-20">
      <Card title={role ? `Edit ${role.name}` : "New role"}>
        <form onSubmit={submit} className="space-y-5">
          <div className="grid gap-5 sm:grid-cols-2">
            <Field label="Name"><Input name="name" defaultValue={role?.name} required /></Field>
            <Field label="Description"><Input name="description" defaultValue={role?.description} /></Field>
          </div>
          <Checkbox checked={isAdmin} onChange={(e) => setIsAdmin(e.target.checked)}
                    label="Administrator" hint="Every permission, including ones added in later versions." />
          {!isAdmin && (
            <fieldset>
              <legend className="mb-1 text-sm font-medium text-ink-2">Permissions</legend>
              <div className="grid gap-x-4 sm:grid-cols-2">
                {permissions.map((p) => (
                  <Checkbox key={p.key} name="permissions" value={p.key} label={p.label}
                            defaultChecked={role?.permissions.includes(p.key)} />
                ))}
              </div>
            </fieldset>
          )}
          <Notice>{error}</Notice>
          <div className="flex flex-wrap gap-2">
            <Button type="submit" variant={role ? "success" : "primary"} disabled={busy}>{busy ? "Saving" : role ? "Save changes" : "Create role"}</Button>
            <Button type="button" variant="secondary" onClick={onCancel}>Cancel</Button>
          </div>
        </form>
      </Card>
    </div>
  );
}
