"use client";

import { DeleteButton } from "@/components/delete-button";
import { useState, type FormEvent } from "react";
import { RequirePermission } from "@/components/shell";
import { Badge, Button, Card, ErrorState, Input, Notice, PageHeader, SkeletonRows } from "@/components/ui";
import type { ListKind } from "@/components/list-select";
import { api, useApi } from "@/lib/api";

type Entry = { id: string; name: string; is_active: boolean };

const LISTS: { kind: ListKind; title: string; note: string }[] = [
  { kind: "part_brand", title: "Part brands", note: "Shown when adding stock." },
  { kind: "part_category", title: "Part categories", note: "Shown when adding stock." },
  { kind: "car_make", title: "Car makes", note: "Shown when adding a car." },
  { kind: "fitment", title: "Cars a part fits", note: "Shown in the Fits box when adding stock." },
  { kind: "labour_category", title: "Labour categories", note: "Shown when adding a labour code." },
];

export default function ListsSettingsPage() {
  return (
    <RequirePermission permission="settings">
      <PageHeader title="Pick-lists" description="The choices people pick from in forms. Anyone can add a new one from the form itself; here you can fix a name or hide one nobody should use." />
      <div className="grid gap-4 shell:grid-cols-2">
        {LISTS.map((l) => <ListCard key={l.kind} {...l} />)}
      </div>
    </RequirePermission>
  );
}

function ListCard({ kind, title, note }: { kind: ListKind; title: string; note: string }) {
  const list = useApi<Entry[]>(`/api/lists/${kind}?all=true`);
  const [editing, setEditing] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [newName, setNewName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [near, setNear] = useState<string | null>(null);

  async function save(id: string, body: object) {
    setError(null);
    try { await api(`/api/lists/${kind}/${id}`, { method: "PUT", json: body }); setEditing(null); list.reload(); }
    catch (e) { setError((e as Error).message); }
  }
  async function add(e: FormEvent, confirm = false) {
    e.preventDefault();
    setError(null);
    try { await api(`/api/lists/${kind}`, { method: "POST", json: { name: newName, confirm }, toast: "Added to the list" }); setNewName(""); setNear(null); list.reload(); }
    catch (err) {
      const m = (err as Error).message.match(/^Did you mean (.+)\?/);
      if (m) setNear(m[1]); else setError((err as Error).message);
    }
  }

  return (
    <Card title={title} flush>
      <form onSubmit={add} className="flex flex-wrap items-end gap-2 px-4 py-3 shell:px-5">
        <div className="min-w-0 flex-1"><Input aria-label={`New ${title.toLowerCase()}`} value={newName} maxLength={60} placeholder="Add a new one" onChange={(e) => { setNewName(e.target.value); setNear(null); }} /></div>
        <Button type="submit" disabled={!newName.trim()}>Add</Button>
      </form>
      {near && (
        <div className="px-4 pb-3 shell:px-5">
          <Notice tone="warning">Did you mean <strong>{near}</strong>? It is already in the list.
            <span className="mt-2 flex flex-wrap gap-2">
              <Button type="button" variant="secondary" onClick={() => { setNewName(""); setNear(null); }}>Yes, that one</Button>
              <Button type="button" variant="secondary" onClick={(e) => add(e, true)}>No, add mine</Button>
            </span>
          </Notice>
        </div>
      )}
      {error && <div className="px-4 pb-3 shell:px-5"><Notice>{error}</Notice></div>}
      {list.error ? <ErrorState message={list.error} onRetry={list.reload} /> : !list.data ? <SkeletonRows rows={4} /> : (
        <ul>
          {list.data.map((e) => (
            <li key={e.id} className="flex flex-wrap items-center justify-between gap-2 border-t border-rule px-4 py-2 shell:px-5">
              {editing === e.id ? (
                <form className="flex min-w-0 flex-1 flex-wrap items-center gap-2" onSubmit={(ev) => { ev.preventDefault(); void save(e.id, { name }); }}>
                  <div className="min-w-0 flex-1"><Input aria-label="Name" value={name} maxLength={60} autoFocus onChange={(ev) => setName(ev.target.value)} /></div>
                  <Button type="submit">Save</Button>
                  <Button type="button" variant="secondary" onClick={() => setEditing(null)}>Cancel</Button>
                </form>
              ) : (
                <>
                  <span className={e.is_active ? "" : "text-muted line-through"}>{e.name} {!e.is_active && <Badge>Hidden</Badge>}</span>
                  <span className="flex gap-2">
                    <Button variant="secondary" onClick={() => { setEditing(e.id); setName(e.name); setError(null); }}>Rename</Button>
                    <Button variant="secondary" onClick={() => save(e.id, { is_active: !e.is_active })}>{e.is_active ? "Hide" : "Show again"}</Button>
                    <DeleteButton path={`/api/lists/${kind}/${e.id}`} what="entry" onDone={list.reload} />
                  </span>
                </>
              )}
            </li>
          ))}
        </ul>
      )}
      <p className="border-t border-rule px-4 py-3 text-sm text-muted shell:px-5">{note} Renaming also fixes the name on records that already use it. Hiding keeps old records as they are.</p>
    </Card>
  );
}
