"use client";

import Link from "next/link";
import { useState } from "react";
import { Button } from "@/components/ui";

const KEY = "how-it-works-hidden";
const STEPS = ["Check the car in", "Write the job card", "Send the quotation", "Customer approves", "Do the repair", "Make the invoice", "Take the payment", "Car leaves"];

/** A short picture of the whole job for someone new. Can be hidden; the choice is remembered on this device. */
export function HowItWorks() {
  const [hidden, setHidden] = useState(() => { try { return localStorage.getItem(KEY) === "1"; } catch { return false; } });
  if (hidden) return null;
  return (
    <section className="mb-6 rounded-card bg-surface px-4 py-4 shell:px-5" aria-label="How a car moves through the workshop">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">New here? This is how a job goes</h2>
          <p className="text-muted">Every car follows the same steps. The system always shows the next step on the car&apos;s page.</p>
        </div>
        <div className="flex gap-2">
          <Link href="/help" className="inline-flex min-h-11 items-center rounded-control border border-rule-strong bg-surface px-4 font-medium hover:bg-paper">Read the guide</Link>
          <Button variant="secondary" onClick={() => { try { localStorage.setItem(KEY, "1"); } catch {} setHidden(true); }}>Hide this</Button>
        </div>
      </div>
      <ol className="mt-3 flex flex-wrap gap-2">
        {STEPS.map((s, i) => (
          <li key={s} className="flex items-center gap-2 rounded-control bg-paper-3 px-3 py-1.5 text-sm"><span className="num font-semibold text-primary">{i + 1}</span>{s}</li>
        ))}
      </ol>
    </section>
  );
}
