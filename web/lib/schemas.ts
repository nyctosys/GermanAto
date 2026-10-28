import { z } from "zod";

// Mirrors api/app/validators.py so mistakes show beside the field before a
// round trip. The API still validates everything; these are for the person typing.

const text = (max = 3000) => z.string().trim().max(max, `At most ${max} characters`);
const name = text(120).min(1, "Required");
const checkbox = z.literal("on").optional().transform(Boolean);

/** Pakistani numbers to +92XXXXXXXXXX; empty stays empty. */
const phoneOrEmpty = z.string().transform((v, ctx) => {
  let d = v.trim().replace(/[^\d+]/g, "");
  if (!d) return "";
  if (d.startsWith("+92")) d = d.slice(3);
  else if (d.startsWith("0092")) d = d.slice(4);
  else if (d.startsWith("92") && d.length === 12) d = d.slice(2);
  else if (d.startsWith("0")) d = d.slice(1);
  if (!/^\d{9,10}$/.test(d)) {
    ctx.addIssue({ code: "custom", message: "Enter a Pakistani phone number, e.g. 0300 1234567" });
    return z.NEVER;
  }
  return "+92" + d;
});
const phone = phoneOrEmpty.refine(Boolean, "Required");

const email = z.string().trim().toLowerCase().refine((v) => !v || /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(v), "Enter a valid email");

const cnic = z.string().transform((v, ctx) => {
  const d = v.replace(/\D/g, "");
  if (!d) return "";
  if (d.length !== 13) {
    ctx.addIssue({ code: "custom", message: "A CNIC has 13 digits, e.g. 35202-1234567-1" });
    return z.NEVER;
  }
  return `${d.slice(0, 5)}-${d.slice(5, 12)}-${d[12]}`;
});

/** A 17-character VIN or a local chassis number (NZE141-6012345): the same field. */
const vin = z.string().transform((v) => v.toUpperCase().replace(/\s/g, ""))
  .refine((v) => !v || /^[A-Z0-9-]{5,30}$/.test(v), "Use the VIN or chassis number: 5 to 30 letters, digits or dashes")
  .refine((v) => !(v.length === 17 && !v.includes("-") && /[IOQ]/.test(v)), "A 17-character VIN never contains I, O or Q");

/** "" becomes null; anything else must be a whole number in range. */
const optionalInt = (min: number, max: number, label: string) => z.string().trim().transform((v, ctx) => {
  if (!v) return null;
  const n = Number(v);
  if (!Number.isInteger(n) || n < min || n > max) {
    ctx.addIssue({ code: "custom", message: `${label} must be a whole number from ${min.toLocaleString("en-PK")} to ${max.toLocaleString("en-PK")}` });
    return z.NEVER;
  }
  return n;
});

export const customerSchema = z.object({
  kind: z.enum(["individual", "company"]),
  name,
  phone,
  phone_alt: phoneOrEmpty,
  email,
  cnic,
  address: text(300),
  notes: text(),
  whatsapp_opt_out: checkbox,
  is_active: checkbox,
});

export const carSchema = z.object({
  plate: text(20),
  make: text(60).min(1, "Required"),
  model: text(60),
  year: optionalInt(1950, new Date().getFullYear() + 1, "Year"),
  fuel: z.enum(["petrol", "diesel", "hybrid", "ev", "cng", "other"]),
  color: text(40),
  vin,
  engine_no: text(40).toUpperCase(),
  odometer_km: optionalInt(0, 2_000_000, "Odometer"),
  notes: text(),
});

export const checkInSchema = z.object({
  complaint: text(),
  odometer_in: optionalInt(0, 2_000_000, "Odometer").refine((v) => v != null, "Required"),
  condition_notes: text(),
  items_left: text(1000),
});

export const userSchema = z.object({
  username: z.string().trim().toLowerCase().regex(/^[a-z0-9._-]{3,32}$/, "3 to 32 letters, digits, dots, dashes or underscores").optional(),
  full_name: name,
  phone: phoneOrEmpty,
  email,
  password: z.string().refine((v) => !v || (v.length >= 8 && v.length <= 128), "At least 8 characters"),
});

export type FieldErrors = Partial<Record<string, string>>;

/**
 * Validate a form's values. Returns the cleaned data, or one message per field.
 * Fields the schema doesn't know (and missing checkboxes) are handled by the schema.
 */
export function parseForm<S extends z.ZodType>(schema: S, form: HTMLFormElement | FormData):
  { data: z.output<S>; errors: null } | { data: null; errors: FieldErrors } {
  const values = Object.fromEntries(form instanceof FormData ? form : new FormData(form));
  const r = schema.safeParse(values);
  if (r.success) return { data: r.data, errors: null };
  const errors: FieldErrors = {};
  for (const issue of r.error.issues) errors[String(issue.path[0])] ??= issue.message;
  // Take the person straight to the first thing to fix.
  if (!(form instanceof FormData)) {
    form.querySelector<HTMLElement>(Object.keys(errors).map((k) => `[name="${k}"]`).join(","))?.focus();
  }
  return { data: null, errors };
}

/** A line quantity on a job card or quotation. */
export const lineQty = z.string().trim().refine((v) => Number(v) > 0 && Number(v) <= 10000, "More than 0");

/** A price typed on a quotation line: whole rupees or paisa, more than zero to send. */
export const linePrice = z.string().trim().refine((v) => /^\d{1,9}(\.\d{1,2})?$/.test(v) && Number(v) > 0, "Enter the price");

export const advanceSchema = z.object({
  amount: z.string().trim().refine((v) => /^\d{1,9}(\.\d{1,2})?$/.test(v) && Number(v) > 0, "Enter the amount received"),
  account: z.enum(["cash", "bank", "wallet"]),
  reference: text(60),
  note: text(500),
});
