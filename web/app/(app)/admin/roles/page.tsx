"use client";

import { useState, type FormEvent } from "react";
import { RequirePermission } from "@/components/shell";
import { Button, Card, ErrorBox, Field, Input, PageTitle } from "@/components/ui";
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

  return (
    <>
      <PageTitle title="Roles & permissions" subtitle="A role is a set of permissions; each user has one role."
                 actions={<Button onClick={() => setEditing("new")}>Add role</Button>} />
      <ErrorBox message={roles.error ?? perms.error} />
      {editing && perms.data && (
        <RoleForm role={editing === "new" ? null : editing} permissions={perms.data}
                  onDone={() => { setEditing(null); roles.reload(); }} />
      )}
      <div className="grid gap-4 md:grid-cols-2">
        {roles.data?.map((r) => (
          <Card key={r.id} title={r.name} actions={<Button variant="secondary" onClick={() => setEditing(r)}>Edit</Button>}>
            {r.description && <p className="mb-2 text-sm text-neutral-600">{r.description}</p>}
            {r.is_admin ? (
              <p className="text-sm font-medium text-brand">Administrator: every permission</p>
            ) : (
              <ul className="flex flex-wrap gap-1">
                {r.permissions.length ? r.permissions.map((p) => (
                  <li key={p} className="rounded bg-neutral-100 px-2 py-0.5 text-xs">{p}</li>
                )) : <li className="text-sm text-neutral-500">No permissions</li>}
              </ul>
            )}
          </Card>
        ))}
      </div>
    </>
  );
}

function RoleForm({ role, permissions, onDone }: { role: Role | null; permissions: Permission[]; onDone: () => void }) {
  const [error, setError] = useState<string | null>(null);
  const [isAdmin, setIsAdmin] = useState(role?.is_admin ?? false);

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const body = { name: f.get("name"), description: f.get("description"), is_admin: isAdmin,
                   permissions: isAdmin ? [] : f.getAll("permissions") };
    setError(null);
    try {
      await api(role ? `/api/roles/${role.id}` : "/api/roles", { method: role ? "PUT" : "POST", json: body });
      onDone();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <div className="mb-6">
      <Card title={role ? `Edit ${role.name}` : "New role"}>
        <form onSubmit={submit} className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <Field label="Name"><Input name="name" defaultValue={role?.name} required /></Field>
            <Field label="Description"><Input name="description" defaultValue={role?.description} /></Field>
          </div>
          <label className="inline-flex items-center gap-2 text-sm font-medium">
            <input type="checkbox" checked={isAdmin} onChange={(e) => setIsAdmin(e.target.checked)} />
            Administrator (every permission, including future ones)
          </label>
          {!isAdmin && (
            <fieldset className="grid gap-2 md:grid-cols-2">
              {permissions.map((p) => (
                <label key={p.key} className="flex items-start gap-2 text-sm">
                  <input type="checkbox" name="permissions" value={p.key} defaultChecked={role?.permissions.includes(p.key)} />
                  <span><span className="font-medium">{p.key}</span> <span className="text-neutral-500">— {p.label}</span></span>
                </label>
              ))}
            </fieldset>
          )}
          <ErrorBox message={error} />
          <div className="flex gap-2">
            <Button type="submit">{role ? "Save" : "Create role"}</Button>
            <Button type="button" variant="secondary" onClick={onDone}>Cancel</Button>
          </div>
        </form>
      </Card>
    </div>
  );
}
