"use client";

import { createContext, useContext, type ReactNode } from "react";
import { useApi } from "./api";

export type Branch = { id: string; code: string; name: string };
export type Me = {
  user: { id: string; username: string; full_name: string };
  role: { id: string; name: string; is_admin: boolean };
  permissions: string[];
  branch: Branch;
  branches: Branch[];
};

const SessionContext = createContext<(Me & { can: (p: string) => boolean; reload: () => void }) | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const { data, error, reload } = useApi<Me>("/api/auth/me");
  if (error) return <p className="p-8 text-red-700">Could not load your account: {error}</p>;
  if (!data) return <p className="p-8 text-neutral-500">Loading…</p>;
  const can = (p: string) => data.permissions.includes(p);
  return <SessionContext.Provider value={{ ...data, can, reload }}>{children}</SessionContext.Provider>;
}

export function useSession() {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession must be used inside <SessionProvider>");
  return ctx;
}
