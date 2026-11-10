"use client";

import { useState, type ReactNode } from "react";

export type SortDir = "asc" | "desc";
export type SortState = { key: string; dir: SortDir } | null;

type Val = string | number | boolean | null | undefined;

function cmp(a: Val, b: Val): number {
  if (a == null && b == null) return 0;
  if (a == null || a === "") return 1;
  if (b == null || b === "") return -1;
  if (typeof a === "number" && typeof b === "number") return a - b;
  if (typeof a === "boolean" && typeof b === "boolean") return Number(a) - Number(b);
  const na = Number(a), nb = Number(b);
  if (typeof a !== "boolean" && typeof b !== "boolean" && a !== "" && b !== "" && Number.isFinite(na) && Number.isFinite(nb)) return na - nb;
  return String(a).localeCompare(String(b), undefined, { numeric: true, sensitivity: "base" });
}

/** Client-side sort for a table. Pass a getter per column key. */
export function sortRows<T>(rows: T[], sort: SortState, get: Record<string, (row: T) => Val>): T[] {
  if (!sort || !get[sort.key]) return rows;
  const g = get[sort.key];
  const mul = sort.dir === "asc" ? 1 : -1;
  return [...rows].sort((a, b) => mul * cmp(g(a), g(b)));
}

/** Click cycles none → ascending → descending → none. */
export function useTableSort(initial: SortState = null) {
  const [sort, setSort] = useState<SortState>(initial);
  const set = (key: string) =>
    setSort((s) => (s?.key !== key ? { key, dir: "asc" } : s.dir === "asc" ? { key, dir: "desc" } : null));
  return { sort, set };
}

/**
 * Sortable column head: label + one dual caret (▲▼), matching workshop table chrome.
 * Click the whole head to cycle sort. Active direction fills darker; the other stays muted.
 */
export function SortTh({ label, k, sort, onSort, className = "", align = "left" }:
  { label: ReactNode; k: string; sort: SortState; onSort: (key: string) => void; className?: string; align?: "left" | "right" }) {
  const active = sort?.key === k ? sort.dir : null;
  const name = typeof label === "string" ? label : k;
  return (
    <th className={className} aria-sort={active === "asc" ? "ascending" : active === "desc" ? "descending" : "none"}>
      <button type="button" onClick={() => onSort(k)}
              aria-label={active ? `Sorted ${name} ${active === "asc" ? "ascending" : "descending"}. Change sort.` : `Sort by ${name}`}
              className={`inline-flex min-h-11 cursor-pointer items-center gap-1.5 rounded-control text-inherit transition-colors duration-330 hover:text-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink ${align === "right" ? "w-full justify-end" : ""}`}>
        <span className="whitespace-nowrap">{label}</span>
        <SortCarets active={active} />
      </button>
    </th>
  );
}

/** Compact up+down carets beside the label (inactive both pewter; active direction Carbon). */
function SortCarets({ active }: { active: SortDir | null }) {
  return (
    <svg width="8" height="12" viewBox="0 0 8 12" aria-hidden="true" className="shrink-0 translate-y-px">
      <path d="M4 1.25L7.1 4.75H0.9L4 1.25Z" fill="currentColor" className={active === "asc" ? "text-ink" : "text-muted/45"} />
      <path d="M4 10.75L0.9 7.25H7.1L4 10.75Z" fill="currentColor" className={active === "desc" ? "text-ink" : "text-muted/45"} />
    </svg>
  );
}
