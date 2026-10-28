"use client";

import { useState, type FormEvent } from "react";
import { api } from "@/lib/api";
import { Button, ErrorBox, Field, Input } from "@/components/ui";

export default function LoginPage() {
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    setBusy(true);
    setError(null);
    try {
      await api("/api/auth/login", { method: "POST", json: Object.fromEntries(form) });
      const next = new URLSearchParams(window.location.search).get("next");
      // Only same-site paths, so a crafted link can't bounce users elsewhere.
      // Full load so the app starts with the new session from scratch.
      window.location.assign(next?.startsWith("/") && !next.startsWith("//") ? next : "/");
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center p-4">
      <form onSubmit={submit} className="w-full max-w-sm space-y-4 rounded-lg border border-neutral-200 bg-white p-6 shadow-sm">
        <div>
          <h1 className="text-xl font-semibold text-brand">GermanATO</h1>
          <p className="text-sm text-neutral-500">Sign in to continue</p>
        </div>
        <Field label="Username">
          <Input name="username" autoComplete="username" autoFocus required />
        </Field>
        <Field label="Password">
          <Input name="password" type="password" autoComplete="current-password" required />
        </Field>
        <ErrorBox message={error} />
        <Button type="submit" disabled={busy} className="w-full">
          {busy ? "Signing in…" : "Sign in"}
        </Button>
      </form>
    </main>
  );
}
