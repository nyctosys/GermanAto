"use client";

import Image from "next/image";
import { useState, type FormEvent } from "react";
import { api } from "@/lib/api";
import { Button, Field, Input, Notice } from "@/components/ui";

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
    <main className="grid min-h-dvh shell:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
      <section className="hidden flex-col items-center justify-center gap-6 border-r border-rule bg-paper-2 p-12 shell:flex">
        <Image src="/logo.png" alt="GermanATO" width={280} height={280} priority />
        <p className="text-section text-ink-2">Gets your car road ready.</p>
      </section>

      <section className="flex items-center justify-center px-4 py-10">
        <form onSubmit={submit} className="w-full max-w-sm space-y-5" aria-describedby={error ? "login-error" : undefined}>
          <div className="flex flex-col items-start gap-4">
            <Image src="/logo.png" alt="GermanATO" width={72} height={72} priority className="shell:hidden" />
            <div>
              <h1>Sign in</h1>
              <p className="mt-1 text-muted">Use the account your administrator gave you.</p>
            </div>
          </div>
          <Field label="Username">
            <Input name="username" autoComplete="username" autoCapitalize="none" spellCheck={false} autoFocus required />
          </Field>
          <Field label="Password">
            <Input name="password" type="password" autoComplete="current-password" required />
          </Field>
          <div id="login-error"><Notice>{error}</Notice></div>
          <Button type="submit" disabled={busy} className="w-full">
            {busy ? "Signing in" : "Sign in"}
          </Button>
        </form>
      </section>
    </main>
  );
}
