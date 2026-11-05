// One place for how money, quantities and dates read across the app.

const pkr = new Intl.NumberFormat("en-PK", { style: "currency", currency: "PKR", maximumFractionDigits: 0 });
/** Whole rupees plus paisa — for cash counts, where rounding hid real differences. */
const pkrExact = new Intl.NumberFormat("en-PK", { style: "currency", currency: "PKR", minimumFractionDigits: 2, maximumFractionDigits: 2 });
const qtyFmt = new Intl.NumberFormat("en-PK", { maximumFractionDigits: 3 });

export const money = (v: string | number | null | undefined) => (v == null || v === "" ? "None" : pkr.format(Number(v)));
export const moneyExact = (v: string | number | null | undefined) => (v == null || v === "" ? "None" : pkrExact.format(Number(v)));
/** Difference in rupees, compared to the nearest paisa (avoids float noise on cash close). */
export const moneyDiff = (counted: string | number, expected: string | number) =>
  (Math.round(Number(counted) * 100) - Math.round(Number(expected) * 100)) / 100;
export const qty = (v: string | number) => qtyFmt.format(Number(v));
export const day = (v: string | null | undefined) =>
  v ? new Date(v.length === 10 ? `${v}T00:00:00` : v).toLocaleDateString("en-PK", { day: "numeric", month: "short", year: "numeric" }) : "";
export const when = (v: string) => new Date(v).toLocaleString("en-PK", { day: "numeric", month: "short", year: "numeric", hour: "numeric", minute: "2-digit" });
export const today = () => new Date().toLocaleDateString("en-CA"); // YYYY-MM-DD in local time, not UTC

/** Phones are stored as +923001234567; people read 0300 1234567. */
/** International format for display: +92 300 1234567. */
export const phone = (v: string) => (v?.startsWith("+92") && v.length === 13 ? `+92 ${v.slice(3, 6)} ${v.slice(6)}` : v?.startsWith("+") && v.length > 8 ? `${v.slice(0, v.length - 7)} ${v.slice(-7)}` : v);

/** Pieces, sets, pairs and boxes are counted whole; litres, kilograms and metres can be part-filled. */
export const qtyStep = (unit?: string) => (["litre", "kg", "metre"].includes(unit ?? "") ? "any" : "1");
