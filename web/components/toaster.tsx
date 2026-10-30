"use client";

import { useToasts } from "@/lib/toast";

/** Notices for what just happened ("Payment recorded"). Announced to screen readers, never blocks the screen, and does not animate. */
export function Toaster() {
  const { toasts, dismiss } = useToasts();
  return (
    <div aria-live="polite" className="no-print pointer-events-none fixed inset-x-0 top-0 z-[60] flex flex-col items-center gap-2 px-4 pt-[max(1rem,env(safe-area-inset-top))] shell:items-end">
      {toasts.map((t) => (
        <div key={t.id} role={t.tone === "error" ? "alert" : "status"}
             className={`pointer-events-auto flex w-full max-w-md items-center gap-3 rounded-control py-1 pl-4 pr-1 shadow-lg ${t.tone === "error" ? "bg-error text-accent-ink" : "bg-ink text-surface"}`}>
          <p className="min-w-0 flex-1 py-2 [overflow-wrap:anywhere]">{t.message}</p>
          <button onClick={() => dismiss(t.id)} aria-label="Close this notice" className="flex size-11 shrink-0 items-center justify-center rounded-control hover:bg-white/15 active:bg-white/25">
            <svg width="16" height="16" viewBox="0 0 20 20" aria-hidden="true"><path d="M5 5l10 10M15 5L5 15" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" /></svg>
          </button>
        </div>
      ))}
    </div>
  );
}
