"use client";

import { useState, type FormEvent } from "react";
import { DeleteButton } from "@/components/delete-button";
import { ListSelect } from "@/components/list-select";
import { Button, Checkbox, Field, Input, Notice } from "@/components/ui";
import { api } from "@/lib/api";

export type LabourCode = { id: string; code: string; name: string; category: string; description: string; is_active: boolean; version: number };

/** Add or edit a labour code, on the Labour codes screen or from the job card's search. */
export function LabourCodeForm({ code, presetName, onSaved, onCancel }:
  { code: LabourCode | null; presetName?: string; onSaved: (c: LabourCode) => void; onCancel: () => void }) {
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    e.stopPropagation(); // from the picker's dialog, React would bubble this into a surrounding form
    const f = new FormData(e.currentTarget);
    if (!f.get("category")) { setError("Choose a category."); return; }
    const body = { code: code?.code ?? "", name: f.get("name"), category: f.get("category"),
                   description: f.get("description"), is_active: code ? f.get("is_active") === "on" : true };
    setBusy(true);
    setError(null);
    try {
      onSaved(await api<LabourCode>(code ? `/api/labour-codes/${code.id}` : "/api/labour-codes", { method: code ? "PUT" : "POST", json: body }));
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="grid gap-5 sm:grid-cols-2">
      {code && <Field label="Code" hint="Made by the system. It can't be changed."><Input value={code.code} disabled readOnly /></Field>}
      <Field required label="Category"><ListSelect name="category" kind="labour_category" defaultValue={code?.category} placeholder="Choose a category" /></Field>
      <div className="sm:col-span-2"><Field required label="Name"><Input name="name" defaultValue={code?.name ?? presetName} required placeholder="Paint one door" /></Field></div>
      <div className="sm:col-span-2"><Field label="Description (optional)"><Input name="description" defaultValue={code?.description} /></Field></div>
      {code && <div className="sm:col-span-2"><Checkbox name="is_active" defaultChecked={code.is_active} label="In use" hint="Retired codes stay on old documents but can't be picked." /></div>}
      <div className="flex flex-col gap-3 sm:col-span-2">
        <Notice>{error}</Notice>
        <div className="flex flex-wrap gap-2">
          <Button type="submit" variant={code ? "success" : "primary"} disabled={busy}>{busy ? "Saving" : code ? "Save changes" : "Add labour code"}</Button>
          <Button type="button" variant="danger" onClick={onCancel}>Cancel</Button>
          {code && <DeleteButton path={`/api/labour-codes/${code.id}`} what="labour code" onDone={onCancel} label="Delete code" />}
        </div>
      </div>
    </form>
  );
}
