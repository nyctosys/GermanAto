"use client";

import { useState } from "react";
import { Button, Input, Notice, Select } from "@/components/ui";
import { api, useApi } from "@/lib/api";

export type ListKind = "part_brand" | "part_category" | "car_make" | "labour_category" | "fitment";
type Entry = { id: string; name: string };

const ADD = "__add";

/** A pick-list the team keeps themselves. A new name is added with "Add to list": the server tidies the spelling
 *  and asks "Did you mean ...?" when it looks like a typo of one already there. Posts its value under `name`. */
export function ListSelect({ name, kind, defaultValue = "", placeholder = "Choose", onChange }:
  { name: string; kind: ListKind; defaultValue?: string; placeholder?: string; onChange?: (v: string) => void }) {
  const list = useApi<Entry[]>(`/api/lists/${kind}`);
  const [pick, setPick] = useState(defaultValue);
  const [adding, setAdding] = useState(false);
  const [typed, setTyped] = useState("");
  const [near, setNear] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const names = (list.data ?? []).map((e) => e.name);
  const options = pick && !names.some((n) => n.toLowerCase() === pick.toLowerCase()) ? [pick, ...names] : names;

  function choose(v: string) { setPick(v); onChange?.(v); }

  async function add(confirm = false) {
    if (!typed.trim()) { setError("Type the name first."); return; }
    setBusy(true);
    setError(null);
    try {
      const r = await api<{ name: string }>(`/api/lists/${kind}`, { method: "POST", json: { name: typed, confirm }, toast: "Added to the list" });
      list.reload();
      choose(r.name);
      setAdding(false); setTyped(""); setNear(null);
    } catch (e) {
      const m = (e as Error).message;
      const close = m.match(/^Did you mean (.+)\?/);
      if (close) setNear(close[1]); else setError(m);
    }
    setBusy(false);
  }

  return (
    <div className="flex flex-col gap-2">
      <Select aria-label={name} value={adding ? ADD : pick} onChange={(e) => {
        if (e.target.value === ADD) { setAdding(true); setNear(null); setError(null); } else { setAdding(false); choose(e.target.value); }
      }}>
        <option value="">{placeholder}</option>
        {options.map((o) => <option key={o} value={o}>{o}</option>)}
        <option value={ADD}>+ Add a new one to the list</option>
      </Select>
      {adding && (
        <div className="flex flex-col gap-2 rounded-control border border-rule bg-paper-3 p-3">
          <Input aria-label={`${name}, new`} value={typed} maxLength={60} placeholder="Type the new name" autoFocus
            onChange={(e) => { setTyped(e.target.value); setNear(null); setError(null); }}
            onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); void add(); } }} />
          {near && (
            <Notice tone="warning">
              Did you mean <strong>{near}</strong>?
              <span className="mt-2 flex flex-wrap gap-2">
                <Button type="button" onClick={() => { choose(near); setAdding(false); setTyped(""); setNear(null); }}>Yes, use {near}</Button>
                <Button type="button" variant="secondary" disabled={busy} onClick={() => add(true)}>No, add mine</Button>
              </span>
            </Notice>
          )}
          {error && <p role="alert" className="text-sm text-error">{error}</p>}
          {!near && (
            <div className="flex flex-wrap gap-2">
              <Button type="button" disabled={busy} onClick={() => add()}>Add to list</Button>
              <Button type="button" variant="secondary" onClick={() => { setAdding(false); setTyped(""); setError(null); }}>Cancel</Button>
            </div>
          )}
          <p className="text-sm text-muted">It joins the list for everyone, and the spelling is checked.</p>
        </div>
      )}
      <input type="hidden" name={name} value={pick} />
    </div>
  );
}
