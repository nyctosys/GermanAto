"use client";

import { type Dispatch, type FocusEvent, type FormEvent, type SetStateAction, useCallback, useMemo, useState } from "react";
import type { z } from "zod";
import { ApiError } from "@/lib/api";
import { type FieldErrors, fieldErrorAt, issuesToFieldErrors } from "@/lib/schemas";

type Schema = z.ZodType;
type SchemaOrFn = Schema | (() => Schema);

/**
 * Spread onto a <form>: leaving a field shows its error beside it at once, and fixing
 * it clears the message as they type. Pass a function when the schema depends on other state
 * (e.g. last odometer reading).
 */
export function liveForm(
  schema: SchemaOrFn,
  errors: FieldErrors,
  setErrors: Dispatch<SetStateAction<FieldErrors>>,
) {
  const get = typeof schema === "function" ? schema : () => schema;
  const sync = (form: HTMLFormElement, name: string) => {
    if (!name) return;
    const msg = fieldErrorAt(get(), form, name);
    setErrors((prev) => {
      if (msg) return prev[name] === msg ? prev : { ...prev, [name]: msg };
      if (!(name in prev)) return prev;
      const next = { ...prev };
      delete next[name];
      return next;
    });
  };
  const control = (target: EventTarget | null) => {
    if (!(target instanceof HTMLInputElement || target instanceof HTMLSelectElement || target instanceof HTMLTextAreaElement)) return null;
    return target;
  };
  return {
    onBlur: (e: FocusEvent<HTMLFormElement>) => {
      const t = control(e.target);
      if (t?.name) sync(e.currentTarget, t.name);
    },
    // Re-check as they type so a bad odometer (etc.) lights up on that field at once.
    onInput: (e: FormEvent<HTMLFormElement>) => {
      const t = control(e.target);
      if (t?.name) sync(e.currentTarget, t.name);
    },
    onChange: (e: FormEvent<HTMLFormElement>) => {
      const t = control(e.target);
      if (!t?.name) return;
      const kind = t instanceof HTMLInputElement ? t.type : "";
      if (t.tagName === "SELECT" || kind === "checkbox" || kind === "radio" || kind === "date") {
        sync(e.currentTarget, t.name);
      }
    },
  };
}

/** Put an API failure on the right field when we can; otherwise return a banner message. */
export function fieldErrorsFromApi(err: unknown): { fields: FieldErrors; banner: string | null } {
  if (!(err instanceof ApiError)) {
    return { fields: {}, banner: err instanceof Error ? err.message : "Something went wrong" };
  }
  const detail = err.detail;
  if (Array.isArray(detail)) {
    const fields = issuesToFieldErrors(
      (detail as { loc?: (string | number)[]; msg?: string }[])
        .filter((d) => d.msg)
        .map((d) => ({
          path: (d.loc ?? []).filter((p) => p !== "body" && p !== "query"),
          message: d.msg!,
        })),
    );
    if (Object.keys(fields).length) return { fields, banner: null };
  }
  const msg = err.message;
  // Specific first: money amounts, proof, references, then identity fields.
  const rules: [RegExp, string][] = [
    [/advance cannot|still be taken|still be given back|still owed|more than the (quotation|balance|invoice)|more than the balance|month'?s pay|advances outstanding|owed back|refundable|at most .*(owed|advance)/i, "amount"],
    [/transaction reference|reference or a screenshot|screenshot for a bank/i, "reference"],
    [/no proof|say why|write why|proof_id|no_proof_reason/i, "reason"],
    [/categor(y|ies)|retired\. Pick another/i, "category_id"],
    [/date is in the future/i, "occurred_on"],
    [/discount is more/i, "discount"],
    [/odometer.*less than last|last time|last reading/i, "odometer_in"],
    [/exit reading|less than at check-in|odometer.*check-in/i, "odometer_out"],
    [/credit|unpaid|reason for releas/i, "credit_reason"],
    [/handed|who is taking/i, "handed_to"],
    [/\bphone\b/i, "phone"],
    [/\bcnic\b/i, "cnic"],
    [/\bvin\b|chassis/i, "vin"],
    [/password/i, "password"],
    [/username/i, "username"],
    [/\bemail\b/i, "email"],
    [/\bplate\b/i, "plate"],
    [/odometer/i, "odometer_km"],
  ];
  for (const [re, field] of rules) {
    if (re.test(msg)) return { fields: { [field]: msg }, banner: null };
  }
  return { fields: {}, banner: msg };
}

/** Field errors + live handlers + API mapping for native <form> screens. */
export function useFormErrors(schema: SchemaOrFn) {
  const [errors, setErrors] = useState<FieldErrors>({});
  const live = useMemo(() => liveForm(schema, errors, setErrors), [schema, errors]);
  const applyApi = useCallback((err: unknown) => {
    const { fields, banner } = fieldErrorsFromApi(err);
    if (Object.keys(fields).length) setErrors((prev) => ({ ...prev, ...fields }));
    return banner;
  }, []);
  return { errors, setErrors, live, applyApi };
}

/**
 * Controlled forms (payments, money book): after submit or an API refusal, wrong
 * values show beside their controls and update as they keep typing.
 * Do not wake on input/change/blur — waking during the first keystroke races the
 * amount field's update, validates the previous empty value, and the re-render
 * eats that digit (Take an advance, pay, money in/out).
 * Once `active`, any value change already re-runs validate via render.
 */
export function useLiveErrors<T>(value: T, validate: (v: T) => FieldErrors) {
  const [active, setActive] = useState(false);
  const [server, setServer] = useState<FieldErrors>({});
  const local = active ? validate(value) : {};
  const errors = { ...server, ...local };
  const clearServer = useCallback(() => setServer({}), []);
  const wake = useCallback(() => setActive(true), []);
  const applyApi = useCallback((err: unknown) => {
    const { fields, banner } = fieldErrorsFromApi(err);
    if (Object.keys(fields).length) {
      setActive(true);
      setServer(fields);
    }
    return banner;
  }, []);
  return {
    errors,
    active,
    activate: wake,
    clearServer,
    applyApi,
    // No form-level listeners: activate() on submit / applyApi on refusal only.
    live: {},
  };
}
