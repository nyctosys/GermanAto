import { z } from "zod";

// Mirrors api/app/validators.py so mistakes show beside the field before a
// round trip. The API still validates everything; these are for the person typing.

const text = (max = 3000) => z.string().trim().max(max, `At most ${max} characters`);
const name = text(120).min(1, "Required");
const checkbox = z.literal("on").optional().transform(Boolean);

/** International format: Pakistani numbers become +92XXXXXXXXXX, other country codes are kept; empty stays empty. */
const phoneOrEmpty = z.string().transform((v, ctx) => {
  if (/[^\d\s+\-()./]/.test(v)) {
    ctx.addIssue({ code: "custom", message: "A phone number has digits only, e.g. +92 300 1234567" });
    return z.NEVER;
  }
  let d = v.trim().replace(/[^\d+]/g, "");
  if (!d) return "";
  if (d.startsWith("00") && !d.startsWith("0092")) d = `+${d.slice(2)}`;
  if (d.startsWith("+") && !d.startsWith("+92")) {
    if (/^\+[1-9]\d{7,14}$/.test(d)) return d;
    ctx.addIssue({ code: "custom", message: "That number is too short or too long for its country code, e.g. +971 50 123 4567" });
    return z.NEVER;
  }
  if (d.startsWith("+92")) d = d.slice(3);
  else if (d.startsWith("0092")) d = d.slice(4);
  else if (d.startsWith("92") && d.length === 12) d = d.slice(2);
  else if (d.startsWith("0")) d = d.slice(1);
  if (!/^\d{9,10}$/.test(d)) {
    ctx.addIssue({ code: "custom", message: `A Pakistani number has 10 digits after +92 (you typed ${d.length}), e.g. +92 300 1234567` });
    return z.NEVER;
  }
  return "+92" + d;
});
const phone = phoneOrEmpty.refine(Boolean, "Required");

const email = z.string().trim().toLowerCase().refine((v) => !v || /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(v), "Enter a valid email");

const cnicOrEmpty = z.string().transform((v, ctx) => {
  const d = v.replace(/\D/g, "");
  if (!d) return "";
  if (d.length !== 13) {
    ctx.addIssue({ code: "custom", message: "A CNIC has 13 digits, e.g. 35202-1234567-1" });
    return z.NEVER;
  }
  return `${d.slice(0, 5)}-${d.slice(5, 12)}-${d[12]}`;
});

const cnic = cnicOrEmpty.refine(Boolean, "Required");

/** Empty, or 7 digits (optionally with check digit 1234567-8). */
export const ntnOrEmpty = z.string().transform((v, ctx) => {
  const d = v.replace(/\D/g, "");
  if (!d) return "";
  if (d.length === 7) return d;
  if (d.length === 8) return `${d.slice(0, 7)}-${d[7]}`;
  ctx.addIssue({ code: "custom", message: "A company NTN has 7 digits, e.g. 1234567-8" });
  return z.NEVER;
});

/** A 17-character VIN or a local chassis number (NZE141-6012345): the same field. */
const vin = z.string().transform((v) => v.toUpperCase().replace(/\s/g, ""))
  .refine((v) => !v || /^[A-Z0-9-]{5,30}$/.test(v), "Use the VIN or chassis number: 5 to 30 letters, digits or dashes")
  .refine((v) => !(v.length === 17 && !v.includes("-") && /[IOQ]/.test(v)), "A 17-character VIN never contains I, O or Q");

/** Matches the API's usual odometer ceiling (api/app/routers/workshop.py). */
export const ODOMETER_MAX = 3_000_000;

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
  cnic: cnicOrEmpty,
  ntn: ntnOrEmpty,
  address: text(300),
  notes: text(),
  whatsapp_opt_out: checkbox,
  is_active: checkbox,
}).transform((c) => (c.kind === "company" ? c : { ...c, ntn: "" }));

export const carSchema = z.object({
  plate: text(20),
  make: text(60).min(1, "Required"),
  model: text(60),
  year: optionalInt(1950, new Date().getFullYear() + 1, "Year"),
  fuel: z.enum(["petrol", "diesel", "hybrid", "ev", "cng", "other"]),
  color: text(40),
  vin,
  engine_no: text(40).toUpperCase(),
  odometer_km: optionalInt(0, ODOMETER_MAX, "Odometer"),
  notes: text(),
});

export const checkInSchema = z.object({
  complaint: text(),
  odometer_in: optionalInt(0, ODOMETER_MAX, "Odometer").refine((v) => v != null, "Required"),
  condition_notes: text(),
  items_left: text(1000),
});

/** Check-in with the car's last reading: leaving the field shows "lower than last" at once. */
export function checkInSchemaAt(lastKm: number | null) {
  return checkInSchema.superRefine((d, ctx) => {
    if (lastKm != null && d.odometer_in != null && d.odometer_in < lastKm) {
      ctx.addIssue({
        code: "custom",
        path: ["odometer_in"],
        message: `Lower than the last reading (${lastKm.toLocaleString("en-PK")} km)`,
      });
    }
  });
}

export const userSchema = z.object({
  username: z.string().trim().toLowerCase().regex(/^[a-z0-9._-]{3,32}$/, "3 to 32 letters, digits, dots, dashes or underscores").optional(),
  full_name: name,
  phone: phoneOrEmpty,
  email,
  password: z.string().refine((v) => !v || (v.length >= 8 && v.length <= 128), "At least 8 characters"),
});

export type FieldErrors = Partial<Record<string, string>>;

export function issuesToFieldErrors(issues: { path: PropertyKey[]; message: string }[]): FieldErrors {
  const errors: FieldErrors = {};
  for (const issue of issues) errors[String(issue.path[0])] ??= issue.message;
  return errors;
}

/**
 * Validate a form's values. Returns the cleaned data, or one message per field.
 * Fields the schema doesn't know (and missing checkboxes) are handled by the schema.
 */
export function parseForm<S extends z.ZodType>(schema: S, form: HTMLFormElement | FormData):
  { data: z.output<S>; errors: null } | { data: null; errors: FieldErrors } {
  const values = Object.fromEntries(form instanceof FormData ? form : new FormData(form));
  const r = schema.safeParse(values);
  if (r.success) return { data: r.data, errors: null };
  const errors = issuesToFieldErrors(r.error.issues);
  // Take the person straight to the first thing to fix.
  if (!(form instanceof FormData)) {
    form.querySelector<HTMLElement>(Object.keys(errors).map((k) => `[name="${k}"]`).join(","))?.focus();
  }
  return { data: null, errors };
}

/** The message for one named control, if that control is wrong right now. */
export function fieldErrorAt(schema: z.ZodType, form: HTMLFormElement, name: string): string | undefined {
  if (!name) return undefined;
  const r = schema.safeParse(Object.fromEntries(new FormData(form)));
  if (r.success) return undefined;
  return r.error.issues.find((i) => String(i.path[0]) === name)?.message;
}

/** A line quantity on a job card or quotation. */
// coerce: the API sends saved quantities and prices as numbers, which must count as valid just like typed text.
export const lineQty = z.coerce.string().trim().refine((v) => Number(v) > 0 && Number(v) <= 10000, "More than 0");

/** Same as lineQty, but pcs/set/pair/box must be whole numbers (matches api/app/stock.require_qty). */
export function lineQtyFor(unit?: string) {
  const whole = !unit || !["litre", "kg", "metre"].includes(unit);
  return z.coerce.string().trim().refine((v) => {
    const n = Number(v);
    if (!(n > 0 && n <= 10000)) return false;
    return !whole || Number.isInteger(n);
  }, whole ? "Enter a whole number" : "More than 0");
}

/** A price typed on a quotation line: whole rupees or paisa, more than zero to send. */
export const linePrice = z.coerce.string().trim().refine((v) => /^\d{1,9}(\.\d{1,2})?$/.test(v) && Number(v) > 0, "Enter the price");

/** One payment being recorded: proof or a reason; a transfer needs its reference or a screenshot (mirrors the API). */
export const paymentRowSchema = z.object({
  amount: z.string().trim().refine((v) => /^\d{1,9}(\.\d{1,2})?$/.test(v) && Number(v) > 0, "Enter the amount received"),
  account: z.enum(["cash", "bank", "wallet"]),
  reference: text(60),
  proof: z.array(z.object({ id: z.string() })),
  reason: z.string().trim(),
}).superRefine((r, ctx) => {
  if (!r.proof.length && r.reason.length < 5) ctx.addIssue({ code: "custom", path: ["reason"], message: "Attach proof, or explain why there is none" });
  if (r.account !== "cash" && !r.reference && !r.proof.length) ctx.addIssue({ code: "custom", path: ["reference"], message: "Add the transaction reference or a screenshot" });
});

export const gatePassSchema = z.object({
  odometer_out: optionalInt(0, ODOMETER_MAX, "Odometer"),
  handed_to: text(120),
  note: text(500),
  credit_reason: z.string().trim().max(500).optional().transform((v) => v ?? ""),
});

/** Gate pass: exit reading can't go backwards; unpaid release needs a reason. */
export function gatePassSchemaAt(opts: { minOut?: number | null; requireHandedTo?: boolean; creditBalance?: number } = {}) {
  return gatePassSchema.superRefine((d, ctx) => {
    if (opts.minOut != null && d.odometer_out != null && d.odometer_out < opts.minOut) {
      ctx.addIssue({
        code: "custom",
        path: ["odometer_out"],
        message: `Less than at check-in (${opts.minOut.toLocaleString("en-PK")} km)`,
      });
    }
    if (opts.requireHandedTo && !d.handed_to) {
      ctx.addIssue({ code: "custom", path: ["handed_to"], message: "Write who is taking the car" });
    }
    if ((opts.creditBalance ?? 0) > 0 && d.credit_reason.length < 5) {
      ctx.addIssue({ code: "custom", path: ["credit_reason"], message: "Give the reason" });
    }
  });
}

// --- purchasing ----------------------------------------------------------------------------------

/** A purchase cost, up to four decimals (per-unit costs of cheap parts). */
export const unitCost = z.string().trim().refine((v) => /^\d{1,9}(\.\d{1,4})?$/.test(v) && Number(v) > 0, "Enter the cost");
const signedMoney = z.string().trim().refine((v) => !v || (/^-?\d{1,9}(\.\d{1,2})?$/.test(v) && Number(v) !== 0 || v === "0"), "Enter an amount");

export const vendorSchema = z.object({
  name,
  contact_person: text(120).refine((v) => !/\d/.test(v), "A person's name has no numbers. Put a phone number in the Phone box."),
  phone: phoneOrEmpty,
  email,
  address: text(300),
  terms_days: optionalInt(0, 365, "Payment terms").transform((v) => v ?? 0),
  notes: text(),
});

export const billSchema = z.object({
  vendor_invoice_no: text(60),
  bill_date: z.string().min(1, "Required"),
  due_on: z.string(),
  adjustment: signedMoney,
  adjustment_reason: text(200),
}).superRefine((b, ctx) => {
  if (Number(b.adjustment || 0) !== 0 && b.adjustment_reason.length < 3) ctx.addIssue({ code: "custom", path: ["adjustment_reason"], message: "Say what it is for (freight, discount)" });
  if (b.due_on && b.due_on < b.bill_date) ctx.addIssue({ code: "custom", path: ["due_on"], message: "Before the bill date" });
});

// --- money ----------------------------------------------------------------------------------------

/** A money amount typed by a person: whole rupees or paisa, never negative. */
export const rupees = z.string().trim().refine((v) => v === "" || /^\d{1,10}(\.\d{1,2})?$/.test(v), "Enter an amount");

export const accountSchema = z.object({
  name,
  opening_balance: rupees.transform((v) => v || "0"),
  opening_date: z.string().min(1, "Required").refine((v) => v <= new Date().toLocaleDateString("en-CA"), "Can't be in the future"),
});

/** The wording of one customer message and the reminder days (mirrors api/app/routers/messages.py). */
// A ticked checkbox arrives as "on" and an unticked one is missing from the form data altogether.
export const templateSchema = z.object({ body: text(600).min(5, "Write at least a few words"), enabled: z.string().optional().transform((v) => v === "on") });
export const reminderSchema = z.object({
  reminder_days: z.string().trim().regex(/^\d{1,3}(,\s*\d{1,3}){0,5}$/, "Days separated by commas, like 3, 7, 15").transform((v) => v.replace(/\s/g, "")),
  service_reminder_days: z.coerce.number().int().min(30, "At least 30 days").max(730, "At most 730 days"),
});

export const categorySchema = z.object({ name: text(80).min(1, "Required") });

/** A money entry that isn't a customer or vendor payment (mirrors api/app/routers/moneybook.py). */
export const entrySchema = z.object({
  kind: z.enum(["other_income", "owner_capital", "transfer", "expense", "drawings"]),
  amount: z.string().trim().refine((v) => /^\d{1,10}(\.\d{1,2})?$/.test(v) && Number(v) > 0, "Enter the amount"),
  account: z.enum(["cash", "bank", "wallet"]),
  to_account: z.string(),
  category_id: z.string(),
  party: text(120),
  reference: text(60),
  note: text(500),
  occurred_on: z.string().min(1, "Required").refine((v) => v <= new Date().toLocaleDateString("en-CA"), "Can't be in the future"),
  proof: z.array(z.object({ id: z.string() })),
  reason: z.string().trim(),
}).superRefine((e, ctx) => {
  const bad = (path: string, message: string) => ctx.addIssue({ code: "custom", path: [path], message });
  if (e.kind === "transfer" && (!e.to_account || e.to_account === e.account)) bad("to_account", "Choose a different account");
  if (e.kind === "expense" && !e.category_id) bad("category_id", "Choose a category");
  if (!e.proof.length && e.reason.length < 5) bad("reason", "Attach proof, or explain why there is none");
  const touched = [e.account, e.kind === "transfer" ? e.to_account : "cash"].some((a) => a && a !== "cash");
  if (touched && !e.reference && !e.proof.length) bad("reference", "Add the transaction reference or a screenshot");
});

/** A count of one account. A difference from the books needs a reason (mirrors api/app/routers/cashclose.py). */
export const closeSchema = (expected: number) => z.object({
  counted: z.string().trim().refine((v) => /^\d{1,10}(\.\d{1,2})?$/.test(v), "Enter what is in the account"),
  reason: z.string().trim(),
  note: text(500),
}).superRefine((c, ctx) => {
  const diff = (Math.round(Number(c.counted) * 100) - Math.round(expected * 100)) / 100;
  if (/^\d/.test(c.counted) && diff !== 0 && c.reason.length < 5) ctx.addIssue({ code: "custom", path: ["reason"], message: "Say why the count differs" });
});

// --- people ----------------------------------------------------------------------------------------

export const employeeSchema = z.object({
  full_name: name,
  title: text(80),
  phone: phoneOrEmpty,
  cnic,
  device_pin: text(20),
  monthly_salary: rupees.transform((v) => v || "0"),
  shift_start: z.string().min(1, "Required"),
  shift_end: z.string().min(1, "Required"),
  days_off: z.string().transform((v) => (v ? v.split(",").map(Number) : [])),
  joined_on: z.string().min(1, "Required"),
  left_on: z.string().optional().transform((v) => v || null),
  user_id: z.string().optional().transform((v) => v || null),
  notes: text(),
  is_technician: checkbox,
}).superRefine((e, ctx) => {
  if (e.shift_end <= e.shift_start) ctx.addIssue({ code: "custom", path: ["shift_end"], message: "Must be after the shift starts" });
  if (e.left_on && e.left_on < e.joined_on) ctx.addIssue({ code: "custom", path: ["left_on"], message: "Before they joined" });
});

export const deviceSchema = z.object({
  serial: z.string().trim().regex(/^[A-Za-z0-9_-]{3,40}$/, "3 to 40 letters, digits, dashes or underscores"),
  name: text(80).min(1, "Required"),
});

export const punchSchema = z.object({
  punched_at: z.string().min(1, "Required"),
  reason: text(500).refine((v) => v.length >= 5, "Say why (at least five characters)"),
});

export const markSchema = z.object({
  day: z.string().min(1, "Required"),
  kind: z.enum(["paid_leave", "unpaid_leave", "present"]),
  reason: text(500).refine((v) => v.length >= 3, "Say why"),
});

export const payrollLineSchema = z.object({
  adjustment: z.string().trim().refine((v) => v === "" || /^-?\d{1,9}(\.\d{1,2})?$/.test(v), "Enter an amount").transform((v) => v || "0"),
  adjustment_reason: text(200),
  advance_recovery: rupees.transform((v) => v || "0"),
}).superRefine((l, ctx) => {
  if (Number(l.adjustment) !== 0 && l.adjustment_reason.length < 3) ctx.addIssue({ code: "custom", path: ["adjustment_reason"], message: "Say what it is for" });
});
