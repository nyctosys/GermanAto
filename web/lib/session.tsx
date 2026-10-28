"use client";

import { useEffect, type ReactNode } from "react";
import { create } from "zustand";
import { ErrorState } from "@/components/ui";
import { api } from "./api";

export type Branch = { id: string; code: string; name: string };
export type Me = {
  user: { id: string; username: string; full_name: string };
  role: { id: string; name: string; is_admin: boolean };
  permissions: string[];
  branch: Branch;
  branches: Branch[];
};

/** The signed-in user, their role and branch: one store any component can read. */
export const useSessionStore = create<{ me: Me | null; error: string | null; load: () => Promise<void> }>()((set) => ({
  me: null,
  error: null,
  load: async () => {
    try {
      set({ me: await api<Me>("/api/auth/me"), error: null });
    } catch (e) {
      set({ error: (e as Error).message });
    }
  },
}));

export function SessionProvider({ children }: { children: ReactNode }) {
  const { me, error, load } = useSessionStore();
  useEffect(() => { load(); }, [load]);
  if (error && !me) {
    return (
      <div className="mx-auto mt-16 max-w-md px-4">
        <ErrorState message={`Your account couldn't be loaded: ${error}`} onRetry={load} />
      </div>
    );
  }
  if (!me) {
    return (
      <div aria-busy="true" aria-label="Loading" className="flex min-h-dvh">
        <div className="hidden w-64 shrink-0 border-r border-rule bg-paper-2 shell:block" />
        <div className="flex-1 space-y-4 p-10">
          <div className="skeleton h-8 w-64" />
          <div className="skeleton h-40 w-full max-w-3xl" />
        </div>
      </div>
    );
  }
  return children;
}

/** Only valid inside <SessionProvider>, which renders children once `me` has loaded. */
export function useSession() {
  const me = useSessionStore((s) => s.me);
  const reload = useSessionStore((s) => s.load);
  if (!me) throw new Error("useSession must be used inside <SessionProvider>");
  return { ...me, can: (p: string) => me.permissions.includes(p), reload };
}
