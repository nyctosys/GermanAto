"use client";

import { useState, type FormEvent } from "react";
import { RequirePermission } from "@/components/shell";
import { Button, Card, ErrorBox, Field, Input, PageTitle, Select } from "@/components/ui";
import { api, useApi } from "@/lib/api";
import { useSession } from "@/lib/session";

type User = {
  id: string; username: string; full_name: string; email: string | null; phone: string; role_id: string;
  role_name: string; branch_ids: string[]; is_active: boolean; last_login_at: string | null; locked: boolean;
};
type Role = { id: string; name: string };

export default function UsersPage() {
  return (
    <RequirePermission permission="users">
      <Users />
    </RequirePermission>
  );
}

function Users() {
  const users = useApi<User[]>("/api/users");
  const roles = useApi<Role[]>("/api/roles");
  const [editing, setEditing] = useState<User | "new" | null>(null);

  return (
    <>
      <PageTitle
        title="Users"
        subtitle="Everyone signs in with their own account; every change they make is logged under their name."
        actions={<Button onClick={() => setEditing("new")}>Add user</Button>}
      />
      <ErrorBox message={users.error} />
      {editing && roles.data && (
        <UserForm user={editing === "new" ? null : editing} roles={roles.data}
                  onDone={() => { setEditing(null); users.reload(); }} />
      )}
      <Card>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-left text-neutral-500">
              <tr><th className="py-2">Name</th><th>Username</th><th>Role</th><th>Phone</th><th>Last sign-in</th><th>Status</th><th /></tr>
            </thead>
            <tbody>
              {users.data?.map((u) => (
                <tr key={u.id} className="border-t border-neutral-100">
                  <td className="py-2 font-medium">{u.full_name}</td>
                  <td>{u.username}</td>
                  <td>{u.role_name}</td>
                  <td>{u.phone || "—"}</td>
                  <td>{u.last_login_at ? new Date(u.last_login_at).toLocaleString() : "Never"}</td>
                  <td>
                    {!u.is_active ? <span className="text-neutral-400">Disabled</span>
                      : u.locked ? <span className="text-amber-700">Locked</span>
                      : <span className="text-green-700">Active</span>}
                  </td>
                  <td className="text-right"><Button variant="secondary" onClick={() => setEditing(u)}>Edit</Button></td>
                </tr>
              ))}
            </tbody>
          </table>
          {users.loading && <p className="py-4 text-neutral-500">Loading…</p>}
        </div>
      </Card>
    </>
  );
}

function UserForm({ user, roles, onDone }: { user: User | null; roles: Role[]; onDone: () => void }) {
  const { branches } = useSession();
  const [error, setError] = useState<string | null>(null);

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const body: Record<string, unknown> = {
      full_name: f.get("full_name"), email: f.get("email"), phone: f.get("phone"), role_id: f.get("role_id"),
      branch_ids: f.getAll("branch_ids"), is_active: f.get("is_active") === "on",
    };
    const password = String(f.get("password") || "");
    if (password) body.password = password;
    setError(null);
    try {
      if (user) await api(`/api/users/${user.id}`, { method: "PATCH", json: body });
      else await api("/api/users", { method: "POST", json: { ...body, username: f.get("username") } });
      onDone();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <div className="mb-6">
      <Card title={user ? `Edit ${user.full_name}` : "New user"}>
        <form onSubmit={submit} className="grid gap-4 md:grid-cols-2">
          {!user && (
            <Field label="Username" hint="3–32 characters: letters, digits, . _ -">
              <Input name="username" required pattern="[A-Za-z0-9._\-]{3,32}" />
            </Field>
          )}
          <Field label="Full name"><Input name="full_name" defaultValue={user?.full_name} required /></Field>
          <Field label="Phone"><Input name="phone" defaultValue={user?.phone} inputMode="tel" /></Field>
          <Field label="Email (optional)"><Input name="email" type="email" defaultValue={user?.email ?? ""} /></Field>
          <Field label="Role">
            <Select name="role_id" defaultValue={user?.role_id} required>
              {roles.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
            </Select>
          </Field>
          <Field label={user ? "New password (leave blank to keep)" : "Password"} hint="At least 8 characters">
            <Input name="password" type="password" minLength={8} required={!user} autoComplete="new-password" />
          </Field>
          <fieldset className="text-sm">
            <legend className="mb-1 font-medium text-neutral-700">Branches</legend>
            {branches.map((b) => (
              <label key={b.id} className="mr-4 inline-flex items-center gap-1">
                <input type="checkbox" name="branch_ids" value={b.id}
                       defaultChecked={user ? user.branch_ids.includes(b.id) : branches.length === 1} />
                {b.name}
              </label>
            ))}
          </fieldset>
          <label className="inline-flex items-center gap-2 text-sm">
            <input type="checkbox" name="is_active" defaultChecked={user?.is_active ?? true} /> Account active
          </label>
          <div className="md:col-span-2"><ErrorBox message={error} /></div>
          <div className="flex gap-2 md:col-span-2">
            <Button type="submit">{user ? "Save" : "Create user"}</Button>
            <Button type="button" variant="secondary" onClick={onDone}>Cancel</Button>
          </div>
        </form>
      </Card>
    </div>
  );
}
