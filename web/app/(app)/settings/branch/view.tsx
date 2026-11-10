"use client";

import { PhoneInput } from "@/components/phone-input";
import { useState, type FormEvent } from "react";
import { RequirePermission } from "@/components/shell";
import { Button, Card, ErrorState, Field, Input, Notice, PageHeader, SkeletonRows } from "@/components/ui";
import { api, useApi } from "@/lib/api";

type Branch = {
  id: string; code: string; name: string; address: string; phone: string; email: string;
  tax_rate: string; ntn: string; ntn_options: string; timezone: string; currency: string; quotation_terms: string; terms: string[]; version: number;
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
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!data) return;
    setSaveError(null);
    setSaved(false);
    setBusy(true);
    try {
      const fd = new FormData(e.currentTarget);
      const ntn_options = [1, 2, 3].map((i) => String(fd.get(`ntn_${i}`) ?? "").trim()).filter(Boolean).join("\n");
      const body = Object.fromEntries(fd);
      delete body.ntn_1; delete body.ntn_2; delete body.ntn_3;
      await api("/api/branch", {
        method: "PUT",
        json: { ...body, ntn_options, ntn: data.ntn || ntn_options.split("\n")[0] || "", version: data.version },
      });
      setSaved(true);
      reload();
    } catch (err) {
      setSaveError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Branch settings"
        description="Printed on quotations, invoices and receipts, and used in WhatsApp messages."
      />
      <Card flush>
        {error ? <ErrorState message={error} onRetry={reload} />
          : !data ? <SkeletonRows rows={6} />
          : (
            /* key: remount with fresh values after each save */
            <form key={data.version} onSubmit={submit} className="grid gap-5 p-4 sm:grid-cols-2 shell:p-6">
              <Field label="Workshop name"><Input name="name" defaultValue={data.name} required maxLength={120} /></Field>
              <Field label="Branch code" hint="Fixed. It appears in every document number.">
                <Input value={data.code} readOnly disabled />
              </Field>
              <Field label="Phone"><PhoneInput name="phone" defaultValue={data.phone} /></Field>
              <Field label="Email"><Input name="email" type="email" defaultValue={data.email} autoComplete="email" /></Field>
              <div className="sm:col-span-2">
                <Field label="Address"><Input name="address" defaultValue={data.address} maxLength={300} autoComplete="street-address" /></Field>
              </div>
              <Field label="Tax rate (%)" hint="Used when “Include tax” is ticked on a quotation or invoice.">
                <Input name="tax_rate" type="number" inputMode="decimal" min={0} max={100} step="0.01" defaultValue={data.tax_rate} required />
              </Field>
              <div className="sm:col-span-2 grid gap-4 sm:grid-cols-3">
                {([1, 2, 3] as const).map((i) => {
                  const opts = (data.ntn_options || "").split("\n").filter(Boolean);
                  return (
                    <Field key={i} label={`Workshop NTN ${i}`} hint={i === 1 ? "Up to three. Printed under the letterhead. When issuing, pick one — last used is remembered." : undefined}>
                      <Input name={`ntn_${i}`} defaultValue={opts[i - 1] ?? ""} inputMode="numeric" maxLength={15} placeholder="1234567-8" />
                    </Field>
                  );
                })}
              </div>
              {data.ntn && <p className="sm:col-span-2 text-sm text-muted">Last used when issuing: <span className="num font-medium text-ink">{data.ntn}</span></p>}
              <Field label="Currency"><Input name="currency" defaultValue={data.currency} pattern="[A-Z]{3}" required /></Field>
              <Field label="Timezone"><Input name="timezone" defaultValue={data.timezone} required /></Field>
              <div className="sm:col-span-2">
                <Field label="Terms and conditions on quotations" hint="One clause per line. They print on their own page after the quotation. Clear the box and save to go back to the standard terms.">
                  <textarea name="quotation_terms" defaultValue={data.quotation_terms || data.terms.join("\n")} rows={12} maxLength={8000}
                            className="min-h-40 w-full rounded-control border border-rule-strong bg-surface px-3 py-2 text-base hover:border-ink-2 focus-visible:border-ink" />
                </Field>
              </div>
              <div className="flex flex-col gap-3 sm:col-span-2">
                <Notice>{saveError}</Notice>
                {saved && <Notice tone="success">Settings saved.</Notice>}
                <div><Button type="submit" variant="success" disabled={busy}>{busy ? "Saving" : "Save settings"}</Button></div>
              </div>
            </form>
          )}
      </Card>
    </>
  );
}
