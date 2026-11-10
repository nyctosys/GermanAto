"use client";

import { Field, Select } from "@/components/ui";

/** Pick which workshop NTN to print. Defaults to the last-used value from Branch settings. */
export function WorkshopNtnPick({ options, value, onChange }: { options: string[]; value: string; onChange: (v: string) => void }) {
  if (!options.length) return null;
  return (
    <Field label="Workshop NTN" hint="Printed under the letterhead. Leave as last used, or pick another.">
      <Select value={value || options[0]} onChange={(e) => onChange(e.target.value)}>
        {options.map((n) => <option key={n} value={n}>{n}</option>)}
      </Select>
    </Field>
  );
}

export function ntnOptionsFrom(branch: { ntn_options?: string; ntn?: string } | null | undefined): string[] {
  const listed = (branch?.ntn_options ?? "").split("\n").map((s) => s.trim()).filter(Boolean);
  if (listed.length) return listed;
  return branch?.ntn ? [branch.ntn] : [];
}
