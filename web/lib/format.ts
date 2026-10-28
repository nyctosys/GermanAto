// One place for how money, quantities and dates read across the app.

const pkr = new Intl.NumberFormat("en-PK", { style: "currency", currency: "PKR", maximumFractionDigits: 0 });
const qtyFmt = new Intl.NumberFormat("en-PK", { maximumFractionDigits: 3 });

export const money = (v: string | number | null | undefined) => (v == null || v === "" ? "None" : pkr.format(Number(v)));
export const qty = (v: string | number) => qtyFmt.format(Number(v));
export const day = (v: string | null | undefined) =>
  v ? new Date(v.length === 10 ? `${v}T00:00:00` : v).toLocaleDateString("en-PK", { day: "numeric", month: "short", year: "numeric" }) : "";
export const when = (v: string) => new Date(v).toLocaleString("en-PK", { day: "numeric", month: "short", year: "numeric", hour: "numeric", minute: "2-digit" });
export const today = () => new Date().toLocaleDateString("en-CA"); // YYYY-MM-DD in local time, not UTC

/** Phones are stored as +923001234567; people read 0300 1234567. */
export const phone = (v: string) => (v?.startsWith("+92") && v.length === 13 ? `0${v.slice(3, 6)} ${v.slice(6)}` : v);
