"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { RequirePermission } from "@/components/shell";
import {
  Badge, Button, Card, Checkbox, EmptyState, ErrorState, Field, Input, Notice, PageHeader, Select, SkeletonRows,
} from "@/components/ui";
import { useFormErrors } from "@/lib/form";
import { parseForm, userSchema } from "@/lib/schemas";
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
      <PageHeader
        title="Users"
        description="Everyone signs in with their own account, so every change is logged under their name."
        actions={<Button onClick={() => setEditing("new")} disabled={!roles.data}>Add user</Button>}
      />
      {editing && roles.data && (
        <UserForm
          key={editing === "new" ? "new" : editing.id}
          user={editing === "new" ? null : editing}
          roles={roles.data}
          onCancel={() => setEditing(null)}
          onSaved={() => { setEditing(null); users.reload(); }}
        />
      )}
      <Card flush>
        {users.error ? <ErrorState message={users.error} onRetry={users.reload} />
          : !users.data ? <SkeletonRows />
          : !users.data.length ? (
            <EmptyState title="No users yet" action={<Button onClick={() => setEditing("new")}>Add user</Button>}>
              Add an account for each person who works on the system.
            </EmptyState>
          ) : (
            <table className="table-stack w-full text-left">
              <thead className="border-b border-rule text-sm text-muted">
                <tr>
                  <th className="px-5 py-3 font-medium">Name</th>
                  <th className="px-3 py-3 font-medium">Role</th>
                  <th className="px-3 py-3 font-medium">Phone</th>
                  <th className="px-3 py-3 font-medium">Last sign-in</th>
                  <th className="px-3 py-3 font-medium">Status</th>
                  <th className="px-5 py-3"><span className="sr-only">Actions</span></th>
                </tr>
              </thead>
              <tbody>
                {users.data.map((u) => (
                  <tr key={u.id} className="border-t border-rule first:border-t-0">
                    <td className="px-5 py-3 max-sm:px-0">
                      <span className="block font-medium">{u.full_name}</span>
                      <span className="block text-sm text-muted">{u.username}</span>
                    </td>
                    <td data-label="Role" className="px-3 py-3 max-sm:px-0">{u.role_name}</td>
                    <td data-label="Phone" className="num px-3 py-3 max-sm:px-0">{u.phone || "None"}</td>
                    <td data-label="Last sign-in" className="px-3 py-3 max-sm:px-0">
                      {u.last_login_at ? new Date(u.last_login_at).toLocaleString() : "Never"}
                    </td>
                    <td data-label="Status" className="px-3 py-3 max-sm:px-0">
                      {!u.is_active ? <Badge>Disabled</Badge> : u.locked ? <Badge tone="warning">Locked</Badge> : <Badge tone="success">Active</Badge>}
                    </td>
                    <td className="px-5 py-2 text-right max-sm:px-0 max-sm:pt-2">
                      <Button variant="secondary" onClick={() => setEditing(u)} className="max-sm:w-full">Edit</Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
      </Card>
    </>
  );
}

function UserForm({ user, roles, onCancel, onSaved }:
  { user: User | null; roles: Role[]; onCancel: () => void; onSaved: () => void }) {
  const { branches, user: me } = useSession();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const isSelf = user?.id === me.id;

  // On a phone the form opens above a long list; bring it into view.
  useEffect(() => { ref.current?.scrollIntoView({ block: "start", behavior: "smooth" }); }, []);

  const schema = () => userSchema.extend({ password: user ? userSchema.shape.password : userSchema.shape.password.refine(Boolean, "Required") });
  const { errors, setErrors, live, applyApi } = useFormErrors(schema);
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const branchIds = f.getAll("branch_ids");
    const { data, errors } = parseForm(schema(), e.currentTarget);
    setErrors(errors ?? {});
    if (!data) return;
    if (!branchIds.length) {
      setError("Pick at least one branch.");
      return;
    }
    const body: Record<string, unknown> = { full_name: data.full_name, email: data.email, phone: data.phone, branch_ids: branchIds };
    if (!isSelf) {
      body.role_id = f.get("role_id");
      body.is_active = f.get("is_active") === "on";
    }
    if (data.password) body.password = data.password;
    setError(null);
    setBusy(true);
    try {
      if (user) await api(`/api/users/${user.id}`, { method: "PATCH", json: body });
      else await api("/api/users", { method: "POST", json: { ...body, username: data.username } });
      onSaved();
    } catch (err) {
      setError(applyApi(err));
      setBusy(false);
    }
  }

  return (
    <div ref={ref} className="mb-6 scroll-mt-20">
      <Card title={user ? `Edit ${user.full_name}` : "New user"}>
        <form onSubmit={submit} noValidate className="grid gap-5 sm:grid-cols-2" {...live}>
          {user ? (
            <Field label="Username" hint="Usernames can't be changed."><Input value={user.username} disabled readOnly /></Field>
          ) : (
            <Field error={errors.username} label="Username" hint="3 to 32 letters, digits, dots, dashes or underscores.">
              <Input name="username" required pattern="[A-Za-z0-9._\-]{3,32}" autoCapitalize="none" spellCheck={false} />
            </Field>
          )}
          <Field error={errors.full_name} label="Full name"><Input name="full_name" defaultValue={user?.full_name} required autoComplete="off" /></Field>
          <Field error={errors.phone} label="Phone"><Input name="phone" defaultValue={user?.phone} inputMode="tel" placeholder="+92 300 1234567" /></Field>
          <Field error={errors.email} label="Email (optional)"><Input name="email" type="email" defaultValue={user?.email ?? ""} /></Field>
          <Field label="Role" hint={isSelf ? "You can't change your own role." : undefined}>
            <Select name="role_id" defaultValue={user?.role_id} required disabled={isSelf}>
              {roles.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
            </Select>
          </Field>
          <Field error={errors.password} label={user ? "New password" : "Password"} hint={user ? "Leave blank to keep the current one. At least 8 characters." : "At least 8 characters."}>
            <Input name="password" type="password" minLength={8} required={!user} autoComplete="new-password" />
          </Field>
          <fieldset className="sm:col-span-2">
            <legend className="mb-1 text-sm font-medium text-ink-2">Branches</legend>
            <div className="grid gap-x-4 sm:grid-cols-2">
              {branches.map((b) => (
                <Checkbox key={b.id} name="branch_ids" value={b.id} label={b.name}
                          defaultChecked={user ? user.branch_ids.includes(b.id) : branches.length === 1} />
              ))}
            </div>
          </fieldset>
          {!isSelf && (
            <div className="sm:col-span-2">
              <Checkbox name="is_active" defaultChecked={user?.is_active ?? true} label="Account active"
                        hint="A disabled account can't sign in. Its history stays." />
            </div>
          )}
          <div className="flex flex-col gap-3 sm:col-span-2">
            <Notice>{error}</Notice>
            <div className="flex flex-wrap gap-2">
              <Button type="submit" variant={user ? "success" : "primary"} disabled={busy}>{busy ? "Saving" : user ? "Save changes" : "Create user"}</Button>
              <Button type="button" variant="danger" onClick={onCancel}>Cancel</Button>
            </div>
          </div>
        </form>
      </Card>
    </div>
  );
}
