"use client";

import { useState, type FormEvent } from "react";
import { RequirePermission } from "@/components/shell";
import { Button, Card, ErrorBox, Field, Input, PageTitle } from "@/components/ui";
import { api, useApi } from "@/lib/api";

type Branch = {
  id: string; code: string; name: string; address: string; phone: string; email: string;
  tax_rate: string; timezone: string; currency: string; version: number;
};

export default function BranchSettingsPage() {
  return (
    <RequirePermission permission="settings">
      <BranchSettings />
    </RequirePermission>
  );
}

function BranchSettings() {
  const { data, error, reload } = useApi<Branch>("/api/branch");
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!data) return;
    setSaveError(null);
    setSaved(false);
    try {
      await api("/api/branch", {
        method: "PUT",
        json: { ...Object.fromEntries(new FormData(e.currentTarget)), version: data.version },
      });
      setSaved(true);
      reload();
    } catch (err) {
      setSaveError((err as Error).message);
    }
  }

  if (error) return <ErrorBox message={error} />;
  if (!data) return <p className="text-neutral-500">Loading…</p>;

  return (
    <>
      <PageTitle title="Branch settings" subtitle={`Branch code ${data.code}: it appears in every document number`} />
      <Card>
        {/* key: remount the form with fresh values after each save */}
        <form key={data.version} onSubmit={submit} className="grid gap-4 md:grid-cols-2">
          <Field label="Workshop name"><Input name="name" defaultValue={data.name} required maxLength={120} /></Field>
          <Field label="Phone" hint="Printed on documents and WhatsApp messages">
            <Input name="phone" defaultValue={data.phone} inputMode="tel" />
          </Field>
          <Field label="Address"><Input name="address" defaultValue={data.address} maxLength={300} /></Field>
          <Field label="Email"><Input name="email" type="email" defaultValue={data.email} /></Field>
          <Field label="Tax rate (%)" hint="Applied when “Include tax” is ticked on a quotation or invoice">
            <Input name="tax_rate" type="number" min={0} max={100} step="0.01" defaultValue={data.tax_rate} required />
          </Field>
          <Field label="Currency"><Input name="currency" defaultValue={data.currency} pattern="[A-Z]{3}" required /></Field>
          <Field label="Timezone"><Input name="timezone" defaultValue={data.timezone} required /></Field>
          <div className="flex items-end gap-3 md:col-span-2">
            <Button type="submit">Save settings</Button>
            {saved && <span className="text-sm text-green-700">Saved.</span>}
          </div>
          <div className="md:col-span-2"><ErrorBox message={saveError} /></div>
        </form>
      </Card>
    </>
  );
}
