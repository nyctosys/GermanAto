"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui";
import { api } from "@/lib/api";

/** Deletes a record made by mistake. The server refuses when anything else uses it and says to mark it inactive instead. */
export function DeleteButton({ path, what, goTo, onDone, label = "Delete" }:
  { path: string; what: string; goTo?: string; onDone?: () => void; label?: string }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  return (
    <Button type="button" variant="danger" disabled={busy} onClick={async () => {
      if (!confirm(`Delete this ${what}? This can't be undone.`)) return;
      setBusy(true);
      try {
        await api(path, { method: "DELETE", toast: `${what[0].toUpperCase()}${what.slice(1)} deleted` });
        onDone?.();
        if (goTo) router.push(goTo);
      } catch (e) { alert((e as Error).message); }
      setBusy(false);
    }}>{label}</Button>
  );
}
