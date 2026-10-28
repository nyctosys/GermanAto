"use client";

import { useState } from "react";
import Link from "next/link";
import { RequirePermission } from "@/components/shell";
import { Badge, Button, Card, EmptyState, ErrorState, Notice, PageHeader, Select, SkeletonRows } from "@/components/ui";
import { api, useApi } from "@/lib/api";
import { phone, when } from "@/lib/format";

type Message = { id: string; customer: string; customer_id: string | null; to: string; template: string; body: string; status: Status; error: string; attempts: number; created_at: string; sent_at: string | null };
type Status = "queued" | "sent" | "delivered" | "read" | "failed" | "skipped";
type Data = { connected: boolean; counts: Partial<Record<Status, number>>; messages: Message[] };

const STATUS: Record<Status, { label: string; tone: "neutral" | "success" | "warning" | "error" | "accent" }> = {
  queued: { label: "Waiting to send", tone: "warning" }, sent: { label: "Sent", tone: "accent" }, delivered: { label: "Delivered", tone: "success" },
  read: { label: "Read", tone: "success" }, failed: { label: "Failed", tone: "error" }, skipped: { label: "Not sent", tone: "neutral" },
};
const KIND: Record<string, string> = {
  quotation_sent: "Quotation", car_ready: "Car ready", invoice_issued: "Invoice", payment_received: "Payment received",
  payment_reminder: "Payment reminder", service_reminder: "Service reminder", welcome: "Welcome",
};

export default function MessagesPage() {
  const [status, setStatus] = useState("all");
  const list = useApi<Data>(`/api/messages?status=${status}`);
  const [note, setNote] = useState<{ tone: "success" | "error"; text: string } | null>(null);
  const [busy, setBusy] = useState(false);

  async function run(path: string, label: string) {
    setBusy(true);
    setNote(null);
    try {
      const r = await api<Record<string, unknown>>(path, { method: "POST" });
      const q = r.queued as Record<string, number> | undefined;
      setNote({ tone: "success", text: q ? `${label}: ${q.payment} payment, ${q.service} service, ${q.welcome} welcome. ${r.sent} sent, ${r.waiting} waiting.` : `${label}: ${r.sent} sent, ${r.failed} failed, ${r.waiting} waiting.` });
      list.reload();
    } catch (e) {
      setNote({ tone: "error", text: (e as Error).message });
    } finally {
      setBusy(false);
    }
  }

  const d = list.data;
  return (
    <RequirePermission permission="messages">
      <PageHeader title="Messages" description="WhatsApp messages to customers: what was queued, what was sent, and what needs another try."
        actions={<><Link href="/settings/messages" className="inline-flex min-h-11 items-center px-1 font-medium underline underline-offset-4">Change the wording</Link>
          <Button variant="secondary" disabled={busy} onClick={() => run("/api/messages/run-reminders", "Reminders")}>Queue due reminders</Button></>} />
      {d && !d.connected && (
        <div className="mb-4"><Notice tone="warning">WhatsApp is not connected, so messages wait here and nothing is sent. Add the Twilio account details to the server settings to start sending.</Notice></div>
      )}
      {note && <div className="mb-4"><Notice tone={note.tone}>{note.text}</Notice></div>}
      <Card title="Messages" flush actions={
        <div className="flex flex-wrap items-center gap-2">
          <Select aria-label="Show" value={status} onChange={(e) => setStatus(e.target.value)} className="w-auto">
            <option value="all">All messages</option>
            {(Object.keys(STATUS) as Status[]).map((s) => <option key={s} value={s}>{STATUS[s].label}{d?.counts[s] ? ` (${d.counts[s]})` : ""}</option>)}
          </Select>
          {d?.connected && <Button variant="secondary" disabled={busy} onClick={() => run("/api/messages/send", "Send")}>Send waiting messages</Button>}
        </div>}>
        {list.error ? <ErrorState message={list.error} onRetry={list.reload} /> : !d ? <SkeletonRows rows={4} /> : !d.messages.length ? (
          <EmptyState title="No messages yet">Messages appear here when a quotation is sent, a car is ready, an invoice is issued or a payment is received.</EmptyState>
        ) : (
          <ul>
            {d.messages.map((m) => (
              <li key={m.id} className="border-t border-rule px-4 py-4 first:border-t-0 shell:px-5">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="font-medium">{m.customer || "Walk-in"} <span className="font-normal text-muted">{m.to ? phone(m.to) : "no phone"}</span></p>
                  <p className="flex items-center gap-2"><Badge>{KIND[m.template] ?? m.template}</Badge><Badge tone={STATUS[m.status].tone}>{STATUS[m.status].label}</Badge></p>
                </div>
                <p className="mt-1 break-words text-[0.9375rem]">{m.body}</p>
                <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-sm text-muted">
                  <span>{when(m.sent_at ?? m.created_at)}{m.error && <span className="text-error"> · {m.error}</span>}</span>
                  {m.status === "failed" && <Button variant="secondary" disabled={busy} onClick={() => run(`/api/messages/${m.id}/retry`, "Retry")}>Try again</Button>}
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </RequirePermission>
  );
}
