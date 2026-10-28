"use client";

import { useRouter } from "next/navigation";
import { useEffect, useId, useMemo, useRef, useState, useSyncExternalStore } from "react";

export type Command = { label: string; group: string; href: string; keys?: string };

/** ⌘ on Apple devices, Ctrl everywhere else. Decided after mount so the server and browser render the same HTML. */
export function useModKey() {
  return useSyncExternalStore(() => () => {}, () => (/Mac|iPhone|iPad/.test(navigator.platform) ? "⌘" : "Ctrl"), () => "Ctrl");
}

export const Kbd = ({ children }: { children: React.ReactNode }) => (
  <kbd className="rounded-control border border-rule-strong bg-paper px-1.5 py-0.5 font-sans text-xs text-ink-2">{children}</kbd>
);

/** True while the person is typing, so a shortcut never steals a letter. */
const typing = (t: EventTarget | null) => {
  const el = t as HTMLElement | null;
  return !!el && (el.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName));
};

/**
 * Cmd/Ctrl+K opens a search of every page and action, usable with the keyboard alone.
 * "g" then a letter jumps straight to a page (shown as a hint beside each command).
 */
export function CommandMenu({ commands, open, setOpen }: { commands: Command[]; open: boolean; setOpen: (v: boolean) => void }) {
  const router = useRouter();
  const pending = useRef<number | null>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setOpen(!open); return; }
      if (open || e.metaKey || e.ctrlKey || e.altKey || typing(e.target)) return;
      if (pending.current) {
        window.clearTimeout(pending.current);
        pending.current = null;
        const hit = commands.find((c) => c.keys === `g ${e.key.toLowerCase()}`);
        if (hit) { e.preventDefault(); router.push(hit.href); }
      } else if (e.key === "g") {
        pending.current = window.setTimeout(() => { pending.current = null; }, 1200);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [commands, open, router, setOpen]);

  return open ? <Palette commands={commands} close={() => setOpen(false)} /> : null;
}

// Mounted only while open, so each opening starts with an empty search.
function Palette({ commands, close }: { commands: Command[]; close: () => void }) {
  const router = useRouter();
  const mod = useModKey();
  const [q, setQ] = useState("");
  const [active, setActive] = useState(0);
  const listId = useId();
  const [from] = useState(() => document.activeElement as HTMLElement | null);
  // Give focus back to what opened the menu, once it has really closed (React's dev double-mount must not count).
  useEffect(() => () => { window.setTimeout(() => { if (!document.querySelector("[data-palette]")) from?.focus(); }); }, [from]);

  const shown = useMemo(() => {
    const words = q.toLowerCase().split(/\s+/).filter(Boolean);
    return commands.filter((c) => words.every((w) => `${c.label} ${c.group}`.toLowerCase().includes(w)));
  }, [commands, q]);
  const setOpen = (v: boolean) => { if (!v) close(); };
  const run = (c: Command | undefined) => { if (c) { setOpen(false); router.push(c.href); } };

  return (
    <div className="no-print fixed inset-0 z-50 flex items-start justify-center px-4 pt-[12vh]">
      <button aria-label="Close search" tabIndex={-1} className="absolute inset-0 bg-scrim" onClick={() => setOpen(false)} />
      <div data-palette role="dialog" aria-modal="true" aria-label="Search pages and actions" className="relative w-full max-w-lg overflow-hidden rounded-card bg-surface">
        <input
          autoFocus role="combobox" aria-expanded="true" aria-controls={listId} aria-activedescendant={shown[active] ? `${listId}-${active}` : undefined}
          aria-label="Search pages and actions" placeholder="Go to a page or start something..." value={q} enterKeyHint="go"
          onChange={(e) => { setQ(e.target.value); setActive(0); }}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") { e.preventDefault(); setActive((a) => Math.min(a + 1, shown.length - 1)); }
            else if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)); }
            else if (e.key === "Enter") { e.preventDefault(); run(shown[active]); }
            else if (e.key === "Escape") { e.preventDefault(); setOpen(false); }
            else if (e.key === "Tab") e.preventDefault(); // focus stays in the menu until it closes
          }}
          className="min-h-12 w-full border-b border-rule bg-surface px-4 text-base placeholder:text-muted focus-visible:outline-none"
        />
        <ul id={listId} role="listbox" className="max-h-[50vh] overflow-auto py-1">
          {shown.length ? shown.map((c, i) => (
            <li key={c.href} id={`${listId}-${i}`} role="option" aria-selected={i === active}
                onMouseMove={() => setActive(i)} onClick={() => run(c)}
                className={`flex min-h-11 cursor-pointer items-center justify-between gap-3 px-4 ${i === active ? "bg-accent-soft" : ""}`}>
              <span className="min-w-0"><span className="font-medium">{c.label}</span> <span className="text-sm text-muted">{c.group}</span></span>
              {c.keys && <span className="flex shrink-0 gap-1">{c.keys.split(" ").map((k) => <Kbd key={k}>{k.toUpperCase()}</Kbd>)}</span>}
            </li>
          )) : <li className="px-4 py-3 text-muted">Nothing matches “{q}”.</li>}
        </ul>
        <p className="flex flex-wrap gap-x-4 gap-y-1 border-t border-rule px-4 py-2 text-sm text-muted">
          <span><Kbd>↑</Kbd> <Kbd>↓</Kbd> to move</span><span><Kbd>Enter</Kbd> to open</span><span><Kbd>Esc</Kbd> to close</span><span>Open anywhere with <Kbd>{mod}</Kbd> <Kbd>K</Kbd></span>
        </p>
      </div>
    </div>
  );
}
