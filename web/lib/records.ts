"use client";

import { useEffect } from "react";
import { create } from "zustand";
import { api } from "./api";

type Kind = "cars" | "customers";
type Entry = { data?: unknown; error?: string };

/**
 * One client-side copy of each car and customer. Every form that saves one
 * calls `put`, so every panel showing that record updates at once.
 */
export const useRecords = create<{
  cars: Record<string, Entry>; customers: Record<string, Entry>;
  put: (kind: Kind, record: { id: string }) => void;
  load: (kind: Kind, id: string) => Promise<void>;
}>()((set) => ({
  cars: {},
  customers: {},
  put: (kind, record) => set((s) => ({ [kind]: { ...s[kind], [record.id]: { data: record } } })),
  load: async (kind, id) => {
    try {
      const data = await api<{ id: string }>(`/api/${kind}/${id}`);
      set((s) => ({ [kind]: { ...s[kind], [id]: { data } } }));
    } catch (e) {
      set((s) => ({ [kind]: { ...s[kind], [id]: { error: (e as Error).message } } }));
    }
  },
}));

/** Read a car or customer from the store, fetching it the first time. */
export function useRecord<T>(kind: Kind, id: string | null | undefined) {
  const entry = useRecords((s) => (id ? s[kind][id] : undefined));
  const load = useRecords((s) => s.load);
  useEffect(() => { if (id) load(kind, id); }, [kind, id, load]);
  return { data: entry?.data as T | undefined, error: entry?.error ?? null, reload: () => id && load(kind, id) };
}
