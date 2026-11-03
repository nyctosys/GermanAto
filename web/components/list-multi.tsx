"use client";

import { useEffect, useRef, useState } from "react";
import { Button, Input, Notice } from "@/components/ui";
import { api, useApi } from "@/lib/api";

type Entry = { id: string; name: string };

/** Search a list the team keeps and tick as many as fit; a name not in it yet is added with one click and is there next time.
 *  Posts the ticked names joined by "; " under `name`. The server tidies spelling and asks "Did you mean ...?". */
export function ListMulti({ name, kind, defaultValue = "", placeholder = "Search or add a car" }:
  { name: string; kind: string; defaultValue?: string; placeholder?: string }) {
  const list = useApi<Entry[]>(`/api/lists/${kind}`);
  const [picked, setPicked] = useState<string[]>(() => defaultValue.split(/[;,]/).map((s) => s.trim()).filter(Boolean));
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [near, setNear] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const away = (e: MouseEvent) => { if (box.current && !box.current.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("mousedown", away);
    return () => document.removeEventListener("mousedown", away);
  }, []);

  const has = (n: string) => picked.some((p) => p.toLowerCase() === n.toLowerCase());
  const toggle = (n: string) => setPicked((p) => (has(n) ? p.filter((x) => x.toLowerCase() !== n.toLowerCase()) : [...p, n]));
  const names = (list.data ?? []).map((e) => e.name);
  const all = [...names, ...picked.filter((p) => !names.some((n) => n.toLowerCase() === p.toLowerCase()))];
  const shown = all.filter((n) => n.toLowerCase().includes(q.trim().toLowerCase()));
  const exact = all.some((n) => n.toLowerCase() === q.trim().toLowerCase());

  async function add(confirm = false) {
    setBusy(true); setError(null);
    try {
      const r = await api<{ name: string }>(`/api/lists/${kind}`, { method: "POST", json: { name: q, confirm }, toast: "Added to the list" });
      list.reload();
      if (!has(r.name)) setPicked((p) => [...p, r.name]);
      setQ(""); setNear(null);
    } catch (e) {
      const m = (e as Error).message;
      const close = m.match(/^Did you mean (.+)\?/);
      if (close) setNear(close[1]); else setError(m);
    }
    setBusy(false);
  }

  return (
    <div ref={box} className="relative flex flex-col gap-2">
      {picked.length > 0 && (
        <ul className="flex flex-wrap gap-2">
          {picked.map((p) => (
            <li key={p} className="flex items-center gap-1 rounded-control border border-rule bg-paper-3 py-1 pl-3 pr-1 text-sm">
              <span>{p}</span>
              <button type="button" aria-label={`Remove ${p}`} className="rounded px-2 text-muted hover:text-error"
                onClick={(e) => { e.stopPropagation(); toggle(p); }}>×</button>
            </li>
          ))}
        </ul>
      )}
      <Input aria-label={`${name}, search`} value={q} placeholder={placeholder} autoComplete="off" maxLength={60}
        onFocus={() => setOpen(true)} onChange={(e) => { setQ(e.target.value); setOpen(true); setNear(null); setError(null); }}
        onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); if (q.trim() && !exact) void add(); } if (e.key === "Escape") setOpen(false); }} />
      {open && (
        <div className="absolute left-0 right-0 top-full z-20 mt-1 max-h-64 overflow-auto rounded-control border border-rule bg-paper shadow-lg" role="listbox" aria-multiselectable="true">
          {shown.map((n) => (
            <div key={n} role="option" aria-selected={has(n)}
              className="flex cursor-pointer items-center gap-3 px-3 py-2 hover:bg-paper-3"
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => toggle(n)}>
              <input type="checkbox" tabIndex={-1} readOnly checked={has(n)} className="pointer-events-none size-4 accent-primary" />
              {n}
            </div>
          ))}
          {!shown.length && !q.trim() && <p className="px-3 py-2 text-sm text-muted">Nothing in the list yet. Type a car to add it.</p>}
          {q.trim() && !exact && (
            <button type="button" disabled={busy} onClick={() => add()} className="block w-full border-t border-rule px-3 py-2 text-left font-medium text-primary hover:bg-paper-3">
              + Add “{q.trim()}” to the list
            </button>
          )}
        </div>
      )}
      {near && (
        <Notice tone="warning">
          Did you mean <strong>{near}</strong>?
          <span className="mt-2 flex flex-wrap gap-2">
            <Button type="button" onClick={() => { if (!has(near)) setPicked((p) => [...p, near]); setQ(""); setNear(null); }}>Yes, use {near}</Button>
            <Button type="button" variant="secondary" disabled={busy} onClick={() => add(true)}>No, add mine</Button>
          </span>
        </Notice>
      )}
      {error && <p role="alert" className="text-sm text-error">{error}</p>}
      <input type="hidden" name={name} value={picked.join("; ")} />
    </div>
  );
}
