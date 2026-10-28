"use client";

import { createContext, useContext, type ReactNode } from "react";
import { ErrorState } from "@/components/ui";
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
  if (error) {
    return (
      <div className="mx-auto mt-16 max-w-md px-4">
        <ErrorState message={`Your account couldn't be loaded: ${error}`} onRetry={reload} />
      </div>
    );
  }
  if (!data) {
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
  const can = (p: string) => data.permissions.includes(p);
  return <SessionContext.Provider value={{ ...data, can, reload }}>{children}</SessionContext.Provider>;
}

export function useSession() {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession must be used inside <SessionProvider>");
  return ctx;
}
