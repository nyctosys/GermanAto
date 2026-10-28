"use client";

import { useState } from "react";
import { RequirePermission } from "@/components/shell";
import { Button, Card, Checkbox, ErrorState, Field, Input, Notice, PageHeader, SkeletonRows } from "@/components/ui";
import { api, useApi } from "@/lib/api";
import { type FieldErrors, parseForm, reminderSchema, templateSchema } from "@/lib/schemas";

type Template = { key: string; label: string; body: string; enabled: boolean; version: number };
type Data = { templates: Template[]; fields: string[]; reminder_days: string; service_reminder_days: number };

export default function MessageSettingsPage() {
  const list = useApi<Data>("/api/message-templates");
  return (
    <RequirePermission permission="messages">
      <PageHeader title="Message wording" description="What customers are told, and when they are reminded." />
      {list.error ? <ErrorState message={list.error} onRetry={list.reload} /> : !list.data ? <SkeletonRows rows={4} /> : (
        <div className="grid gap-4 shell:grid-cols-[2fr_1fr] shell:items-start">
          <Card title="Messages to customers" flush>
            <p className="border-b border-rule px-4 py-3 text-sm text-muted shell:px-5">
              Fill-in fields: {list.data.fields.map((f) => `{${f}}`).join(" ")}. They are replaced with the real details when the message is sent.
            </p>
            <ul>{list.data.templates.map((t) => <li key={`${t.key}:${t.version}`} className="border-t border-rule px-4 py-4 first:border-t-0 shell:px-5"><TemplateForm t={t} onDone={list.reload} /></li>)}</ul>
          </Card>
          <ReminderForm d={list.data} onDone={list.reload} />
        </div>
      )}
    </RequirePermission>
  );
}

function TemplateForm({ t, onDone }: { t: Template; onDone: () => void }) {
  const [errors, setErrors] = useState<FieldErrors>({});
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const { data, errors } = parseForm(templateSchema, e.currentTarget);
    setErrors(errors ?? {});
    if (!data) return;
    setError(null);
    try { await api(`/api/message-templates/${t.key}`, { method: "PUT", json: { ...data, version: t.version } }); setSaved(true); onDone(); }
    catch (err) { setError((err as Error).message); }
  }
  return (
    <form noValidate onSubmit={submit} className="grid gap-3">
      <Field label={t.label} error={errors.body}>
        <textarea name="body" defaultValue={t.body} rows={3} maxLength={600} className="min-h-24 w-full rounded-control border border-rule-strong bg-surface px-3 py-2 text-base hover:border-ink-2 focus-visible:border-ink" />
      </Field>
      <Checkbox name="enabled" label="Send this message" defaultChecked={t.enabled} />
      <Notice>{error}</Notice>
      <div className="flex flex-wrap items-center gap-3"><Button type="submit" className="self-start">Save</Button>{saved && <span className="text-sm text-muted">Saved</span>}</div>
    </form>
  );
}

function ReminderForm({ d, onDone }: { d: Data; onDone: () => void }) {
  const [errors, setErrors] = useState<FieldErrors>({});
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const { data, errors } = parseForm(reminderSchema, e.currentTarget);
    setErrors(errors ?? {});
    if (!data) return;
    setError(null);
    try { await api("/api/message-settings", { method: "PUT", json: data }); setSaved(true); onDone(); }
    catch (err) { setError((err as Error).message); }
  }
  return (
    <Card title="Reminders">
      <form noValidate onSubmit={submit} className="grid gap-4">
        <Field label="Chase an unpaid invoice after (days)" hint="Only the latest step is sent each time." error={errors.reminder_days}>
          <Input name="reminder_days" defaultValue={d.reminder_days} inputMode="numeric" />
        </Field>
        <Field label="Suggest the next service after (days)" error={errors.service_reminder_days}>
          <Input name="service_reminder_days" type="number" inputMode="numeric" defaultValue={d.service_reminder_days} />
        </Field>
        <Notice>{error}</Notice>
        <div className="flex flex-wrap items-center gap-3"><Button type="submit" className="self-start">Save</Button>{saved && <span className="text-sm text-muted">Saved</span>}</div>
        <p className="text-sm text-muted">Reminders are queued when someone presses Queue due reminders on the Messages page, or when a daily job calls it. Each reminder is queued once.</p>
      </form>
    </Card>
  );
}
